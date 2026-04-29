from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.services import ComissaoService
from apps.contratos.canonicalization import (
    get_operational_contracts_for_associado,
    is_shadow_duplicate_contract,
    resolve_operational_contract_for_associado,
)
from apps.contratos.competencia import create_cycle_with_parcelas
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.services import EsteiraService

from .factories import AssociadoFactory
from .models import AdminOverrideChange, AdminOverrideEvent, Associado, Documento
from .strategies import CadastroValidationStrategy, calculate_contract_financials


def add_months(base_date: date, months: int) -> date:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def day_of_month(month_date: date, target_day: int = 5) -> date:
    return month_date.replace(day=min(target_day, monthrange(month_date.year, month_date.month)[1]))


def calculate_contract_dates(data_aprovacao: date | None) -> tuple[date, date, date]:
    approval_date = data_aprovacao or timezone.localdate()
    mes_base = approval_date.replace(day=1)
    mes_averbacao = mes_base if approval_date.day <= 5 else add_months(mes_base, 1)
    mes_primeira_mensalidade = add_months(mes_averbacao, 1)
    primeira_mensalidade = day_of_month(mes_primeira_mensalidade)
    return approval_date, primeira_mensalidade, mes_averbacao


class AssociadoService:
    INACTIVATION_MOTIVOS = {
        "inativo": "inativo",
        "inativo_inadimplente": "inadimplente",
        "inativo_passivel_renovacao": "passível de renovação",
        "inativo_a_pedido": "a pedido do associado",
        "inativo_falecimento": "falecimento",
        "inativo_outros": "outros motivos",
    }

    """Camada de serviço para lógica de negócio de associados."""

    @staticmethod
    def _json_safe_snapshot(value):
        if isinstance(value, dict):
            return {
                str(key): AssociadoService._json_safe_snapshot(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [AssociadoService._json_safe_snapshot(item) for item in value]
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return value

    @staticmethod
    def _serialize_associado_inactivation_snapshot(
        associado: Associado,
    ) -> dict[str, object]:
        return {
            "id": associado.id,
            "matricula": associado.matricula,
            "tipo_documento": associado.tipo_documento,
            "nome_completo": associado.nome_completo,
            "cpf_cnpj": associado.cpf_cnpj,
            "rg": associado.rg,
            "orgao_expedidor": associado.orgao_expedidor,
            "email": associado.email,
            "telefone": associado.telefone,
            "data_nascimento": (
                associado.data_nascimento.isoformat()
                if associado.data_nascimento
                else None
            ),
            "profissao": associado.profissao,
            "estado_civil": associado.estado_civil,
            "orgao_publico": associado.orgao_publico,
            "matricula_orgao": associado.matricula_orgao,
            "cargo": associado.cargo,
            "status": associado.status,
            "observacao": associado.observacao,
            "agente_responsavel_id": associado.agente_responsavel_id,
            "percentual_repasse": str(associado.auxilio_taxa),
            "endereco": associado.build_endereco_payload(),
            "dados_bancarios": associado.build_dados_bancarios_payload(),
            "contato": associado.build_contato_payload(),
            "updated_at": associado.updated_at.isoformat() if associado.updated_at else None,
        }

    @staticmethod
    def _serialize_esteira_inactivation_snapshot(
        associado: Associado,
    ) -> dict[str, object]:
        esteira = getattr(associado, "esteira_item", None)
        if esteira is None:
            return {}
        return {
            "id": esteira.id,
            "etapa_atual": esteira.etapa_atual,
            "status": esteira.status,
            "prioridade": esteira.prioridade,
            "observacao": esteira.observacao,
            "assumido_em": esteira.assumido_em.isoformat() if esteira.assumido_em else None,
            "heartbeat_at": esteira.heartbeat_at.isoformat() if esteira.heartbeat_at else None,
            "concluido_em": esteira.concluido_em.isoformat() if esteira.concluido_em else None,
            "analista_responsavel_id": esteira.analista_responsavel_id,
            "coordenador_responsavel_id": esteira.coordenador_responsavel_id,
            "tesoureiro_responsavel_id": esteira.tesoureiro_responsavel_id,
            "updated_at": esteira.updated_at.isoformat() if esteira.updated_at else None,
        }

    @staticmethod
    def _record_inactivation_event(
        *,
        associado: Associado,
        user,
        previous_status: str,
        target_status: str,
        motivo: str,
        before_associado: dict[str, object],
        before_esteira: dict[str, object],
        after_associado: dict[str, object],
        after_esteira: dict[str, object],
    ) -> None:
        if not user or not getattr(user, "is_authenticated", False):
            return
        event = AdminOverrideEvent.objects.create(
            associado=associado,
            realizado_por=user,
            escopo=AdminOverrideEvent.Scope.ASSOCIADO,
            resumo="Inativação administrativa do associado",
            motivo=motivo,
            before_snapshot=AssociadoService._json_safe_snapshot(
                {
                    "meta": {
                        "action": "inativacao",
                        "previous_status": previous_status,
                        "target_status": target_status,
                    },
                    "associado": before_associado,
                    "esteira": before_esteira,
                }
            ),
            after_snapshot=AssociadoService._json_safe_snapshot(
                {
                    "meta": {
                        "action": "inativacao",
                        "previous_status": previous_status,
                        "target_status": target_status,
                    },
                    "associado": after_associado,
                    "esteira": after_esteira,
                }
            ),
            confirmacao_dupla=True,
        )
        AdminOverrideChange.objects.create(
            evento=event,
            entity_type=AdminOverrideChange.EntityType.ASSOCIADO,
            entity_id=associado.id,
            resumo="Associado inativado administrativamente",
            before_snapshot=AssociadoService._json_safe_snapshot(before_associado),
            after_snapshot=AssociadoService._json_safe_snapshot(after_associado),
        )
        if before_esteira or after_esteira:
            AdminOverrideChange.objects.create(
                evento=event,
                entity_type=AdminOverrideChange.EntityType.ESTEIRA,
                entity_id=int((after_esteira or before_esteira).get("id") or 0),
                resumo="Esteira operacional finalizada pela inativação",
                before_snapshot=AssociadoService._json_safe_snapshot(before_esteira),
                after_snapshot=AssociadoService._json_safe_snapshot(after_esteira),
            )

    @staticmethod
    def _variacao_percentual(atual: int, anterior: int) -> float:
        if anterior == 0:
            return 100.0 if atual else 0.0
        return round(((atual - anterior) / anterior) * 100, 1)

    @staticmethod
    def calcular_metricas(queryset=None):
        hoje = timezone.localdate()
        inicio_mes_atual = hoje.replace(day=1)

        if queryset is not None:
            base = queryset.distinct()
            payload = {}
            definicoes = {
                "total": Q(),
                "ativos": Q(status=Associado.Status.ATIVO),
                "em_analise": Q(status=Associado.Status.EM_ANALISE),
                "inativos": Q(status=Associado.Status.INATIVO),
                "liquidados": Q(contratos__status=Contrato.Status.ENCERRADO),
            }

            for chave, filtro in definicoes.items():
                payload[chave] = {
                    "count": base.filter(filtro).distinct().count(),
                    "variacao_percentual": 0.0,
                }
            return payload

        base = Associado.objects.all()
        anterior_base = Associado.objects.filter(created_at__lt=inicio_mes_atual)

        payload = {}
        definicoes = {
            "total": Q(),
            "ativos": Q(status=Associado.Status.ATIVO),
            "em_analise": Q(status=Associado.Status.EM_ANALISE),
            "inativos": Q(status=Associado.Status.INATIVO),
            "liquidados": Q(contratos__status=Contrato.Status.ENCERRADO),
        }

        for chave, filtro in definicoes.items():
            atual = base.filter(filtro).distinct().count()
            anterior = anterior_base.filter(filtro).distinct().count()
            payload[chave] = {
                "count": atual,
                "variacao_percentual": AssociadoService._variacao_percentual(
                    atual, anterior
                ),
            }

        return payload

    @staticmethod
    def _resolve_agente_responsavel(actor, agente_responsavel_id=None):
        agente_responsavel = actor
        if agente_responsavel_id:
            agente_responsavel = actor.__class__.objects.get(pk=agente_responsavel_id)
        return agente_responsavel

    @staticmethod
    def _resolve_percentual_repasse(
        *,
        agente_responsavel,
        percentual_repasse,
    ) -> Decimal:
        if percentual_repasse is not None:
            return Decimal(str(percentual_repasse))
        return ComissaoService.resolve_percentual(
            agente_responsavel.id if agente_responsavel else None
        )

    @staticmethod
    def _prepare_contract_financial_payload(
        contrato_data: dict,
        *,
        percentual_repasse: Decimal,
    ) -> dict:
        payload = dict(contrato_data)
        payload.update(
            calculate_contract_financials(
                mensalidade=payload.get("mensalidade"),
                prazo_meses=payload.get("prazo_meses"),
                percentual_repasse=percentual_repasse,
            )
        )
        payload["percentual_repasse"] = percentual_repasse
        return payload

    @staticmethod
    def _create_operational_contract(
        associado: Associado,
        *,
        agente_responsavel,
        contrato_data: dict,
        status: str,
        origem_operacional: str,
        create_initial_cycle: bool = True,
    ) -> Contrato:
        data_aprovacao, data_primeira_mensalidade, mes_averbacao = (
            calculate_contract_dates(contrato_data.get("data_aprovacao"))
        )
        prazo_meses = int(contrato_data.get("prazo_meses") or 3)
        valor_mensalidade = Decimal(str(contrato_data.get("mensalidade") or 0))

        contrato = Contrato.objects.create(
            associado=associado,
            agente=agente_responsavel,
            valor_bruto=contrato_data.get("valor_bruto_total", 0),
            valor_liquido=contrato_data.get("valor_liquido", 0),
            valor_mensalidade=valor_mensalidade,
            prazo_meses=prazo_meses,
            taxa_antecipacao=contrato_data.get("taxa_antecipacao", 0),
            margem_disponivel=contrato_data.get("margem_disponivel", 0),
            valor_total_antecipacao=contrato_data.get("valor_total_antecipacao", 0),
            doacao_associado=contrato_data.get("doacao_associado", Decimal("0.00")),
            comissao_agente=contrato_data.get("comissao_agente", 0),
            data_aprovacao=data_aprovacao,
            data_primeira_mensalidade=data_primeira_mensalidade,
            mes_averbacao=mes_averbacao,
            contato_web=True,
            termos_web=True,
            status=status,
            origem_operacional=origem_operacional,
        )
        if create_initial_cycle:
            create_cycle_with_parcelas(
                contrato=contrato,
                numero=1,
                competencia_inicial=data_primeira_mensalidade.replace(day=1),
                parcelas_total=prazo_meses,
                ciclo_status=Ciclo.Status.ABERTO,
                parcela_status=Parcela.Status.EM_PREVISAO,
                data_vencimento_fn=day_of_month,
                valor_mensalidade=valor_mensalidade,
                valor_total=contrato.valor_total_antecipacao,
            )
        return contrato

    @staticmethod
    def _has_prior_contract_history(associado: Associado) -> bool:
        return associado.contratos.filter(deleted_at__isnull=True).exists()

    @staticmethod
    def _has_open_operational_contract(associado: Associado) -> bool:
        return associado.contratos.filter(
            deleted_at__isnull=True,
            contrato_canonico__isnull=True,
        ).exclude(
            status__in=[Contrato.Status.CANCELADO, Contrato.Status.ENCERRADO]
        ).exists()

    @staticmethod
    def _contract_has_paid_history(contrato: Contrato) -> bool:
        if contrato.auxilio_liberado_em is not None:
            return True
        return Parcela.all_objects.filter(
            ciclo__contrato=contrato,
            deleted_at__isnull=True,
            status__in=[Parcela.Status.DESCONTADO, Parcela.Status.LIQUIDADA],
        ).exists()

    @staticmethod
    def _promote_prior_paid_contracts_to_history(associado: Associado) -> None:
        prior_contracts = (
            associado.contratos.filter(
                deleted_at__isnull=True,
                contrato_canonico__isnull=True,
            )
            .exclude(status=Contrato.Status.ENCERRADO)
            .order_by("created_at", "id")
        )
        for contrato in prior_contracts:
            if not AssociadoService._contract_has_paid_history(contrato):
                continue
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

    @staticmethod
    def _validate_reativacao_eligibility(associado: Associado) -> None:
        if associado.status != Associado.Status.INATIVO:
            raise ValidationError(
                {"detail": "A reativação só está disponível para associados inativos."}
            )
        if not AssociadoService._has_prior_contract_history(associado):
            raise ValidationError(
                {
                    "detail": (
                        "A reativação exige histórico anterior de contrato para este associado."
                    )
                }
            )
        if AssociadoService._has_open_operational_contract(associado):
            raise ValidationError(
                {
                    "detail": (
                        "Já existe um contrato operacional em andamento para este associado."
                    )
                }
            )

    @staticmethod
    @transaction.atomic
    def criar_associado_completo(validated_data, agente):
        dados = CadastroValidationStrategy().validate(validated_data)

        endereco_data = dados.pop("endereco")
        dados_bancarios_data = dados.pop("dados_bancarios")
        contato_data = dados.pop("contato")
        documentos_payload = dados.pop("documentos_payload", [])
        contrato_data = dados.pop("contrato")
        agente_responsavel_id = dados.pop("agente_responsavel_id", None)
        agente_responsavel = AssociadoService._resolve_agente_responsavel(
            agente,
            agente_responsavel_id,
        )
        percentual_repasse = AssociadoService._resolve_percentual_repasse(
            agente_responsavel=agente_responsavel,
            percentual_repasse=contrato_data.get("percentual_repasse"),
        )
        contrato_data = AssociadoService._prepare_contract_financial_payload(
            contrato_data,
            percentual_repasse=percentual_repasse,
        )

        associado_data = {
            "cpf_cnpj": dados["cpf_cnpj"],
            "nome_completo": dados["nome_completo"],
            "rg": dados.get("rg", ""),
            "orgao_expedidor": dados.get("orgao_expedidor", ""),
            "data_nascimento": dados.get("data_nascimento"),
            "profissao": dados.get("profissao", ""),
            "estado_civil": dados.get("estado_civil", ""),
            "cep": endereco_data.get("cep", ""),
            "logradouro": endereco_data.get("logradouro", ""),
            "numero": endereco_data.get("numero", ""),
            "complemento": endereco_data.get("complemento", ""),
            "bairro": endereco_data.get("bairro", ""),
            "cidade": endereco_data.get("cidade", ""),
            "uf": endereco_data.get("uf", ""),
            "email": contato_data.get("email", ""),
            "telefone": contato_data.get("celular", ""),
            "orgao_publico": contato_data.get("orgao_publico", ""),
            "matricula_orgao": contato_data.get("matricula_servidor", ""),
            "situacao_servidor": contato_data.get("situacao_servidor", ""),
            "banco": dados_bancarios_data.get("banco", ""),
            "agencia": dados_bancarios_data.get("agencia", ""),
            "conta": dados_bancarios_data.get("conta", ""),
            "tipo_conta": dados_bancarios_data.get("tipo_conta", ""),
            "chave_pix": dados_bancarios_data.get("chave_pix", ""),
            "cargo": dados.get("cargo", "") or dados.get("profissao", ""),
            "observacao": dados.get("observacao", ""),
            "auxilio_taxa": percentual_repasse,
        }

        if dados["tipo_documento"] == Associado.TipoDocumento.CNPJ:
            associado = AssociadoFactory.criar_pessoa_juridica(
                associado_data, agente_responsavel
            )
        else:
            associado = AssociadoFactory.criar_pessoa_fisica(
                associado_data, agente_responsavel
            )

        AssociadoService._create_operational_contract(
            associado,
            agente_responsavel=agente_responsavel,
            contrato_data=contrato_data,
            status=Contrato.Status.EM_ANALISE,
            origem_operacional=Contrato.OrigemOperacional.CADASTRO,
        )

        EsteiraService.garantir_item_inicial_cadastro(
            associado,
            agente,
        )

        for documento in documentos_payload:
            Documento.objects.create(
                associado=associado,
                tipo=documento["tipo"],
                arquivo=documento["arquivo"],
                observacao=documento.get("observacao", ""),
            )

        return associado

    @staticmethod
    @transaction.atomic
    def inativar_associado(
        associado: Associado,
        user=None,
        *,
        status_destino: str | None = None,
    ) -> Associado:
        motivo_key = str(status_destino or "inativo").strip()
        label = AssociadoService.INACTIVATION_MOTIVOS.get(motivo_key)
        if label is None:
            raise ValidationError(
                {
                    "status_destino": [
                        "Escolha um motivo válido: "
                        + ", ".join(AssociadoService.INACTIVATION_MOTIVOS.keys())
                    ]
                }
            )
        target_status = Associado.Status.INATIVO
        previous_status = associado.status
        before_associado = AssociadoService._serialize_associado_inactivation_snapshot(
            associado
        )
        before_esteira = AssociadoService._serialize_esteira_inactivation_snapshot(
            associado
        )
        motivo = (
            f"Associado inativado como {label}; fila operacional residual finalizada."
        )
        EsteiraService.normalizar_inativacao_associado(
            associado,
            user,
            observacao=motivo,
        )
        associado.status = target_status
        associado.save(update_fields=["status", "updated_at"])
        after_associado = AssociadoService._serialize_associado_inactivation_snapshot(
            associado
        )
        after_esteira = AssociadoService._serialize_esteira_inactivation_snapshot(
            associado
        )
        AssociadoService._record_inactivation_event(
            associado=associado,
            user=user,
            previous_status=previous_status,
            target_status=target_status,
            motivo=motivo,
            before_associado=before_associado,
            before_esteira=before_esteira,
            after_associado=after_associado,
            after_esteira=after_esteira,
        )
        return associado

    @staticmethod
    @transaction.atomic
    def reativar_associado(associado: Associado, validated_data, user) -> Associado:
        AssociadoService._validate_reativacao_eligibility(associado)
        AssociadoService._promote_prior_paid_contracts_to_history(associado)

        contrato_data = dict(validated_data.get("contrato") or {})
        agente_responsavel = AssociadoService._resolve_agente_responsavel(
            user,
            validated_data.get("agente_responsavel_id"),
        )
        percentual_repasse = AssociadoService._resolve_percentual_repasse(
            agente_responsavel=agente_responsavel,
            percentual_repasse=contrato_data.get("percentual_repasse"),
        )
        contrato_data = AssociadoService._prepare_contract_financial_payload(
            contrato_data,
            percentual_repasse=percentual_repasse,
        )

        associado.agente_responsavel = agente_responsavel
        associado.auxilio_taxa = percentual_repasse
        associado.status = Associado.Status.EM_ANALISE
        associado.save(
            update_fields=[
                "agente_responsavel",
                "auxilio_taxa",
                "status",
                "updated_at",
            ]
        )

        contrato = AssociadoService._create_operational_contract(
            associado,
            agente_responsavel=agente_responsavel,
            contrato_data=contrato_data,
            status=Contrato.Status.EM_ANALISE,
            origem_operacional=Contrato.OrigemOperacional.REATIVACAO,
            create_initial_cycle=False,
        )
        EsteiraService.enviar_reativacao_para_analise(
            associado,
            user,
            observacao=(
                "Reativação enviada para análise. "
                f"Novo contrato {contrato.codigo} criado."
            ),
        )
        associado.refresh_from_db()
        return associado

    @staticmethod
    @transaction.atomic
    def excluir_associado(associado: Associado, user=None) -> None:
        from apps.contratos.soft_delete import soft_delete_contract_tree

        esteira_item = associado._safe_related("esteira_item")
        if (
            esteira_item is not None
            and user is not None
            and getattr(user, "is_authenticated", False)
            and hasattr(user, "has_role")
            and user.has_role("ADMIN", "COORDENADOR")
        ):
            EsteiraService.excluir_solicitacao(esteira_item, user)
            if associado.deleted_at is not None:
                return
            return

        if esteira_item is not None:
            for pendencia in esteira_item.pendencias.filter(deleted_at__isnull=True):
                pendencia.soft_delete()
            for transicao in esteira_item.transicoes.filter(deleted_at__isnull=True):
                transicao.soft_delete()
            esteira_item.soft_delete()

        for documento in associado.documentos.filter(deleted_at__isnull=True):
            documento.soft_delete()
        for issue in associado.doc_issues.filter(deleted_at__isnull=True):
            issue.soft_delete()
        for reupload in associado.doc_reuploads.filter(deleted_at__isnull=True):
            reupload.soft_delete()

        for contrato in associado.contratos.filter(deleted_at__isnull=True).order_by("id"):
            soft_delete_contract_tree(contrato)

        for pagamento in associado.tesouraria_pagamentos.filter(deleted_at__isnull=True):
            for notificacao in pagamento.notificacoes.filter(deleted_at__isnull=True):
                notificacao.soft_delete()
            pagamento.soft_delete()

        for relation in ("endereco", "dados_bancarios", "contato_historico"):
            related = associado._safe_related(relation)
            if related is not None and related.deleted_at is None:
                related.soft_delete()

        associado.soft_delete()

    @staticmethod
    def buscar_com_contagens(queryset):
        return queryset

    @staticmethod
    def get_detail_visible_contracts_for_associado(associado: Associado) -> list[Contrato]:
        contratos = get_operational_contracts_for_associado(associado)
        if contratos or associado.status != Associado.Status.INATIVO:
            return contratos

        cached = getattr(associado, "_prefetched_objects_cache", {}).get("contratos")
        historicos: list[Contrato] = []
        if cached is not None:
            historicos = [
                contrato
                for contrato in cached
                if contrato.deleted_at is None and contrato.contrato_canonico_id is None
            ]
        if cached is None or not historicos:
            historicos = list(
                Contrato.objects.filter(
                    associado=associado,
                    deleted_at__isnull=True,
                    contrato_canonico__isnull=True,
                )
                .select_related("agente")
                .prefetch_related("ciclos__parcelas")
                .order_by("-created_at", "-id")
            )
        return sorted(
            historicos,
            key=lambda contrato: (contrato.created_at, contrato.id),
            reverse=True,
        )

    @staticmethod
    def resolve_report_like_contract_for_associado(associado: Associado) -> Contrato | None:
        contrato = resolve_operational_contract_for_associado(associado)
        if contrato is not None:
            return contrato

        cached_contracts = getattr(associado, "_prefetched_objects_cache", {}).get("contratos")
        if cached_contracts is not None:
            contratos = list(cached_contracts)
        else:
            contratos = []
        if cached_contracts is None or not contratos:
            contratos = list(
                associado.contratos.select_related("agente")
                .prefetch_related("ciclos__parcelas")
                .order_by("-created_at", "-id")
            )

        contratos_visiveis = [
            item
            for item in contratos
            if item.deleted_at is None and not is_shadow_duplicate_contract(item)
        ]
        if not contratos_visiveis:
            return None
        return max(contratos_visiveis, key=lambda item: (item.created_at, item.id))

    @staticmethod
    def count_paid_parcelas_for_contract(contrato: Contrato) -> int:
        paid_statuses = {Parcela.Status.DESCONTADO, Parcela.Status.LIQUIDADA}
        prefetched_cycles = getattr(contrato, "_prefetched_objects_cache", {}).get("ciclos")
        if prefetched_cycles is not None:
            total = 0
            for ciclo in prefetched_cycles:
                prefetched_parcelas = getattr(ciclo, "_prefetched_objects_cache", {}).get(
                    "parcelas"
                )
                if prefetched_parcelas is None:
                    break
                total += sum(
                    1 for parcela in prefetched_parcelas if parcela.status in paid_statuses
                )
            else:
                return total

        return Parcela.objects.filter(
            ciclo__contrato=contrato,
            status__in=paid_statuses,
        ).count()

    @staticmethod
    def contar_ciclos_logicos(associado: Associado) -> dict[str, int]:
        contratos = AssociadoService.get_detail_visible_contracts_for_associado(associado)
        logical_cycles = []
        for contrato in contratos:
            logical_cycles.extend(build_contract_cycle_projection(contrato)["cycles"])
        return {
            "ciclos_abertos": sum(
                1
                for cycle in logical_cycles
                if cycle["status"]
                in [
                    Ciclo.Status.FUTURO,
                    Ciclo.Status.ABERTO,
                    Ciclo.Status.APTO_A_RENOVAR,
                ]
            ),
            "ciclos_fechados": sum(
                1
                for cycle in logical_cycles
                if cycle["status"]
                in [Ciclo.Status.CICLO_RENOVADO, Ciclo.Status.FECHADO]
            ),
        }

    @staticmethod
    def total_ciclos_logicos(associado: Associado) -> int:
        contagens = AssociadoService.contar_ciclos_logicos(associado)
        return contagens["ciclos_abertos"] + contagens["ciclos_fechados"]

    @staticmethod
    def associado_eh_renovado(associado: Associado) -> bool:
        contratos = AssociadoService.get_detail_visible_contracts_for_associado(associado)
        for contrato in contratos:
            projection = build_contract_cycle_projection(contrato)
            if projection.get("refinanciamento_id"):
                return True
            if len(projection.get("cycles", [])) > 1:
                return True
        return False
