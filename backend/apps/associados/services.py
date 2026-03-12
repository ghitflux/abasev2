from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import EsteiraItem, Transicao

from .factories import AssociadoFactory
from .models import Associado, ContatoHistorico, DadosBancarios, Documento, Endereco
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
    def calcular_metricas():
        hoje = timezone.localdate()
        inicio_mes_atual = hoje.replace(day=1)

        base = Associado.objects.all()
        anterior_base = Associado.objects.filter(created_at__lt=inicio_mes_atual)

        payload = {}
        definicoes = {
            "total": Q(),
            "ativos": Q(status=Associado.Status.ATIVO),
            "em_analise": Q(status=Associado.Status.EM_ANALISE),
            "inativos": Q(status=Associado.Status.INATIVO),
        }

        for chave, filtro in definicoes.items():
            atual = base.filter(filtro).count()
            anterior = anterior_base.filter(filtro).count()
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

        associado_data = {
            "cpf_cnpj": dados["cpf_cnpj"],
            "nome_completo": dados["nome_completo"],
            "rg": dados.get("rg", ""),
            "orgao_expedidor": dados.get("orgao_expedidor", ""),
            "data_nascimento": dados.get("data_nascimento"),
            "profissao": dados.get("profissao", ""),
            "estado_civil": dados.get("estado_civil", ""),
            "email": contato_data.get("email", ""),
            "telefone": contato_data.get("celular", ""),
            "orgao_publico": contato_data.get("orgao_publico", ""),
            "matricula_orgao": contato_data.get("matricula_servidor", ""),
            "cargo": dados.get("cargo", "") or dados.get("profissao", ""),
            "observacao": dados.get("observacao", ""),
        }

        if dados["tipo_documento"] == Associado.TipoDocumento.CNPJ:
            associado = AssociadoFactory.criar_pessoa_juridica(associado_data, agente)
        else:
            associado = AssociadoFactory.criar_pessoa_fisica(associado_data, agente)

        Endereco.objects.create(associado=associado, **endereco_data)
        DadosBancarios.objects.create(associado=associado, **dados_bancarios_data)
        ContatoHistorico.objects.create(
            associado=associado,
            celular=contato_data.get("celular", ""),
            email=contato_data.get("email", ""),
            orgao_publico=contato_data.get("orgao_publico", ""),
            situacao_servidor=contato_data.get("situacao_servidor", ""),
            matricula_servidor=contato_data.get("matricula_servidor", ""),
            nome_contato=associado.nome_completo,
            telefone_contato=contato_data.get("celular", ""),
        )

        data_aprovacao, data_primeira_mensalidade, mes_averbacao = (
            calculate_contract_dates(contrato_data.get("data_aprovacao"))
        )
        primeira_referencia = data_primeira_mensalidade.replace(day=1)

        prazo_meses = int(contrato_data.get("prazo_meses") or 3)
        valor_mensalidade = Decimal(str(contrato_data.get("mensalidade") or 0))
        ciclo_fim = add_months(primeira_referencia, max(prazo_meses - 1, 0))

        contrato = Contrato.objects.create(
            associado=associado,
            agente=agente,
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

        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=primeira_referencia,
            data_fim=ciclo_fim,
            status=Ciclo.Status.FUTURO,
            valor_total=(valor_mensalidade * prazo_meses).quantize(Decimal("0.01")),
        )

        parcelas = []
        for indice in range(prazo_meses):
            referencia = add_months(primeira_referencia, indice)
            parcelas.append(
                Parcela(
                    ciclo=ciclo,
                    numero=indice + 1,
                    referencia_mes=referencia,
                    valor=valor_mensalidade,
                    data_vencimento=day_of_month(referencia),
                    status=Parcela.Status.EM_ABERTO,
                )
            )
        Parcela.objects.bulk_create(parcelas)

        esteira_item = EsteiraItem.objects.create(
            associado=associado,
            etapa_atual=EsteiraItem.Etapa.ANALISE,
            status=EsteiraItem.Situacao.AGUARDANDO,
        )
        Transicao.objects.create(
            esteira_item=esteira_item,
            acao="criar_cadastro",
            de_status=EsteiraItem.Etapa.CADASTRO,
            para_status=EsteiraItem.Etapa.ANALISE,
            de_situacao=EsteiraItem.Situacao.AGUARDANDO,
            para_situacao=EsteiraItem.Situacao.AGUARDANDO,
            realizado_por=agente,
            observacao="Cadastro inicial enviado para análise.",
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
    def buscar_com_contagens(queryset):
        return queryset.annotate(
            ciclos_abertos=Count(
                "contratos__ciclos",
                filter=Q(
                    contratos__ciclos__status__in=[
                        Ciclo.Status.FUTURO,
                        Ciclo.Status.ABERTO,
                        Ciclo.Status.APTO_A_RENOVAR,
                    ]
                ),
                distinct=True,
            ),
            ciclos_fechados=Count(
                "contratos__ciclos",
                filter=Q(
                    contratos__ciclos__status__in=[
                        Ciclo.Status.CICLO_RENOVADO,
                        Ciclo.Status.FECHADO,
                    ]
                ),
                distinct=True,
            ),
        )
