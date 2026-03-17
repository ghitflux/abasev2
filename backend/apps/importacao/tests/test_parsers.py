from __future__ import annotations

import tempfile
from decimal import Decimal

from .base import ImportacaoBaseTestCase
from ..parsers import ETIPITxtRetornoParser


def build_detail_line(
    status: str,
    matricula: str,
    nome: str,
    cargo: str,
    fin: str,
    orgao: str,
    lancamento: str,
    total_pago: str,
    valor: str,
    orgao_pagto: str,
    cpf: str,
) -> str:
    return (
        f"{status:>7}"
        f"{matricula:<10}"
        f"{nome:<31}"
        f"{cargo:<31}"
        f"{fin:>5}"
        f"{orgao:>6}"
        f"{lancamento:>7}"
        f"{total_pago:>12}"
        f"{valor:>13}"
        f"{orgao_pagto:>12}"
        f"{cpf}"
    )


class ETIPITxtRetornoParserTestCase(ImportacaoBaseTestCase):
    def test_parse_fixture_ignora_cabecalhos_totais_e_legenda(self):
        parser = ETIPITxtRetornoParser()

        parsed = parser.parse(str(self.fixture_path()))

        self.assertEqual(parsed.meta.competencia, "05/2025")
        self.assertEqual(parsed.meta.data_geracao, "23/05/2025")
        self.assertEqual(len(parsed.items), 4)
        self.assertEqual(parsed.items[0]["status_codigo"], "1")
        self.assertEqual(parsed.items[0]["orgao_pagto_codigo"], "002")
        self.assertEqual(parsed.items[0]["orgao_pagto_nome"], "SEC. EST. ADMIN. E PREVIDEN.")
        self.assertEqual(parsed.items[2]["status_codigo"], "3")
        self.assertEqual(parsed.items[2]["orgao_pagto_nome"], "")
        self.assertEqual(parsed.warnings, [])

    def test_parse_arquivo_latin1_com_acentos(self):
        parser = ETIPITxtRetornoParser()
        conteudo = """
Entidade: 2102-ABASE                                                 Referência: 05/2025   Data da Geração: 23/05/2025
STATUS MATRICULA NOME                           CARGO                          FIN. ORGAO LANC.  TOTAL PAGO  VALOR        ORGAO PAGTO CPF
====== ========= ============================== ============================== ==== ============ ===== ===== ============ =========== ===========
  1    000001-0  JOÃO DA SILVA                  AGENTE                         6580      002     999   001          30.00      002    12345678901
       Órgão Pagamento:  002-SECRETARIA DE TESTE          -  1 Lançamento(s)  -  Total R$ 30.00
""".strip()

        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.write(conteudo.encode("latin-1"))
            temp_file.flush()

            parsed = parser.parse(temp_file.name)

        self.assertEqual(parsed.encoding, "latin-1")
        self.assertEqual(parsed.items[0]["nome_servidor"], "JOÃO DA SILVA")
        self.assertEqual(parsed.items[0]["orgao_pagto_nome"], "SECRETARIA DE TESTE")

    def test_parse_aceita_valor_com_virgula(self):
        parser = ETIPITxtRetornoParser()
        conteudo = """
Entidade: 2102-ABASE                                                 Referência: 05/2025   Data da Geração: 23/05/2025
STATUS MATRICULA NOME                           CARGO                          FIN. ORGAO LANC.  TOTAL PAGO  VALOR        ORGAO PAGTO CPF
====== ========= ============================== ============================== ==== ============ ===== ===== ============ =========== ===========
  1    000001-0  JOÃO DA SILVA                  AGENTE                         6580      002     999   001          30,00      002    12345678901
       Órgão Pagamento:  002-SECRETARIA DE TESTE          -  1 Lançamento(s)  -  Total R$ 30,00
""".strip()

        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.write(conteudo.encode("latin-1"))
            temp_file.flush()

            parsed = parser.parse(temp_file.name)

        self.assertEqual(len(parsed.items), 1)
        self.assertEqual(str(parsed.items[0]["valor_descontado"]), "30.00")
        self.assertEqual(parsed.warnings, [])

    def test_parse_normaliza_status_5_6_e_s(self):
        parser = ETIPITxtRetornoParser()
        conteudo = """
Entidade: 2102-ABASE                                                 Referência: 05/2025   Data da Geração: 23/05/2025
STATUS MATRICULA NOME                           CARGO                          FIN. ORGAO LANC.  TOTAL PAGO  VALOR        ORGAO PAGTO CPF
====== ========= ============================== ============================== ==== ============ ===== ===== ============ =========== ===========
{linha_1}
{linha_2}
{linha_3}
       Órgão Pagamento:  002-SECRETARIA DE TESTE          -  3 Lançamento(s)  -  Total R$ 90.00
""".strip().format(
            linha_1=build_detail_line(
                "5",
                "RET-0001",
                "SERVIDOR PENDENTE UM",
                "CARGO TESTE",
                "6580",
                "002",
                "001",
                "30.00",
                "30.00",
                "002",
                "12345678901",
            ),
            linha_2=build_detail_line(
                "6",
                "RET-0002",
                "SERVIDOR PENDENTE DOIS",
                "CARGO TESTE",
                "6580",
                "002",
                "001",
                "30.00",
                "30.00",
                "002",
                "12345678902",
            ),
            linha_3=build_detail_line(
                "S",
                "RET-0003",
                "SERVIDOR SUSPENSO",
                "CARGO TESTE",
                "6580",
                "002",
                "001",
                "30.00",
                "30.00",
                "002",
                "12345678903",
            ),
        )

        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.write(conteudo.encode("latin-1"))
            temp_file.flush()

            parsed = parser.parse(temp_file.name)

        self.assertEqual([item["status_codigo"] for item in parsed.items], ["5", "6", "S"])
        self.assertEqual([item["status_desconto"] for item in parsed.items], ["pendente", "pendente", "rejeitado"])
        self.assertEqual(parsed.items[2]["motivo_rejeicao"], "Não Lançado: Compra de Dívida ou Suspensão SEAD")

    def test_parse_registra_warning_em_linha_malformada(self):
        parser = ETIPITxtRetornoParser()
        conteudo = """
Entidade: 2102-ABASE                                                 Referência: 05/2025   Data da Geração: 23/05/2025
STATUS MATRICULA NOME                           CARGO                          FIN. ORGAO LANC.  TOTAL PAGO  VALOR        ORGAO PAGTO CPF
====== ========= ============================== ============================== ==== ============ ===== ===== ============ =========== ===========
{linha_valida}
{linha_invalida}
       Órgão Pagamento:  002-SECRETARIA DE TESTE          -  2 Lançamento(s)  -  Total R$ 60.00
""".strip().format(
            linha_valida=build_detail_line(
                "1",
                "RET-1001",
                "SERVIDOR VALIDO",
                "CARGO TESTE",
                "6580",
                "002",
                "001",
                "30.00",
                "30.00",
                "002",
                "12345678901",
            ),
            linha_invalida=build_detail_line(
                "4",
                "RET-1002",
                "SERVIDOR COM ERRO",
                "CARGO TESTE",
                "6580",
                "002",
                "001",
                "30.00",
                "XX.XX",
                "002",
                "12345678902",
            ),
        )

        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.write(conteudo.encode("latin-1"))
            temp_file.flush()

            parsed = parser.parse(temp_file.name)

        self.assertEqual(len(parsed.items), 1)
        self.assertEqual(len(parsed.warnings), 1)
        self.assertIn("Valor inválido", parsed.warnings[0]["erro"])

    def test_parse_prioriza_legenda_do_rodape_para_descricao_do_status(self):
        parser = ETIPITxtRetornoParser()
        conteudo = """
Entidade: 2102-ABASE                                                 Referência: 05/2025   Data da Geração: 23/05/2025
STATUS MATRICULA NOME                           CARGO                          FIN. ORGAO LANC.  TOTAL PAGO  VALOR        ORGAO PAGTO CPF
====== ========= ============================== ============================== ==== ============ ===== ===== ============ =========== ===========
{linha}
       Órgão Pagamento:  002-SECRETARIA DE TESTE          -  1 Lançamento(s)  -  Total R$ 30.00

Legenda do Status
---------------------------------------------------------------------------------
 4 - Descrição personalizada vinda da legenda
""".strip().format(
            linha=build_detail_line(
                "4",
                "RET-4001",
                "SERVIDOR STATUS CUSTOM",
                "CARGO TESTE",
                "6580",
                "002",
                "001",
                "30.00",
                "30.00",
                "002",
                "12345678901",
            )
        )

        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.write(conteudo.encode("latin-1"))
            temp_file.flush()

            parsed = parser.parse(temp_file.name)

        self.assertEqual(len(parsed.items), 1)
        self.assertEqual(parsed.items[0]["status_codigo"], "4")
        self.assertEqual(parsed.items[0]["status_descricao"], "Descrição personalizada vinda da legenda")

    def test_parse_relatorio_outubro_replica_valores_legado(self):
        parser = ETIPITxtRetornoParser()
        parsed = parser.parse(str(self.fixture_path("retorno_etipi_102025.txt")))

        self.assertEqual(len(parsed.items), 239)
        self.assertEqual(
            sum((item["valor_descontado"] for item in parsed.items), Decimal("0")),
            Decimal("47365.38"),
        )
        duplicados = [item for item in parsed.items if item["cpf_cnpj"] == "67556906353"]
        self.assertEqual(len(duplicados), 2)
        self.assertTrue(all(item["valor_descontado"] == Decimal("1.00") for item in duplicados))
