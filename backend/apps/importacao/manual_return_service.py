from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from django.utils.text import get_valid_filename
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.contratos.models import Parcela
from apps.importacao.legacy import list_legacy_pagamento_snapshots_from_dump
from apps.importacao.manual_report import ManualReturnReport, parse_manual_report_pdf
from apps.importacao.matching import find_associado
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem, ImportacaoLog, PagamentoMensalidade


@dataclass(frozen=True)
class ManualReturnBuildResult:
    arquivo_id: int | None
    created: bool
    updated: bool
    competencia: str
    rows_total: int
    matched_pagamentos: int
    matched_parcelas: int
    missing_pagamentos: int
    missing_parcelas: int
    esperado_total: str
    recebido_total: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalize_cpf(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _default_uploaded_by() -> User:
    user = (
        User.objects.filter(is_active=True, roles__codigo__in=["TESOUREIRO", "ADMIN"])
        .distinct()
        .order_by("id")
        .first()
    )
    if user is None:
        raise ValidationError(
            "Nenhum usuário ativo com perfil TESOUREIRO/ADMIN disponível para registrar o arquivo manual."
        )
    return user


def _report_storage_name(pdf_path: Path) -> str:
    safe_name = get_valid_filename(pdf_path.name)
    return f"arquivos_retorno/manual/{uuid4().hex}_{safe_name}"


def _manual_item_payload(
    *,
    report_row,
    pagamento: PagamentoMensalidade,
    arquivo_retorno: ArquivoRetorno,
    linha_numero: int,
):
    associado = pagamento.associado or find_associado(
        cpf=report_row.cpf_cnpj,
        matricula=pagamento.matricula,
        nome=report_row.nome,
        orgao=pagamento.orgao_pagto,
    )
    parcela = None
    if associado is not None:
        parcela = (
            Parcela.all_objects.filter(
                associado=associado,
                referencia_mes=arquivo_retorno.competencia,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("-created_at", "-id")
            .first()
        )

    return {
        "arquivo_retorno": arquivo_retorno,
        "linha_numero": linha_numero,
        "cpf_cnpj": report_row.cpf_cnpj,
        "matricula_servidor": pagamento.matricula or getattr(associado, "matricula_orgao", "") or "",
        "nome_servidor": report_row.nome,
        "cargo": "",
        "competencia": arquivo_retorno.competencia.strftime("%m/%Y"),
        "valor_descontado": report_row.recebido,
        "status_codigo": report_row.status,
        "status_desconto": ArquivoRetornoItem.StatusDesconto.EFETIVADO,
        "status_descricao": "Baixa manual consolidada por relatório mensal.",
        "motivo_rejeicao": "",
        "orgao_codigo": "",
        "orgao_pagto_codigo": "",
        "orgao_pagto_nome": pagamento.orgao_pagto,
        "associado": associado,
        "parcela": parcela,
        "processado": True,
        "resultado_processamento": ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
        "observacao": "Baixa manual registrada a partir do relatório mensal da competência.",
        "payload_bruto": {
            "origem_baixa": "manual_relatorio",
            "fonte_pdf": arquivo_retorno.arquivo_url,
            "legacy_payment_id": report_row.legacy_id,
            "manual_paid_at": report_row.paid_at.isoformat(),
            "recebido_manual": str(report_row.recebido),
            "esperado_manual": str(report_row.esperado),
        },
        "gerou_encerramento": False,
        "gerou_novo_ciclo": False,
    }


class ManualReturnReportService:
    @transaction.atomic
    def create_or_update_from_pdf(
        self,
        *,
        pdf_path: str | Path,
        dump_path: str | Path,
        uploaded_by: User | None = None,
        expected_competencia: date | None = None,
        execute: bool = False,
    ) -> tuple[ManualReturnBuildResult, ManualReturnReport]:
        report = parse_manual_report_pdf(pdf_path)
        if expected_competencia and report.competencia != expected_competencia:
            raise ValidationError(
                "Competência do PDF divergente do valor informado em --competencia."
            )
        snapshots = list_legacy_pagamento_snapshots_from_dump(
            dump_path=dump_path,
            competencia=report.competencia,
        )
        pagamentos = {
            _normalize_cpf(item.cpf_cnpj): item
            for item in PagamentoMensalidade.objects.filter(
                referencia_month=report.competencia,
                manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            ).order_by("cpf_cnpj", "id")
        }

        missing_pagamentos = 0
        matched_pagamentos = 0
        matched_parcelas = 0
        missing_parcelas = 0
        item_payloads: list[dict[str, object]] = []

        for linha_numero, row in enumerate(report.rows, start=1):
            snapshot = snapshots.get((_normalize_cpf(row.cpf_cnpj), report.competencia))
            pagamento = pagamentos.get(_normalize_cpf(row.cpf_cnpj))
            if snapshot is None or pagamento is None:
                missing_pagamentos += 1
                continue
            matched_pagamentos += 1
            payload = _manual_item_payload(
                report_row=row,
                pagamento=pagamento,
                arquivo_retorno=ArquivoRetorno(
                    competencia=report.competencia,
                    arquivo_url="",
                    formato=ArquivoRetorno.Formato.MANUAL,
                ),
                linha_numero=linha_numero,
            )
            if payload["parcela"] is None:
                missing_parcelas += 1
            else:
                matched_parcelas += 1
            item_payloads.append(payload)

        if matched_pagamentos != report.total:
            raise ValidationError(
                f"Relatório manual divergente: {matched_pagamentos}/{report.total} CPFs encontrados no banco atual."
            )

        if execute:
            user = uploaded_by or _default_uploaded_by()
            pdf = Path(pdf_path).expanduser()
            storage_name = default_storage.save(
                _report_storage_name(pdf),
                ContentFile(pdf.read_bytes()),
            )
            existing = (
                ArquivoRetorno.objects.filter(
                    competencia=report.competencia,
                    formato=ArquivoRetorno.Formato.MANUAL,
                )
                .order_by("-created_at", "-id")
                .first()
            )
            created = existing is None
            arquivo_retorno = existing or ArquivoRetorno(uploaded_by=user)
            arquivo_retorno.arquivo_nome = pdf.name
            arquivo_retorno.arquivo_url = storage_name
            arquivo_retorno.formato = ArquivoRetorno.Formato.MANUAL
            arquivo_retorno.orgao_origem = "Relatório mensal de baixa manual"
            arquivo_retorno.competencia = report.competencia
            arquivo_retorno.total_registros = report.total
            arquivo_retorno.processados = report.total
            arquivo_retorno.nao_encontrados = 0
            arquivo_retorno.erros = 0
            arquivo_retorno.status = ArquivoRetorno.Status.CONCLUIDO
            arquivo_retorno.processado_em = timezone.now()
            arquivo_retorno.uploaded_by = user
            arquivo_retorno.resultado_resumo = {
                "competencia": report.competencia.strftime("%m/%Y"),
                "data_geracao": (
                    report.generated_at.strftime("%d/%m/%Y %H:%M")
                    if report.generated_at
                    else ""
                ),
                "entidade": "ABASE",
                "sistema_origem": "manual_relatorio",
                "baixa_efetuada": report.total,
                "nao_descontado": 0,
                "pendencias_manuais": 0,
                "nao_encontrado": 0,
                "erro": 0,
                "ciclo_aberto": 0,
                "encerramentos": 0,
                "novos_ciclos": 0,
                "efetivados": report.ok_total,
                "nao_descontados": 0,
                "origem_processamento": "manual_relatorio",
                "esperado_total": f"{report.esperado_total:.2f}",
                "recebido_total": f"{report.recebido_total:.2f}",
            }
            arquivo_retorno.save()

            arquivo_retorno.itens.all().delete()
            arquivo_retorno.logs.all().delete()

            for payload in item_payloads:
                payload["arquivo_retorno"] = arquivo_retorno
                payload["payload_bruto"]["fonte_pdf"] = storage_name
                ArquivoRetornoItem.objects.create(**payload)

            ImportacaoLog.objects.create(
                arquivo_retorno=arquivo_retorno,
                tipo=ImportacaoLog.Tipo.UPLOAD,
                mensagem="Relatório mensal de baixa manual registrado.",
                dados={
                    "competencia": report.competencia.strftime("%Y-%m"),
                    "arquivo_nome": pdf.name,
                    "origem_processamento": "manual_relatorio",
                },
            )
            ImportacaoLog.objects.create(
                arquivo_retorno=arquivo_retorno,
                tipo=ImportacaoLog.Tipo.BAIXA,
                mensagem="Arquivo retorno sintético de baixas manuais gerado.",
                dados={
                    "total": report.total,
                    "ok": report.ok_total,
                    "esperado": f"{report.esperado_total:.2f}",
                    "recebido": f"{report.recebido_total:.2f}",
                },
            )
        else:
            transaction.set_rollback(True)
            arquivo_retorno = None
            created = False

        result = ManualReturnBuildResult(
            arquivo_id=arquivo_retorno.id if execute and arquivo_retorno else None,
            created=created if execute else False,
            updated=bool(execute and not created),
            competencia=report.competencia.isoformat(),
            rows_total=report.total,
            matched_pagamentos=matched_pagamentos,
            matched_parcelas=matched_parcelas,
            missing_pagamentos=missing_pagamentos,
            missing_parcelas=missing_parcelas,
            esperado_total=f"{report.esperado_total:.2f}",
            recebido_total=f"{report.recebido_total:.2f}",
        )
        return result, report
