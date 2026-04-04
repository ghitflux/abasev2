from __future__ import annotations

from datetime import date, datetime

from apps.associados.models import Associado, only_digits


RETORNO_IMPORTED_FLAG = "associado_importado_por_retorno"


def parse_data_geracao_retorno(value: str | date | None) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%d/%m/%Y").date()
    except ValueError:
        return None


def build_imported_matricula(cpf_cnpj: str) -> str:
    return f"RET-{only_digits(cpf_cnpj)}"[:20]


def upsert_imported_associado_from_retorno(
    *,
    arquivo_nome: str,
    competencia: date,
    data_geracao: str | date | None,
    cpf_cnpj: str,
    nome_completo: str,
    matricula_orgao: str = "",
    orgao_publico: str = "",
    cargo: str = "",
    existing: Associado | None = None,
) -> Associado | None:
    cpf_digits = only_digits(cpf_cnpj)
    if not cpf_digits:
        return None

    associado = existing or Associado.objects.filter(cpf_cnpj=cpf_digits).first()
    data_geracao_date = parse_data_geracao_retorno(data_geracao)
    tipo_documento = (
        Associado.TipoDocumento.CNPJ
        if len(cpf_digits) > 11
        else Associado.TipoDocumento.CPF
    )

    if associado is None:
        return Associado.objects.create(
            matricula=build_imported_matricula(cpf_digits),
            tipo_documento=tipo_documento,
            nome_completo=nome_completo or cpf_digits,
            cpf_cnpj=cpf_digits,
            matricula_orgao=matricula_orgao or "",
            orgao_publico=orgao_publico or "",
            cargo=cargo or "",
            status=Associado.Status.IMPORTADO,
            arquivo_retorno_origem=arquivo_nome or "",
            competencia_importacao_retorno=competencia,
            data_geracao_importacao_retorno=data_geracao_date,
            ultimo_arquivo_retorno=arquivo_nome or "",
        )

    update_fields: list[str] = []
    for field_name, value in (
        ("nome_completo", nome_completo),
        ("matricula_orgao", matricula_orgao),
        ("orgao_publico", orgao_publico),
        ("cargo", cargo),
    ):
        normalized = value or ""
        if normalized and getattr(associado, field_name) != normalized:
            setattr(associado, field_name, normalized)
            update_fields.append(field_name)

    if associado.status == Associado.Status.IMPORTADO:
        if associado.ultimo_arquivo_retorno != (arquivo_nome or ""):
            associado.ultimo_arquivo_retorno = arquivo_nome or ""
            update_fields.append("ultimo_arquivo_retorno")
        if not associado.arquivo_retorno_origem and arquivo_nome:
            associado.arquivo_retorno_origem = arquivo_nome
            update_fields.append("arquivo_retorno_origem")
        if associado.competencia_importacao_retorno is None:
            associado.competencia_importacao_retorno = competencia
            update_fields.append("competencia_importacao_retorno")
        if (
            associado.data_geracao_importacao_retorno is None
            and data_geracao_date is not None
        ):
            associado.data_geracao_importacao_retorno = data_geracao_date
            update_fields.append("data_geracao_importacao_retorno")

    if update_fields:
        associado.save(update_fields=[*sorted(set(update_fields)), "updated_at"])

    return associado
