from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.associados.models import Associado
from apps.contratos.competencia import (
    create_cycle_with_parcelas,
    list_month_references,
    sync_competencia_locks_for_references,
)
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    invalidate_operational_apt_queue_cache,
    resolve_associado_mother_status,
)
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.services import TesourariaService


def _digits(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _format_cpf(digits: str) -> str:
    if len(digits) != 11:
        return digits
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def _parse_cycle_start(value: str | None) -> date | None:
    if not value:
        return None
    normalized = value.strip()
    if len(normalized) == 7:
        normalized = f"{normalized}-01"
    return date.fromisoformat(normalized).replace(day=1)


def _day_of_month(month_date: date, target_day: int = 5) -> date:
    return month_date.replace(day=min(target_day, 28))


class Command(BaseCommand):
    help = (
        "Corrige reativacao paga que ficou como apta/cancelada, "
        "preservando comprovantes e recriando o ciclo operacional correto."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--cpf",
            default="025.000.113-64",
            help="CPF do associado. Padrao: Jarlene Maria Ribeiro Rodrigues.",
        )
        parser.add_argument(
            "--contract-id",
            type=int,
            default=None,
            help="ID do contrato de reativacao pago. Opcional.",
        )
        parser.add_argument(
            "--contract-code",
            default="",
            help="Codigo do contrato de reativacao pago. Opcional.",
        )
        parser.add_argument(
            "--cycle-start",
            default=None,
            help=(
                "Competencia inicial do novo ciclo, em YYYY-MM ou YYYY-MM-DD. "
                "Se omitido, usa o mes do pagamento/auxilio_liberado_em."
            ),
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=None,
            help="Usuario para registrar pagamento/transicao. Opcional.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica as alteracoes. Sem esta flag, executa somente dry-run.",
        )

    def handle(self, *args, **options):
        associado = self._get_associado(options["cpf"])
        contrato = self._get_reactivation_contract(
            associado,
            contract_id=options.get("contract_id"),
            contract_code=options.get("contract_code") or "",
        )
        user = self._get_user(options.get("user_id"))
        paid_at = self._resolve_paid_at(contrato)
        cycle_start = _parse_cycle_start(options.get("cycle_start")) or paid_at.date().replace(day=1)
        referencias = list_month_references(
            cycle_start,
            int(contrato.prazo_meses or 3),
        )
        execute = bool(options["apply"])

        before_status = resolve_associado_mother_status(associado)
        before_projection = build_contract_cycle_projection(contrato)
        old_contracts = self._paid_prior_contracts(associado, contrato)
        active_cycles = list(
            contrato.ciclos.filter(deleted_at__isnull=True)
            .prefetch_related("parcelas")
            .order_by("numero", "id")
        )
        active_refis = list(self._open_apto_refinanciamentos(contrato))
        comprovantes = list(
            Comprovante.objects.filter(
                contrato=contrato,
                refinanciamento__isnull=True,
                deleted_at__isnull=True,
            ).order_by("created_at", "id")
        )

        self._print_plan(
            associado=associado,
            contrato=contrato,
            old_contracts=old_contracts,
            active_cycles=active_cycles,
            active_refis=active_refis,
            comprovantes=comprovantes,
            paid_at=paid_at,
            referencias=referencias,
            before_status=before_status,
            before_projection=before_projection,
            execute=execute,
        )

        if not execute:
            self.stdout.write(
                self.style.WARNING("Dry-run concluido. Rode novamente com --apply para aplicar.")
            )
            return

        with transaction.atomic():
            for old_contract in old_contracts:
                self._mark_prior_contract_as_paid_history(old_contract)

            cycle = self._ensure_reactivation_cycle(
                contrato,
                referencias=referencias,
            )
            self._mark_reactivation_as_paid(
                associado=associado,
                contrato=contrato,
                cycle=cycle,
                paid_at=paid_at,
                user=user,
            )
            self._clear_open_apto_refinanciamentos(contrato)

        invalidate_operational_apt_queue_cache()
        associado.refresh_from_db()
        contrato.refresh_from_db()
        after_status = resolve_associado_mother_status(associado)
        after_projection = build_contract_cycle_projection(contrato)

        self.stdout.write(self.style.SUCCESS("Correcao aplicada."))
        self.stdout.write(
            f"associado={associado.id} status_db={associado.status} status_resolvido={after_status}"
        )
        self.stdout.write(
            f"contrato_reativacao={contrato.id} {contrato.codigo} "
            f"status={contrato.status} auxilio_liberado_em={contrato.auxilio_liberado_em}"
        )
        self.stdout.write(
            "status_renovacao_reativacao="
            f"{after_projection.get('status_renovacao') or ''}"
        )
        if after_status != Associado.Status.ATIVO:
            self.stdout.write(
                self.style.WARNING(
                    "Atencao: status resolvido ainda nao ficou ativo. "
                    "Verifique filas/refinanciamentos abertos para este associado."
                )
            )

    def _get_associado(self, cpf: str) -> Associado:
        cpf_digits = _digits(cpf)
        candidates = [cpf, cpf_digits, _format_cpf(cpf_digits)]
        associado = Associado.objects.filter(cpf_cnpj__in=candidates).first()
        if associado is None:
            raise CommandError(f"Associado nao encontrado para CPF {cpf}.")
        return associado

    def _get_reactivation_contract(
        self,
        associado: Associado,
        *,
        contract_id: int | None,
        contract_code: str,
    ) -> Contrato:
        queryset = associado.contratos.filter(
            deleted_at__isnull=True,
            contrato_canonico__isnull=True,
        )
        if contract_id:
            queryset = queryset.filter(id=contract_id)
        if contract_code:
            queryset = queryset.filter(codigo=contract_code.strip())

        reactivation = (
            queryset.filter(origem_operacional=Contrato.OrigemOperacional.REATIVACAO)
            .order_by("-auxilio_liberado_em", "-created_at", "-id")
            .first()
        )
        if reactivation is not None:
            return reactivation
        if contract_id or contract_code:
            fallback = queryset.order_by("-created_at", "-id").first()
            if fallback is not None:
                return fallback
        raise CommandError(
            "Contrato de reativacao nao encontrado. Informe --contract-id ou --contract-code."
        )

    def _get_user(self, user_id: int | None):
        User = get_user_model()
        if user_id:
            user = User.objects.filter(id=user_id, is_active=True).first()
            if user is None:
                raise CommandError(f"Usuario ativo nao encontrado: {user_id}.")
            return user
        user = User.objects.filter(is_superuser=True, is_active=True).order_by("id").first()
        if user is None:
            user = User.objects.filter(is_active=True).order_by("id").first()
        if user is None:
            raise CommandError("Nenhum usuario ativo encontrado para registrar a correcao.")
        return user

    def _resolve_paid_at(self, contrato: Contrato):
        comprovante = (
            Comprovante.objects.filter(
                contrato=contrato,
                refinanciamento__isnull=True,
                deleted_at__isnull=True,
                data_pagamento__isnull=False,
            )
            .order_by("-data_pagamento", "-created_at", "-id")
            .first()
        )
        if comprovante is not None:
            return comprovante.data_pagamento
        if contrato.auxilio_liberado_em is not None:
            return timezone.make_aware(
                datetime.combine(contrato.auxilio_liberado_em, time(12, 0))
            )
        return timezone.now()

    def _paid_prior_contracts(
        self,
        associado: Associado,
        reactivation_contract: Contrato,
    ) -> list[Contrato]:
        contracts = (
            associado.contratos.filter(
                deleted_at__isnull=True,
                contrato_canonico__isnull=True,
            )
            .exclude(pk=reactivation_contract.pk)
            .order_by("created_at", "id")
        )
        return [
            contrato
            for contrato in contracts
            if contrato.auxilio_liberado_em is not None
            or Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
                status__in=[Parcela.Status.DESCONTADO, Parcela.Status.LIQUIDADA],
            ).exists()
        ]

    def _open_apto_refinanciamentos(self, contrato: Contrato):
        return Refinanciamento.objects.filter(
            associado=contrato.associado,
            contrato_origem=contrato,
            deleted_at__isnull=True,
            origem=Refinanciamento.Origem.OPERACIONAL,
            executado_em__isnull=True,
            data_ativacao_ciclo__isnull=True,
            ciclo_destino__isnull=True,
            status__in=[
                Refinanciamento.Status.APTO_A_RENOVAR,
                Refinanciamento.Status.PENDENTE_APTO,
            ],
        ).order_by("id")

    def _cycle_matches(self, ciclo: Ciclo, referencias: list[date]) -> bool:
        current = list(
            ciclo.parcelas.filter(deleted_at__isnull=True)
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("referencia_mes", "id")
            .values_list("referencia_mes", flat=True)
        )
        return current == referencias

    def _ensure_reactivation_cycle(
        self,
        contrato: Contrato,
        *,
        referencias: list[date],
    ) -> Ciclo:
        active_cycles = list(
            contrato.ciclos.filter(deleted_at__isnull=True)
            .prefetch_related("parcelas")
            .order_by("numero", "id")
        )
        if len(active_cycles) == 1 and self._cycle_matches(active_cycles[0], referencias):
            ciclo = active_cycles[0]
            if ciclo.status != Ciclo.Status.ABERTO:
                ciclo.status = Ciclo.Status.ABERTO
                ciclo.save(update_fields=["status", "updated_at"])
            return ciclo

        old_refs = set(
            Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
            ).values_list("referencia_mes", flat=True)
        )
        for parcela in Parcela.all_objects.filter(
            ciclo__contrato=contrato,
            deleted_at__isnull=True,
        ).order_by("id"):
            parcela.soft_delete()
        for ciclo in active_cycles:
            ciclo.soft_delete()

        ciclo, _parcelas = create_cycle_with_parcelas(
            contrato=contrato,
            numero=1,
            competencia_inicial=referencias[0],
            parcelas_total=len(referencias),
            ciclo_status=Ciclo.Status.ABERTO,
            parcela_status=Parcela.Status.EM_PREVISAO,
            data_vencimento_fn=_day_of_month,
            valor_mensalidade=contrato.valor_mensalidade,
            valor_total=(
                contrato.valor_total_antecipacao
                or Decimal(str(contrato.valor_mensalidade or 0)) * len(referencias)
            ),
        )
        sync_competencia_locks_for_references(
            associado_id=contrato.associado_id,
            referencias=sorted(old_refs.union(referencias)),
        )
        return ciclo

    def _mark_prior_contract_as_paid_history(self, contrato: Contrato) -> None:
        contrato.status = Contrato.Status.ENCERRADO
        contrato.cancelamento_tipo = ""
        contrato.cancelamento_motivo = ""
        contrato.cancelado_em = None
        contrato.save(
            update_fields=[
                "status",
                "cancelamento_tipo",
                "cancelamento_motivo",
                "cancelado_em",
                "updated_at",
            ]
        )
        for ciclo in contrato.ciclos.filter(deleted_at__isnull=True):
            if ciclo.status in {Ciclo.Status.APTO_A_RENOVAR, Ciclo.Status.PENDENCIA}:
                ciclo.status = Ciclo.Status.FECHADO
                ciclo.save(update_fields=["status", "updated_at"])

    def _mark_reactivation_as_paid(
        self,
        *,
        associado: Associado,
        contrato: Contrato,
        cycle: Ciclo,
        paid_at,
        user,
    ) -> None:
        contrato.status = Contrato.Status.ATIVO
        contrato.auxilio_liberado_em = paid_at.date()
        if not contrato.data_aprovacao:
            contrato.data_aprovacao = paid_at.date()
        contrato.cancelamento_tipo = ""
        contrato.cancelamento_motivo = ""
        contrato.cancelado_em = None
        contrato.save(
            update_fields=[
                "status",
                "auxilio_liberado_em",
                "data_aprovacao",
                "cancelamento_tipo",
                "cancelamento_motivo",
                "cancelado_em",
                "updated_at",
            ]
        )

        Comprovante.objects.filter(
            contrato=contrato,
            refinanciamento__isnull=True,
            deleted_at__isnull=True,
            tipo__in=[
                Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
                Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
            ],
        ).update(ciclo=cycle, updated_at=timezone.now())

        for comprovante in Comprovante.objects.filter(
            contrato=contrato,
            refinanciamento__isnull=True,
            deleted_at__isnull=True,
            data_pagamento__isnull=True,
        ):
            comprovante.data_pagamento = paid_at
            comprovante.save(update_fields=["data_pagamento", "updated_at"])

        TesourariaService._upsert_initial_payment(
            contrato,
            user=user,
            paid_at=paid_at,
        )

        associado.status = Associado.Status.ATIVO
        associado.save(update_fields=["status", "updated_at"])

        esteira = getattr(associado, "esteira_item", None)
        if esteira is not None:
            esteira.etapa_atual = esteira.Etapa.CONCLUIDO
            esteira.status = esteira.Situacao.APROVADO
            esteira.tesoureiro_responsavel = user
            esteira.concluido_em = paid_at
            esteira.save(
                update_fields=[
                    "etapa_atual",
                    "status",
                    "tesoureiro_responsavel",
                    "concluido_em",
                    "updated_at",
                ]
            )
            if not esteira.transicoes.filter(acao="repair_paid_reactivation").exists():
                esteira.transicoes.create(
                    acao="repair_paid_reactivation",
                    de_status=esteira.Etapa.TESOURARIA,
                    para_status=esteira.Etapa.CONCLUIDO,
                    de_situacao=esteira.Situacao.AGUARDANDO,
                    para_situacao=esteira.Situacao.APROVADO,
                    realizado_por=user,
                    observacao="Reativacao paga corrigida por comando administrativo.",
                )

    def _clear_open_apto_refinanciamentos(self, contrato: Contrato) -> None:
        for refinanciamento in self._open_apto_refinanciamentos(contrato):
            refinanciamento.status = Refinanciamento.Status.REVERTIDO
            refinanciamento.observacao = (
                (refinanciamento.observacao or "").strip()
                + "\nFila apta removida por correcao de reativacao paga."
            ).strip()
            refinanciamento.save(update_fields=["status", "observacao", "updated_at"])

    def _print_plan(
        self,
        *,
        associado: Associado,
        contrato: Contrato,
        old_contracts: list[Contrato],
        active_cycles: list[Ciclo],
        active_refis: list[Refinanciamento],
        comprovantes: list[Comprovante],
        paid_at,
        referencias: list[date],
        before_status: str,
        before_projection: dict[str, object],
        execute: bool,
    ) -> None:
        mode = "APPLY" if execute else "DRY-RUN"
        self.stdout.write(self.style.WARNING(f"Modo: {mode}"))
        self.stdout.write(
            f"associado={associado.id} nome={associado.nome_completo} "
            f"cpf={associado.cpf_cnpj} status_db={associado.status} "
            f"status_resolvido={before_status}"
        )
        self.stdout.write(
            f"contrato_reativacao={contrato.id} {contrato.codigo} "
            f"status={contrato.status} origem={contrato.origem_operacional} "
            f"auxilio_liberado_em={contrato.auxilio_liberado_em}"
        )
        self.stdout.write(
            "status_renovacao_atual="
            f"{before_projection.get('status_renovacao') or ''}"
        )
        self.stdout.write(f"paid_at={paid_at.isoformat()}")
        self.stdout.write(
            "novo_ciclo="
            + ", ".join(referencia.isoformat() for referencia in referencias)
        )
        self.stdout.write(
            "contratos_antigos_para_historico="
            + (
                ", ".join(
                    f"{item.id}:{item.codigo}:{item.status}" for item in old_contracts
                )
                if old_contracts
                else "nenhum"
            )
        )
        self.stdout.write(
            "ciclos_ativos_reativacao="
            + (
                ", ".join(
                    f"{item.id}:ciclo{item.numero}:{item.status}" for item in active_cycles
                )
                if active_cycles
                else "nenhum"
            )
        )
        self.stdout.write(
            "refinanciamentos_aptos_abertos="
            + (
                ", ".join(f"{item.id}:{item.status}" for item in active_refis)
                if active_refis
                else "nenhum"
            )
        )
        self.stdout.write(
            "comprovantes_preservados="
            + (
                ", ".join(
                    f"{item.id}:{item.papel}:{item.nome_original}" for item in comprovantes
                )
                if comprovantes
                else "nenhum"
            )
        )
