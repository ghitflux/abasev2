from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from django.utils.text import get_valid_filename
from rest_framework.exceptions import ValidationError

from .matching import find_associado
from .models import ArquivoRetorno, ArquivoRetornoItem, ImportacaoLog, PagamentoMensalidade
from .parsers import ETIPITxtRetornoParser, normalize_lines
from .reconciliacao import MotorReconciliacao
from .validators import ArquivoRetornoValidator

logger = logging.getLogger(__name__)


def competencia_to_date(value: str):
    return datetime.strptime(value, "%m/%Y").date().replace(day=1)


class ArquivoRetornoService:
    parser_class = ETIPITxtRetornoParser

    def __init__(self):
        self.parser = self.parser_class()

    def upload(self, arquivo, user) -> ArquivoRetorno:
        ArquivoRetornoValidator.validar_tamanho(arquivo)
        formato = ArquivoRetornoValidator.validar_formato(getattr(arquivo, "name", ""))

        raw_bytes = arquivo.read()
        if not raw_bytes:
            raise ValidationError({"arquivo": "O arquivo enviado está vazio."})

        text, _encoding = self.parser.decode_bytes(raw_bytes)
        lines = normalize_lines(text)
        ArquivoRetornoValidator.validar_cabecalho(lines)
        meta = self.parser.extract_meta(lines)

        safe_name = get_valid_filename(Path(getattr(arquivo, "name", "retorno.txt")).name)
        storage_name = default_storage.save(
            f"arquivos_retorno/{uuid4().hex}_{safe_name}",
            ContentFile(raw_bytes),
        )

        arquivo_retorno = ArquivoRetorno.objects.create(
            arquivo_nome=safe_name,
            arquivo_url=storage_name,
            formato=formato,
            orgao_origem=meta.sistema_origem,
            competencia=competencia_to_date(meta.competencia),
            status=ArquivoRetorno.Status.PENDENTE,
            uploaded_by=user,
            resultado_resumo={
                "competencia": meta.competencia,
                "data_geracao": meta.data_geracao,
                "entidade": meta.entidade,
                "sistema_origem": meta.sistema_origem,
                "baixa_efetuada": 0,
                "nao_descontado": 0,
                "pendencias_manuais": 0,
                "nao_encontrado": 0,
                "erro": 0,
                "ciclo_aberto": 0,
                "encerramentos": 0,
                "novos_ciclos": 0,
                "efetivados": 0,
                "nao_descontados": 0,
            },
        )
        ImportacaoLog.objects.create(
            arquivo_retorno=arquivo_retorno,
            tipo=ImportacaoLog.Tipo.UPLOAD,
            mensagem="Upload de arquivo retorno recebido.",
            dados={"arquivo_nome": safe_name, "competencia": meta.competencia},
        )
        self._dispatch_processamento(arquivo_retorno.id)
        arquivo_retorno.refresh_from_db()
        return arquivo_retorno

    def reprocessar(self, arquivo_retorno_id: int) -> ArquivoRetorno:
        arquivo_retorno = ArquivoRetorno.objects.get(pk=arquivo_retorno_id)
        if arquivo_retorno.status == ArquivoRetorno.Status.PROCESSANDO:
            raise ValidationError("O arquivo já está em processamento.")
        arquivo_retorno.status = ArquivoRetorno.Status.PENDENTE
        arquivo_retorno.processado_em = None
        arquivo_retorno.save(update_fields=["status", "processado_em", "updated_at"])
        ImportacaoLog.objects.create(
            arquivo_retorno=arquivo_retorno,
            tipo=ImportacaoLog.Tipo.UPLOAD,
            mensagem="Reprocessamento solicitado manualmente.",
        )
        self._dispatch_processamento(arquivo_retorno.id)
        return arquivo_retorno

    @transaction.atomic
    def processar(self, arquivo_retorno_id: int) -> ArquivoRetorno:
        arquivo_retorno = ArquivoRetorno.objects.select_for_update().get(pk=arquivo_retorno_id)
        if arquivo_retorno.status == ArquivoRetorno.Status.PROCESSANDO:
            raise ValidationError("O arquivo já está em processamento.")

        arquivo_retorno.status = ArquivoRetorno.Status.PROCESSANDO
        arquivo_retorno.processado_em = None
        arquivo_retorno.save(update_fields=["status", "processado_em", "updated_at"])

        try:
            if arquivo_retorno.itens.exists():
                arquivo_retorno.itens.all().delete()

            import_uuid = str(uuid4())

            parsed = self.parser.parse(self._arquivo_path(arquivo_retorno))
            self._persistir_itens(arquivo_retorno, parsed.items)
            duplicate_cpfs = self._detect_duplicate_cpfs(parsed.items)
            if duplicate_cpfs:
                self._marcar_cpfs_duplicados(arquivo_retorno, duplicate_cpfs)

            for warning in parsed.warnings:
                ImportacaoLog.objects.create(
                    arquivo_retorno=arquivo_retorno,
                    tipo=ImportacaoLog.Tipo.PARSE,
                    mensagem="Linha malformada ignorada durante o parse.",
                    dados=warning,
                )

            resumo = MotorReconciliacao(arquivo_retorno).reconciliar()
            resumo.update(
                {
                    "competencia": parsed.meta.competencia,
                    "data_geracao": parsed.meta.data_geracao,
                    "entidade": parsed.meta.entidade,
                    "sistema_origem": parsed.meta.sistema_origem,
                }
            )
            resumo["cpfs_duplicados_arquivo"] = len(duplicate_cpfs)
            resumo["linhas_duplicadas_ignoradas"] = sum(
                len(group) for group in duplicate_cpfs.values()
            )

            # Upsert PagamentoMensalidade (equivalente ao baixaUpload do PHP)
            resumo_pm = self._upsert_pagamentos_mensalidade(
                arquivo_retorno=arquivo_retorno,
                items=parsed.items,
                import_uuid=import_uuid,
                user=arquivo_retorno.uploaded_by,
                ignored_cpfs=set(duplicate_cpfs),
            )
            resumo.update(resumo_pm)

            arquivo_retorno.total_registros = len(parsed.items)
            arquivo_retorno.processados = arquivo_retorno.itens.filter(processado=True).count()
            arquivo_retorno.nao_encontrados = resumo["nao_encontrado"]
            arquivo_retorno.erros = resumo["erro"] + len(parsed.warnings)
            arquivo_retorno.resultado_resumo = resumo
            arquivo_retorno.status = ArquivoRetorno.Status.CONCLUIDO
            arquivo_retorno.processado_em = timezone.now()
            arquivo_retorno.save(
                update_fields=[
                    "total_registros",
                    "processados",
                    "nao_encontrados",
                    "erros",
                    "resultado_resumo",
                    "status",
                    "processado_em",
                    "updated_at",
                ]
            )
            ImportacaoLog.objects.create(
                arquivo_retorno=arquivo_retorno,
                tipo=ImportacaoLog.Tipo.BAIXA,
                mensagem=(
                    f"Importação concluída: {resumo_pm['pm_criados']} lançamentos, "
                    f"{resumo_pm['pm_duplicados']} duplicados ignorados, "
                    f"{resumo_pm['pm_cpfs_duplicados_arquivo']} CPFs duplicados no arquivo isolados, "
                    f"{resumo_pm['pm_vinculados']} vinculados a associados, "
                    f"{resumo_pm['pm_nao_encontrados']} não encontrados."
                ),
                dados=resumo,
            )
        except Exception as exc:
            arquivo_retorno.status = ArquivoRetorno.Status.ERRO
            arquivo_retorno.processado_em = timezone.now()
            arquivo_retorno.resultado_resumo = {
                **arquivo_retorno.resultado_resumo,
                "erro": arquivo_retorno.resultado_resumo.get("erro", 0) + 1,
                "mensagem": str(exc),
            }
            arquivo_retorno.save(
                update_fields=["status", "processado_em", "resultado_resumo", "updated_at"]
            )
            ImportacaoLog.objects.create(
                arquivo_retorno=arquivo_retorno,
                tipo=ImportacaoLog.Tipo.ERRO,
                mensagem="Falha ao processar o arquivo retorno.",
                dados={"erro": str(exc)},
            )
            raise

        return arquivo_retorno

    def _upsert_pagamentos_mensalidade(
        self,
        arquivo_retorno: ArquivoRetorno,
        items: list[dict],
        import_uuid: str,
        user,
        ignored_cpfs: set[str] | None = None,
    ) -> dict:
        """Cria ou atualiza registros de PagamentoMensalidade com lógica de upsert.
        Equivalente ao baixaUpload do PHP AdminController.

        Regras:
        - Upsert por (cpf_cnpj, referencia_month)
        - Duplicado: mantém registro; backfill de associado se não tiver vínculo
        - Novo: cria com todos os campos
        - Se cadastro tiver 3+ pagamentos com status_code in ['1','4'] → campo não existe aqui
          (lógica de conclusão de contrato é responsabilidade da reconciliação)

        Retorna resumo de contagens.
        """
        criados = 0
        duplicados = 0
        vinculados = 0
        nao_encontrados_list: list[dict] = []
        erros_list: list[dict] = []
        ignored_cpfs = ignored_cpfs or set()
        ignored_lines = 0

        # referencia_month vem da competencia do arquivo (MM/YYYY → YYYY-MM-01)
        competencia = arquivo_retorno.resultado_resumo.get("competencia", "")
        try:
            ref_date = datetime.strptime(competencia, "%m/%Y").date().replace(day=1)
        except (ValueError, TypeError):
            ref_date = arquivo_retorno.competencia

        source_path = arquivo_retorno.arquivo_url

        for i, item in enumerate(items):
            cpf = re.sub(r"\D", "", item.get("cpf_cnpj", ""))
            if not cpf:
                continue
            if cpf in ignored_cpfs:
                ignored_lines += 1
                continue

            valor = item.get("valor_descontado", item.get("valor"))
            status = item.get("status_codigo", item.get("status_code", ""))
            matricula = item.get("matricula_servidor", item.get("matricula", ""))
            nome = item.get("nome_servidor", item.get("nome", ""))
            orgao = (
                item.get("orgao_pagto_nome")
                or item.get("orgao_pagto")
                or item.get("orgao_pagto_codigo", "")
            )
            orgao_codigo = item.get("orgao_pagto_codigo", "")
            orgao_interno = item.get("orgao_codigo", "")
            linha = item.get("linha_numero", i + 1)

            try:
                assoc = find_associado(
                    cpf=cpf,
                    matricula=matricula,
                    nome=nome,
                    orgao=orgao,
                    orgao_alternativo=orgao_codigo,
                    orgao_codigo=orgao_interno,
                )

                existing = PagamentoMensalidade.objects.filter(
                    cpf_cnpj=cpf,
                    referencia_month=ref_date,
                ).first()

                if existing:
                    # Duplicado: backfill do vínculo se não tiver
                    duplicados += 1
                    if not existing.associado_id and assoc:
                        existing.associado = assoc
                        existing.save(update_fields=["associado", "updated_at"])
                        vinculados += 1
                    continue

                # Novo lançamento
                PagamentoMensalidade.objects.create(
                    created_by=user,
                    import_uuid=import_uuid,
                    referencia_month=ref_date,
                    status_code=status,
                    matricula=matricula,
                    orgao_pagto=orgao,
                    nome_relatorio=nome,
                    cpf_cnpj=cpf,
                    valor=valor,
                    source_file_path=source_path,
                    associado=assoc,
                )
                criados += 1
                if assoc:
                    vinculados += 1
                else:
                    nao_encontrados_list.append({
                        "linha": linha, "cpf": cpf, "nome": nome,
                        "valor": str(valor), "status": status,
                    })

            except Exception as exc:
                erros_list.append({
                    "linha": linha, "cpf": cpf, "nome": nome, "motivo": str(exc),
                })
                logger.warning("[RETORNO] erro ao upsert PagamentoMensalidade linha=%s: %s", linha, exc)

        resumo_pagamentos = {
            "pm_criados": criados,
            "pm_duplicados": duplicados,
            "pm_vinculados": vinculados,
            "pm_nao_encontrados": len(nao_encontrados_list),
            "pm_erros": len(erros_list),
            "pm_cpfs_duplicados_arquivo": len(ignored_cpfs),
            "pm_linhas_duplicadas_ignoradas": ignored_lines,
        }
        logger.info(
            "[RETORNO] upsert PagamentoMensalidade concluído: %s",
            resumo_pagamentos,
        )
        return resumo_pagamentos

    def _detect_duplicate_cpfs(self, items: list[dict]) -> dict[str, list[dict]]:
        contagem = Counter(
            re.sub(r"\D", "", str(item.get("cpf_cnpj", "")))
            for item in items
            if item.get("cpf_cnpj")
        )
        duplicados = {
            cpf: []
            for cpf, total in contagem.items()
            if cpf and total > 1
        }
        if not duplicados:
            return {}
        for item in items:
            cpf = re.sub(r"\D", "", str(item.get("cpf_cnpj", "")))
            if cpf in duplicados:
                duplicados[cpf].append(item)
        return duplicados

    def _marcar_cpfs_duplicados(
        self, arquivo_retorno: ArquivoRetorno, duplicate_cpfs: dict[str, list[dict]]
    ) -> None:
        observacao = (
            "CPF duplicado no mesmo arquivo retorno. "
            "As linhas foram isoladas da baixa automática para revisão manual."
        )
        for cpf, itens in duplicate_cpfs.items():
            linhas = [item.get("linha_numero") for item in itens]
            arquivo_retorno.itens.filter(cpf_cnpj=cpf).update(
                processado=True,
                resultado_processamento=ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL,
                observacao=observacao,
                associado=None,
                parcela=None,
            )
            ImportacaoLog.objects.create(
                arquivo_retorno=arquivo_retorno,
                tipo=ImportacaoLog.Tipo.VALIDACAO,
                mensagem="CPF duplicado isolado da conciliação automática.",
                dados={"cpf_cnpj": cpf, "linhas": linhas},
            )

    def _persistir_itens(self, arquivo_retorno: ArquivoRetorno, items: list[dict]) -> None:
        objetos: list[ArquivoRetornoItem] = []
        for item in items:
            try:
                ArquivoRetornoValidator.validar_item(item)
            except ValidationError as exc:
                ImportacaoLog.objects.create(
                    arquivo_retorno=arquivo_retorno,
                    tipo=ImportacaoLog.Tipo.VALIDACAO,
                    mensagem="Item inválido ignorado durante a persistência.",
                    dados={
                        "linha_numero": item.get("linha_numero"),
                        "erros": exc.detail,
                    },
                )
                continue
            objetos.append(ArquivoRetornoItem(arquivo_retorno=arquivo_retorno, **item))

        ArquivoRetornoItem.objects.bulk_create(objetos)

    def _arquivo_path(self, arquivo_retorno: ArquivoRetorno) -> str:
        return default_storage.path(arquivo_retorno.arquivo_url)

    def _dispatch_processamento(self, arquivo_retorno_id: int) -> None:
        from .tasks import processar_arquivo_retorno

        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            self.processar(arquivo_retorno_id)
            return

        try:
            processar_arquivo_retorno.delay(arquivo_retorno_id)
        except Exception:
            self.processar(arquivo_retorno_id)
