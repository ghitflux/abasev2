from __future__ import annotations

import gc
import logging
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from django.utils.text import get_valid_filename
from rest_framework.exceptions import ValidationError

from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.models import Contrato

from .dry_run import simular_dry_run
from .duplicidade import DuplicidadeFinanceiraService
from .financeiro import build_financeiro_resumo
from .legacy import LegacyPagamentoSnapshot, list_legacy_pagamento_snapshots
from .manual_return_conflicts import (
    should_skip_legacy_manual_snapshot,
)
from .matching import find_associado
from .models import (
    ArquivoRetorno,
    ArquivoRetornoItem,
    DuplicidadeFinanceira,
    ImportacaoLog,
    PagamentoMensalidade,
)
from .parsers import ETIPITxtRetornoParser, normalize_lines
from .reconciliacao import MotorReconciliacao
from .validators import ArquivoRetornoValidator

logger = logging.getLogger(__name__)


def competencia_to_date(value: str):
    return datetime.strptime(value, "%m/%Y").date().replace(day=1)


def normalize_snapshot_manual_paid_at(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if timezone.is_aware(value):
        return timezone.localtime(value, timezone.get_current_timezone())
    return timezone.make_aware(value, timezone.get_current_timezone())


def compare_manual_paid_at(
    current: datetime | None,
    snapshot: datetime | None,
) -> str:
    if current is None and snapshot is None:
        return "missing"
    if current is None or snapshot is None:
        return "different"

    normalized_snapshot = normalize_snapshot_manual_paid_at(snapshot)
    if normalized_snapshot is None:
        return "different"

    current_local = timezone.localtime(current, timezone.get_current_timezone())
    if current_local == normalized_snapshot:
        return "exact"

    return "different"


def classify_manual_paid_at_difference(
    current: datetime | None,
    snapshot: datetime | None,
) -> str:
    if current is None and snapshot is None:
        return "missing"
    if current is None or snapshot is None:
        return "different"

    normalized_snapshot = normalize_snapshot_manual_paid_at(snapshot)
    if normalized_snapshot is None:
        return "different"

    current_local = timezone.localtime(current, timezone.get_current_timezone())
    if current_local != normalized_snapshot:
        return "different"

    current_utc_naive = current.astimezone(dt_timezone.utc).replace(tzinfo=None)
    if current_utc_naive - snapshot == timedelta(hours=3):
        return "timezone_only"

    return "exact"


def _apply_legacy_snapshot_to_pagamento(
    pagamento: PagamentoMensalidade,
    snapshot: LegacyPagamentoSnapshot | None,
    *,
    overwrite: bool = False,
) -> list[str]:
    if not snapshot:
        return []

    updated_fields: list[str] = []

    if snapshot.manual_status and (overwrite or not pagamento.manual_status):
        if pagamento.manual_status != snapshot.manual_status:
            pagamento.manual_status = snapshot.manual_status
            updated_fields.append("manual_status")
    if (
        snapshot.esperado_manual is not None
        and (overwrite or pagamento.esperado_manual is None)
        and pagamento.esperado_manual != snapshot.esperado_manual
    ):
        pagamento.esperado_manual = snapshot.esperado_manual
        updated_fields.append("esperado_manual")
    if (
        snapshot.recebido_manual is not None
        and (overwrite or pagamento.recebido_manual is None)
        and pagamento.recebido_manual != snapshot.recebido_manual
    ):
        pagamento.recebido_manual = snapshot.recebido_manual
        updated_fields.append("recebido_manual")
    normalized_snapshot_paid_at = normalize_snapshot_manual_paid_at(snapshot.manual_paid_at)
    if (
        normalized_snapshot_paid_at is not None
        and (overwrite or pagamento.manual_paid_at is None)
        and compare_manual_paid_at(
            pagamento.manual_paid_at,
            snapshot.manual_paid_at,
        )
        == "different"
    ):
        pagamento.manual_paid_at = normalized_snapshot_paid_at
        updated_fields.append("manual_paid_at")
    if (
        snapshot.manual_forma_pagamento
        and (overwrite or not pagamento.manual_forma_pagamento)
        and pagamento.manual_forma_pagamento != snapshot.manual_forma_pagamento
    ):
        pagamento.manual_forma_pagamento = snapshot.manual_forma_pagamento
        updated_fields.append("manual_forma_pagamento")
    if (
        snapshot.manual_comprovante_path
        and (overwrite or not pagamento.manual_comprovante_path)
        and pagamento.manual_comprovante_path != snapshot.manual_comprovante_path
    ):
        pagamento.manual_comprovante_path = snapshot.manual_comprovante_path
        updated_fields.append("manual_comprovante_path")
    if (
        snapshot.agente_refi_solicitado
        and (overwrite or not pagamento.agente_refi_solicitado)
        and pagamento.agente_refi_solicitado != snapshot.agente_refi_solicitado
    ):
        pagamento.agente_refi_solicitado = snapshot.agente_refi_solicitado
        updated_fields.append("agente_refi_solicitado")
    if snapshot.has_manual_context() and not pagamento.source_file_path:
        pagamento.source_file_path = "legacy/pagamentos_mensalidades"
        updated_fields.append("source_file_path")

    return updated_fields


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
        competencia = competencia_to_date(meta.competencia)

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
            competencia=competencia,
            status=ArquivoRetorno.Status.AGUARDANDO_CONFIRMACAO,
            uploaded_by=user,
            resultado_resumo={
                "competencia": meta.competencia,
                "data_geracao": meta.data_geracao,
                "entidade": meta.entidade,
                "sistema_origem": meta.sistema_origem,
                "baixa_efetuada": 0,
                "nao_descontado": 0,
                "pendencias_manuais": 0,
                "duplicidades": 0,
                "nao_encontrado": 0,
                "associados_importados": 0,
                "erro": 0,
                "ciclo_aberto": 0,
                "encerramentos": 0,
                "novos_ciclos": 0,
                "efetivados": 0,
                "nao_descontados": 0,
            },
        )

        # Parse completo e dry-run síncrono — leitura pura do banco, sem escrita
        parsed = self.parser.parse(self._arquivo_path(arquivo_retorno))
        items_unicos, _ = self._deduplicar_itens_por_cpf(parsed.items)
        dry_run = simular_dry_run(competencia=competencia, parsed_items=items_unicos)
        arquivo_retorno.dry_run_resultado = dry_run
        arquivo_retorno.save(update_fields=["dry_run_resultado", "updated_at"])

        ImportacaoLog.objects.create(
            arquivo_retorno=arquivo_retorno,
            tipo=ImportacaoLog.Tipo.UPLOAD,
            mensagem="Upload de arquivo retorno recebido. Aguardando confirmação do usuário.",
            dados={"arquivo_nome": safe_name, "competencia": meta.competencia},
        )

        arquivo_retorno.refresh_from_db()
        return arquivo_retorno

    def confirmar(self, arquivo_retorno_id: int) -> ArquivoRetorno:
        """Confirma a importação e dispara o processamento Celery."""
        arquivo_retorno = ArquivoRetorno.objects.get(pk=arquivo_retorno_id)
        if arquivo_retorno.status != ArquivoRetorno.Status.AGUARDANDO_CONFIRMACAO:
            raise ValidationError(
                "O arquivo não está aguardando confirmação. "
                f"Status atual: {arquivo_retorno.status}."
            )
        arquivo_retorno.status = ArquivoRetorno.Status.PENDENTE
        arquivo_retorno.save(update_fields=["status", "updated_at"])
        ImportacaoLog.objects.create(
            arquivo_retorno=arquivo_retorno,
            tipo=ImportacaoLog.Tipo.UPLOAD,
            mensagem="Importação confirmada pelo usuário. Processamento iniciado.",
        )
        self._dispatch_processamento(arquivo_retorno.id)
        arquivo_retorno.refresh_from_db()
        return arquivo_retorno

    def cancelar(self, arquivo_retorno_id: int) -> None:
        """Cancela e remove (soft-delete) o arquivo aguardando confirmação."""
        arquivo_retorno = ArquivoRetorno.objects.get(pk=arquivo_retorno_id)
        if arquivo_retorno.status != ArquivoRetorno.Status.AGUARDANDO_CONFIRMACAO:
            raise ValidationError(
                "Não é possível cancelar um arquivo que não está aguardando confirmação. "
                f"Status atual: {arquivo_retorno.status}."
            )
        arquivo_retorno.delete()

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

    def processar(self, arquivo_retorno_id: int) -> ArquivoRetorno:
        # Adquire lock apenas para a transição de status (evitar processamento duplo)
        with transaction.atomic():
            arquivo_retorno = ArquivoRetorno.objects.select_for_update().get(pk=arquivo_retorno_id)
            if arquivo_retorno.status == ArquivoRetorno.Status.PROCESSANDO:
                raise ValidationError("O arquivo já está em processamento.")
            arquivo_retorno.status = ArquivoRetorno.Status.PROCESSANDO
            arquivo_retorno.processado_em = None
            arquivo_retorno.save(update_fields=["status", "processado_em", "updated_at"])
        # Processamento pesado sem lock — permite queries de leitura paralelas

        try:
            if arquivo_retorno.itens.exists():
                DuplicidadeFinanceira.objects.filter(
                    arquivo_retorno_item__arquivo_retorno=arquivo_retorno
                ).delete()
                arquivo_retorno.itens.all().delete()

            import_uuid = str(uuid4())

            parsed = self.parser.parse(self._arquivo_path(arquivo_retorno))
            items, duplicate_cpfs = self._deduplicar_itens_por_cpf(parsed.items)
            self._persistir_itens(arquivo_retorno, items)
            if duplicate_cpfs:
                self._registrar_cpfs_duplicados_consolidados(arquivo_retorno, duplicate_cpfs)

            for warning in parsed.warnings:
                ImportacaoLog.objects.create(
                    arquivo_retorno=arquivo_retorno,
                    tipo=ImportacaoLog.Tipo.PARSE,
                    mensagem="Linha malformada ignorada durante o parse.",
                    dados=warning,
                )

            resumo_pm = self._upsert_pagamentos_mensalidade(
                arquivo_retorno=arquivo_retorno,
                items=items,
                import_uuid=import_uuid,
                user=arquivo_retorno.uploaded_by,
            )
            contract_ids_to_rebuild = list(set(resumo_pm.pop("pm_contract_ids_to_rebuild", [])))
            if contract_ids_to_rebuild:
                chunk_size = 50
                for i in range(0, len(contract_ids_to_rebuild), chunk_size):
                    chunk_ids = contract_ids_to_rebuild[i : i + chunk_size]
                    contratos = list(
                        Contrato.objects.select_related("associado")
                        .filter(id__in=chunk_ids)
                        .order_by("id")
                    )
                    for contrato in contratos:
                        rebuild_contract_cycle_state(contrato, execute=True)
                    del contratos
                    gc.collect()

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
                len(group["ignoradas"]) for group in duplicate_cpfs.values()
            )
            resumo_pm["pm_cpfs_duplicados_arquivo"] = len(duplicate_cpfs)
            resumo_pm["pm_linhas_duplicadas_ignoradas"] = resumo["linhas_duplicadas_ignoradas"]
            resumo.update(resumo_pm)
            resumo["financeiro"] = build_financeiro_resumo(
                competencia=arquivo_retorno.competencia
            )

            arquivo_retorno.total_registros = len(items)
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
                    f"{resumo_pm['pm_duplicidades_abertas']} conflitos enviados para duplicidade, "
                    f"{resumo_pm['pm_cpfs_duplicados_arquivo']} CPFs duplicados no arquivo consolidados, "
                    f"{resumo_pm['pm_vinculados']} vinculados a associados, "
                    f"{resumo_pm['pm_nao_encontrados']} CPFs não encontrados."
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
        nao_encontrados = 0
        duplicidades_abertas = 0
        contract_ids_to_rebuild: set[int] = set()
        erros_list: list[dict] = []

        # referencia_month vem da competencia do arquivo (MM/YYYY → YYYY-MM-01)
        competencia = arquivo_retorno.resultado_resumo.get("competencia", "")
        try:
            ref_date = datetime.strptime(competencia, "%m/%Y").date().replace(day=1)
        except (ValueError, TypeError):
            ref_date = arquivo_retorno.competencia

        source_path = arquivo_retorno.arquivo_url
        legacy_snapshots = list_legacy_pagamento_snapshots(competencia=ref_date)

        for i, item in enumerate(items):
            cpf = re.sub(r"\D", "", item.get("cpf_cnpj", ""))
            if not cpf:
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
                if assoc is None:
                    nao_encontrados += 1
                item_obj = arquivo_retorno.itens.filter(linha_numero=linha).first()
                if item_obj is not None and assoc and item_obj.associado_id != assoc.id:
                    item_obj.associado = assoc
                    item_obj.save(update_fields=["associado", "updated_at"])

                if existing:
                    # Duplicado: backfill do vínculo se não tiver
                    duplicados += 1
                    update_fields: list[str] = []
                    if not existing.associado_id and assoc:
                        existing.associado = assoc
                        update_fields.append("associado")
                        vinculados += 1
                    duplicidade = None
                    if item_obj is not None:
                        duplicidade, _pagamento_conflict = (
                            DuplicidadeFinanceiraService.detect_existing_conflict(
                                item=item_obj,
                                cpf_cnpj=cpf,
                                competencia=ref_date,
                                valor=Decimal(str(valor)) if valor is not None else None,
                            )
                        )
                    if duplicidade is not None:
                        duplicidades_abertas += 1
                        if existing.associado_id:
                            contract_ids_to_rebuild.update(
                                Contrato.objects.filter(associado_id=existing.associado_id).values_list(
                                    "id", flat=True
                                )
                            )
                    elif not should_skip_legacy_manual_snapshot(return_status_code=status):
                        update_fields.extend(
                            _apply_legacy_snapshot_to_pagamento(
                                existing,
                                legacy_snapshots.get(cpf),
                            )
                        )
                    if update_fields:
                        existing.save(update_fields=[*sorted(set(update_fields)), "updated_at"])
                    continue

                # Novo lançamento
                if item_obj is not None:
                    duplicidade, conflito_pagamento = (
                        DuplicidadeFinanceiraService.detect_existing_conflict(
                            item=item_obj,
                            cpf_cnpj=cpf,
                            competencia=ref_date,
                            valor=Decimal(str(valor)) if valor is not None else None,
                        )
                    )
                    if duplicidade is not None:
                        duplicados += 1
                        if conflito_pagamento and conflito_pagamento.associado_id:
                            contract_ids_to_rebuild.update(
                                Contrato.objects.filter(
                                    associado_id=conflito_pagamento.associado_id
                                ).values_list("id", flat=True)
                            )
                        continue

                pagamento = PagamentoMensalidade(
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
                if not should_skip_legacy_manual_snapshot(return_status_code=status):
                    _apply_legacy_snapshot_to_pagamento(
                        pagamento,
                        legacy_snapshots.get(cpf),
                    )
                pagamento.save()
                criados += 1
                if assoc:
                    vinculados += 1

            except Exception as exc:
                erros_list.append({
                    "linha": linha, "cpf": cpf, "nome": nome, "motivo": str(exc),
                })
                logger.warning("[RETORNO] erro ao upsert PagamentoMensalidade linha=%s: %s", linha, exc)

        resumo_pagamentos = {
            "pm_criados": criados,
            "pm_duplicados": duplicados,
            "pm_vinculados": vinculados,
            "pm_duplicidades_abertas": duplicidades_abertas,
            "pm_nao_encontrados": nao_encontrados,
            "pm_associados_importados": 0,
            "pm_erros": len(erros_list),
            "pm_cpfs_duplicados_arquivo": 0,
            "pm_linhas_duplicadas_ignoradas": 0,
            "pm_contract_ids_to_rebuild": sorted(contract_ids_to_rebuild),
        }
        logger.info(
            "[RETORNO] upsert PagamentoMensalidade concluído: %s",
            resumo_pagamentos,
        )
        return resumo_pagamentos

    def _deduplicar_itens_por_cpf(
        self, items: list[dict]
    ) -> tuple[list[dict], dict[str, dict[str, list[dict] | dict]]]:
        itens_unicos: list[dict] = []
        itens_por_cpf: dict[str, dict] = {}
        duplicados: dict[str, dict[str, list[dict] | dict]] = {}

        for item in items:
            cpf = re.sub(r"\D", "", str(item.get("cpf_cnpj", "")))
            if not cpf:
                itens_unicos.append(item)
                continue

            if cpf not in itens_por_cpf:
                itens_por_cpf[cpf] = item
                itens_unicos.append(item)
                continue

            bucket = duplicados.setdefault(
                cpf,
                {
                    "mantida": itens_por_cpf[cpf],
                    "ignoradas": [],
                },
            )
            bucket["ignoradas"].append(item)

        return itens_unicos, duplicados

    def _registrar_cpfs_duplicados_consolidados(
        self,
        arquivo_retorno: ArquivoRetorno,
        duplicate_cpfs: dict[str, dict[str, list[dict] | dict]],
    ) -> None:
        for cpf, payload in duplicate_cpfs.items():
            mantida = payload["mantida"]
            ignoradas = payload["ignoradas"]
            linhas_ignoradas = [item.get("linha_numero") for item in ignoradas]
            ImportacaoLog.objects.create(
                arquivo_retorno=arquivo_retorno,
                tipo=ImportacaoLog.Tipo.VALIDACAO,
                mensagem="CPF duplicado consolidado no padrão legado.",
                dados={
                    "cpf_cnpj": cpf,
                    "linha_mantida": mantida.get("linha_numero"),
                    "linhas_ignoradas": linhas_ignoradas,
                },
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

        if not self._has_active_celery_worker():
            logger.warning(
                "Nenhum worker Celery ativo respondeu ao ping. "
                "Processando arquivo retorno %s inline.",
                arquivo_retorno_id,
            )
            self.processar(arquivo_retorno_id)
            return

        try:
            processar_arquivo_retorno.delay(arquivo_retorno_id)
        except Exception:
            logger.exception(
                "Falha ao enfileirar processamento Celery do arquivo retorno %s. "
                "Executando inline.",
                arquivo_retorno_id,
            )
            self.processar(arquivo_retorno_id)

    def _has_active_celery_worker(self, timeout: float = 1.0) -> bool:
        try:
            from config.celery import app as celery_app

            inspector = celery_app.control.inspect(timeout=timeout)
            ping_result = inspector.ping() or {}
            return bool(ping_result)
        except Exception:
            logger.exception("Falha ao verificar disponibilidade do worker Celery.")
            return False
