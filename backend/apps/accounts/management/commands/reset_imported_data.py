from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection

from apps.accounts.models import (
    AgenteMargemConfig,
    AgenteMargemHistorico,
    AgenteMargemSnapshot,
)
from apps.associados.models import Associado, ContatoHistorico, DadosBancarios, Documento, Endereco
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import DocIssue, DocReupload, EsteiraItem, Pendencia, Transicao
from apps.financeiro.models import Despesa
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem, ImportacaoLog, PagamentoMensalidade
from apps.refinanciamento.models import (
    AjusteValor,
    Assumption,
    Comprovante as RefinanciamentoComprovante,
    Item as RefinanciamentoItem,
    Refinanciamento,
)
from apps.relatorios.models import RelatorioGerado
from apps.tesouraria.models import Confirmacao, Pagamento


MODELS_TO_TRUNCATE = (
    AgenteMargemSnapshot,
    AgenteMargemHistorico,
    AgenteMargemConfig,
    Documento,
    ContatoHistorico,
    DadosBancarios,
    Endereco,
    PagamentoMensalidade,
    ImportacaoLog,
    ArquivoRetornoItem,
    ArquivoRetorno,
    DocReupload,
    DocIssue,
    Pendencia,
    Transicao,
    EsteiraItem,
    Confirmacao,
    Pagamento,
    RefinanciamentoComprovante,
    RefinanciamentoItem,
    AjusteValor,
    Assumption,
    Refinanciamento,
    Parcela,
    Ciclo,
    Contrato,
    Despesa,
    RelatorioGerado,
    Associado,
)


class Command(BaseCommand):
    help = (
        "Limpa os dados de dominio importados para a estrutura Django preservando "
        "usuarios, papeis e tabelas legadas cruas."
    )

    def handle(self, *args, **options):
        tables = []
        seen = set()
        for model in MODELS_TO_TRUNCATE:
            table_name = model._meta.db_table
            if table_name not in seen:
                tables.append(table_name)
                seen.add(table_name)

        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            try:
                for table_name in tables:
                    cursor.execute(f"TRUNCATE TABLE {connection.ops.quote_name(table_name)}")
            finally:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        self.stdout.write(
            self.style.SUCCESS(
                f"Reset concluido. {len(tables)} tabelas de dominio foram limpas."
            )
        )
