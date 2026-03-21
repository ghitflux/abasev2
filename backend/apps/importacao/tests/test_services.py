from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.db.models import Sum
from django.test import override_settings
from django.utils import timezone

from apps.associados.models import Associado
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.models import Contrato, Parcela

from .base import ImportacaoBaseTestCase
from ..legacy import LegacyPagamentoSnapshot
from ..models import ArquivoRetorno, ArquivoRetornoItem, ImportacaoLog, PagamentoMensalidade
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
        self.assertEqual(payload["financeiro"]["total"], 4)
        self.assertEqual(payload["financeiro"]["ok"], 2)
        self.assertEqual(payload["financeiro"]["recebido"], "60.00")

        response = self.tes_client.get(
            f"/api/v1/importacao/arquivo-retorno/{payload['id']}/descontados/",
            {"page_size": 10},
        )
        self.assertEqual(response.status_code, 200, response.json())
        detail_payload = response.json()
        self.assertEqual(detail_payload["count"], 2)
        self.assertEqual(len(detail_payload["results"]), 2)
        self.assertEqual(detail_payload["results"][0]["status_codigo"], "1")
        self.assertEqual(detail_payload["results"][0]["agente_responsavel"], "Tes ABASE")
        self.assertIsNotNone(detail_payload["results"][0]["associado_id"])
        self.assertTrue(detail_payload["results"][0]["associado_matricula"])

    def test_list_filtra_por_competencia_e_periodo(self):
        arquivo_jan = self.create_arquivo_retorno(nome="retorno_janeiro.txt")
        arquivo_jan.competencia = date(2026, 1, 1)
        arquivo_jan.status = ArquivoRetorno.Status.CONCLUIDO
        arquivo_jan.save(update_fields=["competencia", "status", "updated_at"])

        arquivo_fev = self.create_arquivo_retorno(nome="retorno_fevereiro.txt")
        arquivo_fev.competencia = date(2026, 2, 1)
        arquivo_fev.status = ArquivoRetorno.Status.CONCLUIDO
        arquivo_fev.save(update_fields=["competencia", "status", "updated_at"])

        arquivo_mar = self.create_arquivo_retorno(nome="retorno_marco.txt")
        arquivo_mar.competencia = date(2026, 3, 1)
        arquivo_mar.status = ArquivoRetorno.Status.CONCLUIDO
        arquivo_mar.save(update_fields=["competencia", "status", "updated_at"])

        response = self.tes_client.get(
            "/api/v1/importacao/arquivo-retorno/",
            {"competencia": "2026-02", "periodo": "mes", "page_size": 10},
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], arquivo_fev.id)

        response = self.tes_client.get(
            "/api/v1/importacao/arquivo-retorno/",
            {"competencia": "2026-02", "periodo": "trimestre", "page_size": 10},
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 3)
        self.assertEqual(
            [row["id"] for row in payload["results"]],
            [arquivo_mar.id, arquivo_fev.id, arquivo_jan.id],
        )

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
        self.assertEqual(contrato.ciclos.count(), 1)

        service.processar(arquivo.id)

        contrato.refresh_from_db()
        self.assertEqual(contrato.ciclos.count(), 1)
        self.assertEqual(contrato.ciclos.get(numero=1).parcelas.count(), 3)

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

    def test_processar_consolida_cpf_duplicado_no_padrao_legado(self):
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
        self.assertEqual(arquivo.resultado_resumo["linhas_duplicadas_ignoradas"], 1)
        self.assertEqual(arquivo.resultado_resumo["pendencias_manuais"], 0)
        self.assertEqual(arquivo.resultado_resumo["baixa_efetuada"], 2)
        self.assertEqual(arquivo.resultado_resumo["pm_criados"], 2)

        itens_duplicados = arquivo.itens.filter(cpf_cnpj="12345678901").order_by("linha_numero")
        self.assertEqual(itens_duplicados.count(), 1)
        self.assertEqual(
            itens_duplicados.first().resultado_processamento,
            ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
        )
        self.assertEqual(
            arquivo.logs.filter(
                tipo=ImportacaoLog.Tipo.VALIDACAO,
                mensagem="CPF duplicado consolidado no padrão legado.",
            ).count(),
            1,
        )

    def test_upload_outubro_replica_totais_do_legado(self):
        response = self.tes_client.post(
            "/api/v1/importacao/arquivo-retorno/upload/",
            {
                "arquivo": SimpleUploadedFile(
                    "Relatorio_D2102-10-2025_inicio.txt",
                    self.fixture_bytes("retorno_etipi_102025.txt"),
                    content_type="text/plain",
                )
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.json())

        arquivo = ArquivoRetorno.objects.get(pk=response.json()["id"])
        self.assertEqual(arquivo.total_registros, 238)
        self.assertEqual(arquivo.resultado_resumo["cpfs_duplicados_arquivo"], 1)
        self.assertEqual(arquivo.resultado_resumo["linhas_duplicadas_ignoradas"], 1)

        pagamentos = PagamentoMensalidade.objects.filter(referencia_month=date(2025, 10, 1))
        self.assertEqual(pagamentos.count(), 238)
        self.assertEqual(
            pagamentos.aggregate(total=Sum("valor"))["total"],
            Decimal("47364.38"),
        )
        self.assertEqual(pagamentos.filter(status_code__in=["1", "4"]).count(), 217)
        self.assertEqual(
            pagamentos.filter(status_code__in=["1", "4"]).aggregate(total=Sum("valor"))["total"],
            Decimal("45491.38"),
        )

        alceanira = pagamentos.filter(cpf_cnpj="67556906353")
        self.assertEqual(alceanira.count(), 1)
        self.assertEqual(alceanira.first().valor, Decimal("1.00"))

        financeiro = self.tes_client.get(
            f"/api/v1/importacao/arquivo-retorno/{arquivo.id}/financeiro/"
        )
        self.assertEqual(financeiro.status_code, 200, financeiro.json())
        payload = financeiro.json()
        self.assertEqual(payload["resumo"]["total"], 238)
        self.assertEqual(payload["resumo"]["esperado"], "47364.38")
        self.assertEqual(payload["resumo"]["ok"], 217)
        self.assertEqual(payload["resumo"]["recebido"], "45491.38")
        self.assertEqual(len(payload["rows"]), 238)

    def test_upload_aplica_snapshot_manual_do_legado_na_tabela_atual_e_no_resumo(self):
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

        with patch(
            "apps.importacao.services.list_legacy_pagamento_snapshots",
            return_value={
                "21819424391": LegacyPagamentoSnapshot(
                    manual_status="pago",
                    esperado_manual=Decimal("30.00"),
                    recebido_manual=Decimal("30.00"),
                    manual_forma_pagamento="PIX",
                    agente_refi_solicitado=True,
                )
            },
        ):
            response = self.tes_client.post(
                "/api/v1/importacao/arquivo-retorno/upload/",
                {
                    "arquivo": SimpleUploadedFile(
                        "retorno_etipi_052025.txt",
                        self.fixture_bytes(),
                        content_type="text/plain",
                    )
                },
                format="multipart",
            )
            self.assertEqual(response.status_code, 201, response.json())

            pagamento = PagamentoMensalidade.objects.get(
                cpf_cnpj="21819424391",
                referencia_month=date(2025, 5, 1),
            )
            self.assertEqual(pagamento.manual_status, PagamentoMensalidade.ManualStatus.PAGO)
            self.assertEqual(pagamento.recebido_manual, Decimal("30.00"))
            self.assertEqual(pagamento.manual_forma_pagamento, "PIX")
            self.assertTrue(pagamento.agente_refi_solicitado)

            financeiro = self.tes_client.get(
                f"/api/v1/importacao/arquivo-retorno/{response.json()['id']}/financeiro/"
            )
            self.assertEqual(financeiro.status_code, 200, financeiro.json())
            payload = financeiro.json()
            self.assertEqual(payload["resumo"]["ok"], 3)
            self.assertEqual(payload["resumo"]["recebido"], "90.00")

    def test_processar_promove_pagamento_manual_para_automatico_antes_da_reconciliacao(self):
        associado = Associado.objects.create(
            nome_completo="ACACIO LUSTOSA DANTAS",
            cpf_cnpj="77852621368",
            email="acacio@teste.local",
            telefone="86999999999",
            orgao_publico="SECRETARIA DA EDUCACAO",
            matricula_orgao="362602-4",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            codigo="CTR-TESTE-ACACIO",
            valor_bruto=Decimal("300.00"),
            valor_liquido=Decimal("210.00"),
            valor_mensalidade=Decimal("100.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("210.00"),
            valor_total_antecipacao=Decimal("300.00"),
            comissao_agente=Decimal("21.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 11, 25),
            data_aprovacao=date(2025, 11, 25),
            data_primeira_mensalidade=date(2026, 1, 7),
            mes_averbacao=date(2025, 12, 1),
            auxilio_liberado_em=date(2025, 11, 25),
        )
        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="import-dez",
            referencia_month=date(2025, 12, 1),
            status_code="1",
            matricula="362602-4",
            orgao_pagto="918",
            nome_relatorio="ACACIO LUSTOSA DANTAS",
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=Decimal("100.00"),
            source_file_path="retornos/dezembro.txt",
        )
        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="import-jan",
            referencia_month=date(2026, 1, 1),
            status_code="1",
            matricula="362602-4",
            orgao_pagto="918",
            nome_relatorio="ACACIO LUSTOSA DANTAS",
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=Decimal("100.00"),
            source_file_path="retornos/janeiro.txt",
        )
        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="manual-fev",
            referencia_month=date(2026, 2, 1),
            status_code="M",
            matricula="362602-4",
            orgao_pagto="918",
            nome_relatorio="ACACIO LUSTOSA DANTAS",
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=Decimal("100.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=timezone.make_aware(datetime(2026, 2, 5, 0, 0, 0)),
            recebido_manual=Decimal("100.00"),
            source_file_path="legacy/pagamentos_mensalidades",
        )

        with patch("apps.contratos.cycle_projection.timezone.localdate", return_value=date(2026, 3, 21)):
            rebuild_contract_cycle_state(contrato, execute=True)

        self.assertEqual(
            list(
                Parcela.objects.filter(ciclo__contrato=contrato)
                .order_by("ciclo__numero", "numero")
                .values_list("referencia_mes", flat=True)
            ),
            [date(2025, 12, 1), date(2026, 1, 1), date(2026, 3, 1)],
        )

        arquivo = self.create_arquivo_retorno(nome="retorno_fev_acacio.txt")
        arquivo.competencia = date(2026, 2, 1)
        arquivo.resultado_resumo = {"competencia": "02/2026"}
        arquivo.save(update_fields=["competencia", "resultado_resumo", "updated_at"])
        default_storage.save(arquivo.arquivo_url, ContentFile(b"retorno-fevereiro"))

        parsed = SimpleNamespace(
            meta=SimpleNamespace(
                competencia="02/2026",
                data_geracao="04/03/2026",
                entidade="2102-ABASE",
                sistema_origem="ETIPI/iNETConsig",
            ),
            items=[
                {
                    "linha_numero": 710,
                    "cpf_cnpj": associado.cpf_cnpj,
                    "matricula_servidor": "362602-4",
                    "nome_servidor": "ACACIO LUSTOSA DANTAS",
                    "cargo": "-SEM PLANO",
                    "competencia": "02/2026",
                    "valor_descontado": Decimal("100.00"),
                    "status_codigo": "1",
                    "status_desconto": ArquivoRetornoItem.StatusDesconto.EFETIVADO,
                    "status_descricao": "Lançado e Efetivado",
                    "motivo_rejeicao": None,
                    "orgao_codigo": "6580",
                    "orgao_pagto_codigo": "918",
                    "orgao_pagto_nome": "SECRETARIA DA EDUCACAO",
                    "payload_bruto": {},
                }
            ],
            warnings=[],
        )

        service = ArquivoRetornoService()
        with (
            patch.object(service.parser, "parse", return_value=parsed),
            patch("apps.contratos.cycle_projection.timezone.localdate", return_value=date(2026, 3, 21)),
            patch("apps.importacao.reconciliacao.timezone.localdate", return_value=date(2026, 3, 21)),
        ):
            service.processar(arquivo.id)

        pagamento = PagamentoMensalidade.objects.get(
            cpf_cnpj=associado.cpf_cnpj,
            referencia_month=date(2026, 2, 1),
        )
        item = ArquivoRetornoItem.objects.get(arquivo_retorno=arquivo, cpf_cnpj=associado.cpf_cnpj)
        contrato.refresh_from_db()

        self.assertEqual(pagamento.status_code, "1")
        self.assertIsNone(pagamento.manual_status)
        self.assertIsNone(pagamento.manual_paid_at)
        self.assertEqual(pagamento.source_file_path, arquivo.arquivo_url)
        self.assertEqual(
            item.resultado_processamento,
            ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
        )
        self.assertIsNotNone(item.parcela_id)
        self.assertEqual(item.parcela.referencia_mes, date(2026, 2, 1))
        self.assertEqual(contrato.ciclos.count(), 1)
        self.assertEqual(
            list(
                Parcela.objects.filter(ciclo__contrato=contrato)
                .order_by("ciclo__numero", "numero")
                .values_list("referencia_mes", flat=True)
            ),
            [date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)],
        )
