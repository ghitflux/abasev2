from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.services import ComissaoService
from apps.contratos.canonicalization import get_operational_contracts_for_associado
from apps.contratos.competencia import create_cycle_with_parcelas
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.services import EsteiraService

from .factories import AssociadoFactory
from .models import Associado, Documento
from .strategies import CadastroValidationStrategy


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
    """Camada de serviço para lógica de negócio de associados."""

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
    @transaction.atomic
    def criar_associado_completo(validated_data, agente):
        dados = CadastroValidationStrategy().validate(validated_data)

        endereco_data = dados.pop("endereco")
        dados_bancarios_data = dados.pop("dados_bancarios")
        contato_data = dados.pop("contato")
        documentos_payload = dados.pop("documentos_payload", [])
        contrato_data = dados.pop("contrato")
        agente_responsavel = agente
        agente_responsavel_id = dados.pop("agente_responsavel_id", None)
        if agente_responsavel_id:
            agente_responsavel = agente.__class__.objects.get(pk=agente_responsavel_id)
        percentual_repasse = contrato_data.get("percentual_repasse")
        if percentual_repasse is None:
            percentual_repasse = ComissaoService.resolve_percentual(
                agente_responsavel.id if agente_responsavel else None
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
            status=Contrato.Status.EM_ANALISE,
        )
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
    def inativar_associado(associado: Associado) -> Associado:
        associado.status = Associado.Status.INATIVO
        associado.save(update_fields=["status", "updated_at"])
        return associado

    @staticmethod
    def buscar_com_contagens(queryset):
        return queryset

    @staticmethod
    def contar_ciclos_logicos(associado: Associado) -> dict[str, int]:
        contratos = get_operational_contracts_for_associado(associado)
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
        contratos = get_operational_contracts_for_associado(associado)
        for contrato in contratos:
            projection = build_contract_cycle_projection(contrato)
            if projection.get("refinanciamento_id"):
                return True
            if len(projection.get("cycles", [])) > 1:
                return True
        return False
