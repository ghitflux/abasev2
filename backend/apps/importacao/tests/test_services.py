from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from .base import ImportacaoBaseTestCase
from ..models import ArquivoRetorno, ArquivoRetornoItem, ImportacaoLog
from ..services import ArquivoRetornoService


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


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class ArquivoRetornoServiceTestCase(ImportacaoBaseTestCase):
    def test_upload_endpoint_restringe_permissao_e_processa_fixture(self):
        response = self.agent_client.get("/api/v1/importacao/arquivo-retorno/")
        self.assertEqual(response.status_code, 403)

        arquivo_agente = SimpleUploadedFile(
            "retorno_etipi_052025.txt",
            self.fixture_bytes(),
            content_type="text/plain",
        )
        response = self.agent_client.post(
            "/api/v1/importacao/arquivo-retorno/upload/",
            {"arquivo": arquivo_agente},
            format="multipart",
        )
        self.assertEqual(response.status_code, 403)

        self.create_associado_com_contrato(
            cpf="23993596315",
            nome="Maria de Jesus Santana Costa",
        )
        self.create_associado_com_contrato(
            cpf="21819424391",
            nome="Francisco Crisostomo Batista",
        )
        self.create_associado_com_contrato(
            cpf="48204773315",
            nome="Maria de Jesus Araujo Goncalves",
        )

        arquivo_tes = SimpleUploadedFile(
            "retorno_etipi_052025.txt",
            self.fixture_bytes(),
            content_type="text/plain",
        )
        response = self.tes_client.post(
            "/api/v1/importacao/arquivo-retorno/upload/",
            {"arquivo": arquivo_tes},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.json())
        payload = response.json()

        self.assertEqual(payload["competencia_display"], "05/2025")
        self.assertEqual(payload["status"], ArquivoRetorno.Status.CONCLUIDO)
        self.assertEqual(payload["resumo"]["baixa_efetuada"], 2)
        self.assertEqual(payload["resumo"]["nao_descontado"], 1)
        self.assertEqual(payload["resumo"]["pendencias_manuais"], 0)
        self.assertEqual(payload["resumo"]["nao_encontrado"], 1)

        response = self.tes_client.get(
            f"/api/v1/importacao/arquivo-retorno/{payload['id']}/descontados/",
            {"page_size": 10},
        )
        self.assertEqual(response.status_code, 200, response.json())
        detail_payload = response.json()
        self.assertEqual(detail_payload["count"], 2)
        self.assertEqual(len(detail_payload["results"]), 2)
        self.assertEqual(detail_payload["results"][0]["status_codigo"], "1")

    def test_processar_reprocessamento_idempotente_nao_duplica_ciclo(self):
        self.create_associado_com_contrato(
            cpf="23993596315",
            nome="Maria de Jesus Santana Costa",
        )
        self.create_associado_com_contrato(
            cpf="21819424391",
            nome="Francisco Crisostomo Batista",
        )
        self.create_associado_com_contrato(
            cpf="48204773315",
            nome="Maria de Jesus Araujo Goncalves",
        )

        service = ArquivoRetornoService()
        arquivo = service.upload(
            SimpleUploadedFile(
                "retorno_etipi_052025.txt",
                self.fixture_bytes(),
                content_type="text/plain",
            ),
            self.tesoureiro,
        )

        contrato = arquivo.itens.get(status_codigo="1").parcela.ciclo.contrato
        self.assertEqual(contrato.ciclos.count(), 2)

        service.processar(arquivo.id)

        contrato.refresh_from_db()
        self.assertEqual(contrato.ciclos.count(), 2)
        self.assertEqual(contrato.ciclos.get(numero=2).parcelas.count(), 3)

    def test_processar_registra_warning_de_parse_e_continua(self):
        self.create_associado_com_contrato(
            cpf="12345678901",
            nome="Servidor Valido",
        )
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

        response = self.tes_client.post(
            "/api/v1/importacao/arquivo-retorno/upload/",
            {
                "arquivo": SimpleUploadedFile(
                    "retorno_warning.txt",
                    conteudo.encode("latin-1"),
                    content_type="text/plain",
                )
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.json())

        arquivo = ArquivoRetorno.objects.get(pk=response.json()["id"])
        self.assertEqual(arquivo.total_registros, 1)
        self.assertEqual(arquivo.erros, 1)
        self.assertTrue(
            arquivo.logs.filter(
                tipo=ImportacaoLog.Tipo.PARSE,
                mensagem="Linha malformada ignorada durante o parse.",
            ).exists()
        )

    def test_processar_isola_cpf_duplicado_no_mesmo_arquivo(self):
        self.create_associado_com_contrato(
            cpf="12345678901",
            nome="SERVIDOR DUPLICADO",
            matricula_orgao="RET1001",
            orgao_publico="SECRETARIA DE TESTE",
        )
        self.create_associado_com_contrato(
            cpf="98765432100",
            nome="SERVIDOR UNICO",
            matricula_orgao="RET2001",
            orgao_publico="SECRETARIA DE TESTE",
        )
        conteudo = """
Entidade: 2102-ABASE                                                 Referência: 05/2025   Data da Geração: 23/05/2025
STATUS MATRICULA NOME                           CARGO                          FIN. ORGAO LANC.  TOTAL PAGO  VALOR        ORGAO PAGTO CPF
====== ========= ============================== ============================== ==== ============ ===== ===== ============ =========== ===========
{linha_duplicada_1}
{linha_duplicada_2}
       Órgão Pagamento:  002-SECRETARIA DE TESTE          -  2 Lançamento(s)  -  Total R$ 60.00
              Total do Status:  1  -  2 Lançamento(s)  -  Total R$ 60.00
{linha_unica}
       Órgão Pagamento:  002-SECRETARIA DE TESTE          -  1 Lançamento(s)  -  Total R$ 30.00
""".strip().format(
            linha_duplicada_1=build_detail_line(
                "1",
                "RET1001",
                "SERVIDOR DUPLICADO",
                "CARGO TESTE",
                "6580",
                "002",
                "001",
                "30.00",
                "30.00",
                "002",
                "12345678901",
            ),
            linha_duplicada_2=build_detail_line(
                "1",
                "RET1002",
                "SERVIDOR DUPLICADO",
                "CARGO TESTE",
                "6580",
                "002",
                "001",
                "30.00",
                "30.00",
                "002",
                "12345678901",
            ),
            linha_unica=build_detail_line(
                "1",
                "RET2001",
                "SERVIDOR UNICO",
                "CARGO TESTE",
                "6580",
                "002",
                "001",
                "30.00",
                "30.00",
                "002",
                "98765432100",
            ),
        )

        response = self.tes_client.post(
            "/api/v1/importacao/arquivo-retorno/upload/",
            {
                "arquivo": SimpleUploadedFile(
                    "retorno_cpf_duplicado.txt",
                    conteudo.encode("latin-1"),
                    content_type="text/plain",
                )
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.json())

        arquivo = ArquivoRetorno.objects.get(pk=response.json()["id"])
        self.assertEqual(arquivo.resultado_resumo["cpfs_duplicados_arquivo"], 1)
        self.assertEqual(arquivo.resultado_resumo["linhas_duplicadas_ignoradas"], 2)
        self.assertEqual(arquivo.resultado_resumo["pendencias_manuais"], 2)
        self.assertEqual(arquivo.resultado_resumo["baixa_efetuada"], 1)
        self.assertEqual(arquivo.resultado_resumo["pm_criados"], 1)

        itens_duplicados = arquivo.itens.filter(cpf_cnpj="12345678901").order_by("linha_numero")
        self.assertEqual(itens_duplicados.count(), 2)
        self.assertTrue(
            all(
                item.resultado_processamento == ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL
                for item in itens_duplicados
            )
        )
        self.assertEqual(
            arquivo.logs.filter(
                tipo=ImportacaoLog.Tipo.VALIDACAO,
                mensagem="CPF duplicado isolado da conciliação automática.",
            ).count(),
            1,
        )
