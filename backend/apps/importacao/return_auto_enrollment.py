from __future__ import annotations

from datetime import date
from decimal import Decimal
from hashlib import sha1

from apps.associados.models import Associado, only_digits
from apps.contratos.canonicalization import resolve_operational_contract_for_associado
from apps.contratos.competencia import add_months, sync_competencia_locks_for_references
from apps.contratos.models import Ciclo, Contrato, Parcela

from .imported_associados import parse_data_geracao_retorno, upsert_imported_associado_from_retorno
from .matching import normalize_matricula

SYNTHETIC_RETURN_CONTRACT_PREFIX = "RETIMP"
SYNTHETIC_RETURN_CONTRACT_PARCELAS = 3


def is_synthetic_return_contract_code(value: str | None) -> bool:
    return (value or "").startswith(f"{SYNTHETIC_RETURN_CONTRACT_PREFIX}-")


def build_synthetic_return_contract_code(
    *,
    cpf_cnpj: str,
    competencia: date,
    matricula: str = "",
) -> str:
    cpf_digits = only_digits(cpf_cnpj)
    matricula_norm = normalize_matricula(matricula) or "SEM-MATRICULA"
    digest = sha1(
        f"{cpf_digits}|{competencia.isoformat()}|{matricula_norm}".encode("utf-8")
    ).hexdigest()[:10].upper()
    matricula_slug = matricula_norm[:12]
    return (
        f"{SYNTHETIC_RETURN_CONTRACT_PREFIX}-{competencia.strftime('%Y%m')}-"
        f"{matricula_slug}-{digest}"
    )[:40]


def build_payment_identity(
    *,
    cpf_cnpj: str,
    referencia_month: date,
    matricula: str = "",
) -> tuple[str, date, str]:
    return (
        only_digits(cpf_cnpj),
        referencia_month,
        normalize_matricula(matricula),
    )


def should_align_parcela_value_from_return(
    *,
    parcela: Parcela | None,
    return_value: Decimal | None,
) -> bool:
    if parcela is None or getattr(parcela, "pk", None) is None or return_value is None:
        return False

    normalized_return = Decimal(str(return_value))
    if normalized_return <= 0 or parcela.valor == normalized_return:
        return False

    contrato_valor = (
        getattr(getattr(parcela.ciclo, "contrato", None), "valor_mensalidade", None)
        or Decimal("0.00")
    )
    if contrato_valor != normalized_return:
        return False

    conflict_exists = (
        Parcela.all_objects.filter(
            associado_id=parcela.associado_id,
            referencia_mes=parcela.referencia_mes,
            valor=normalized_return,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .exclude(pk=parcela.pk)
        .exists()
    )
    return not conflict_exists


def resolve_or_create_imported_associado(
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
) -> tuple[Associado | None, bool]:
    associado = upsert_imported_associado_from_retorno(
        arquivo_nome=arquivo_nome,
        competencia=competencia,
        data_geracao=data_geracao,
        cpf_cnpj=cpf_cnpj,
        nome_completo=nome_completo,
        matricula_orgao=matricula_orgao,
        orgao_publico=orgao_publico,
        cargo=cargo,
        existing=existing,
    )
    return associado, existing is None and associado is not None


def ensure_return_parcela(
    *,
    associado: Associado,
    competencia: date,
    arquivo_nome: str,
    data_geracao: str | date | None,
    cpf_cnpj: str,
    matricula: str,
    valor: Decimal,
) -> tuple[Parcela | None, bool]:
    existing = _find_existing_parcela(
        associado=associado,
        competencia=competencia,
        cpf_cnpj=cpf_cnpj,
        matricula=matricula,
    )
    if existing is not None:
        return existing, False
    if resolve_operational_contract_for_associado(associado) is not None:
        return None, False

    # O fluxo principal de retorno já opera por PagamentoMensalidade/projeção
    # quando não existe parcela materializada. Não voltamos a criar RETIMP.
    return None, False


def _find_existing_parcela(
    *,
    associado: Associado,
    competencia: date,
    cpf_cnpj: str,
    matricula: str,
) -> Parcela | None:
    synthetic_code = build_synthetic_return_contract_code(
        cpf_cnpj=cpf_cnpj,
        competencia=competencia,
        matricula=matricula,
    )
    synthetic = (
        Parcela.all_objects.filter(
            ciclo__contrato__codigo=synthetic_code,
            referencia_mes=competencia,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .select_related("ciclo", "ciclo__contrato")
        .first()
    )
    if synthetic is not None:
        return synthetic

    candidates = list(
        Parcela.all_objects.filter(
            associado=associado,
            referencia_mes=competencia,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .select_related("ciclo", "ciclo__contrato")
        .order_by(
            "-ciclo__contrato__data_aprovacao",
            "-ciclo__contrato__created_at",
            "-ciclo__numero",
            "numero",
            "-id",
        )
    )
    non_synthetic = [
        parcela
        for parcela in candidates
        if not is_synthetic_return_contract_code(parcela.ciclo.contrato.codigo)
    ]
    if len(non_synthetic) == 1:
        return non_synthetic[0]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _ensure_synthetic_contract(
    *,
    associado: Associado,
    competencia: date,
    arquivo_nome: str,
    data_geracao: str | date | None,
    cpf_cnpj: str,
    matricula: str,
    valor: Decimal,
) -> Contrato:
    codigo = build_synthetic_return_contract_code(
        cpf_cnpj=cpf_cnpj,
        competencia=competencia,
        matricula=matricula,
    )
    contrato = Contrato.all_objects.filter(codigo=codigo).first()
    if contrato is not None:
        if contrato.deleted_at is not None:
            contrato.restore()
        _ensure_synthetic_cycle_for_competencia(
            contrato=contrato,
            competencia=competencia,
            valor_mensalidade=valor if valor > 0 else Decimal("30.00"),
            parcelas_total=SYNTHETIC_RETURN_CONTRACT_PARCELAS,
            arquivo_nome=arquivo_nome,
        )
        return contrato

    data_base = parse_data_geracao_retorno(data_geracao) or competencia
    valor_mensalidade = valor if valor > 0 else Decimal("30.00")
    prazo_meses = SYNTHETIC_RETURN_CONTRACT_PARCELAS
    valor_total = (valor_mensalidade * Decimal(str(prazo_meses))).quantize(Decimal("0.01"))

    contrato = Contrato.objects.create(
        associado=associado,
        agente=associado.agente_responsavel,
        codigo=codigo,
        valor_bruto=valor_total,
        valor_liquido=valor_total,
        valor_mensalidade=valor_mensalidade,
        prazo_meses=prazo_meses,
        taxa_antecipacao=Decimal("0.00"),
        margem_disponivel=valor_mensalidade,
        valor_total_antecipacao=valor_total,
        doacao_associado=Decimal("0.00"),
        status=Contrato.Status.ATIVO,
        data_contrato=data_base,
        data_aprovacao=data_base,
        data_primeira_mensalidade=competencia,
        mes_averbacao=competencia,
        contato_web=False,
        termos_web=False,
    )
    _ensure_synthetic_cycle_for_competencia(
        contrato=contrato,
        competencia=competencia,
        valor_mensalidade=valor_mensalidade,
        parcelas_total=prazo_meses,
        arquivo_nome=arquivo_nome,
    )
    return contrato


def _ensure_synthetic_cycle_for_competencia(
    *,
    contrato: Contrato,
    competencia: date,
    valor_mensalidade: Decimal,
    parcelas_total: int,
    arquivo_nome: str,
) -> Ciclo:
    existing_cycle = (
        Ciclo.objects.filter(
            contrato=contrato,
            parcelas__referencia_mes=competencia,
            parcelas__deleted_at__isnull=True,
        )
        .exclude(parcelas__status=Parcela.Status.CANCELADO)
        .order_by("-numero", "-id")
        .first()
    )
    if existing_cycle is not None:
        return existing_cycle

    referencias = [add_months(competencia, index) for index in range(parcelas_total)]
    next_cycle_number = (
        contrato.ciclos.order_by("-numero").values_list("numero", flat=True).first() or 0
    ) + 1
    ciclo = Ciclo.objects.create(
        contrato=contrato,
        numero=next_cycle_number,
        data_inicio=competencia,
        data_fim=referencias[-1],
        status=Ciclo.Status.ABERTO,
        valor_total=(valor_mensalidade * Decimal(str(parcelas_total))).quantize(
            Decimal("0.01")
        ),
    )
    parcelas = [
        Parcela(
            ciclo=ciclo,
            associado=contrato.associado,
            numero=index + 1,
            referencia_mes=referencia,
            valor=valor_mensalidade,
            data_vencimento=referencia,
            status=(
                Parcela.Status.EM_ABERTO if index == 0 else Parcela.Status.FUTURO
            ),
            observacao=(
                f"Parcela sintética criada via arquivo retorno {arquivo_nome}."
                if index == 0
                else f"Parcela futura criada automaticamente via arquivo retorno {arquivo_nome}."
            ),
        )
        for index, referencia in enumerate(referencias)
    ]
    Parcela.objects.bulk_create(parcelas)
    sync_competencia_locks_for_references(
        associado_id=contrato.associado_id,
        referencias=referencias,
    )
    return ciclo
