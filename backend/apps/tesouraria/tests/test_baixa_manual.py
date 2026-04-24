from __future__ import annotations

import tempfile
from datetime import date, datetime
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem, PagamentoMensalidade
from apps.tesouraria.models import BaixaManual


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class BaixaManualViewSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_tesoureiro = Role.objects.create(
            codigo="TESOUREIRO",
            nome="Tesoureiro",
        )
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.role_coordenador = Role.objects.create(
            codigo="COORDENADOR",
            nome="Coordenador",
        )

        cls.tesoureiro = User.objects.create_user(
            email="tesouraria.baixa@abase.local",
            password="Senha@123",
            first_name="Tesouraria",
            last_name="ABASE",
            is_active=True,
        )
        cls.tesoureiro.roles.add(cls.role_tesoureiro)

        cls.agente_a = User.objects.create_user(
            email="agente.a@abase.local",
            password="Senha@123",
            first_name="Agente",
            last_name="Alpha",
            is_active=True,
        )
        cls.agente_a.roles.add(cls.role_agente)

        cls.agente_b = User.objects.create_user(
            email="agente.b@abase.local",
            password="Senha@123",
            first_name="Agente",
            last_name="Beta",
            is_active=True,
        )
        cls.agente_b.roles.add(cls.role_agente)

        cls.coordenador = User.objects.create_user(
            email="coordenador.baixa@abase.local",
            password="Senha@123",
            first_name="Coordenador",
            last_name="ABASE",
            is_active=True,
        )
        cls.coordenador.roles.add(cls.role_coordenador)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.tesoureiro)
        self.coord_client = APIClient()
        self.coord_client.force_authenticate(self.coordenador)

    def _create_associado(
        self,
        *,
        cpf: str,
        nome: str,
        matricula: str,
        agente: User,
        status: str = Associado.Status.ATIVO,
    ) -> Associado:
        return Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula=matricula,
            matricula_orgao=matricula,
            status=status,
            agente_responsavel=agente,
        )

    def _create_parcela(
        self,
        *,
        associado: Associado,
        agente: User,
        referencia: date,
        vencimento: date,
        status: str,
        valor: str = "200.00",
        codigo: str,
    ) -> Parcela:
        contrato = Contrato.objects.create(
            associado=associado,
            agente=agente,
            codigo=codigo,
            valor_bruto=Decimal("600.00"),
            valor_liquido=Decimal("600.00"),
            valor_mensalidade=Decimal(valor),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=referencia,
            data_aprovacao=referencia,
            data_primeira_mensalidade=referencia,
            mes_averbacao=referencia,
            auxilio_liberado_em=referencia,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=referencia,
            data_fim=referencia,
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal(valor),
        )
        return Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=referencia,
            valor=Decimal(valor),
            data_vencimento=vencimento,
            status=status,
        )

    def _create_arquivo_retorno(
        self,
        *,
        competencia: date,
        nome: str = "Relatorio.txt",
        status: str = ArquivoRetorno.Status.CONCLUIDO,
    ) -> ArquivoRetorno:
        return ArquivoRetorno.objects.create(
            arquivo_nome=nome,
            arquivo_url=f"/tmp/{nome}",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI",
            competencia=competencia,
            total_registros=0,
            processados=0,
            status=status,
            uploaded_by=self.tesoureiro,
        )

    def _create_retorno_item(
        self,
        *,
        arquivo: ArquivoRetorno,
        associado: Associado,
        linha_numero: int,
        competencia: str,
        valor: str,
        parcela: Parcela | None = None,
        resultado: str = ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO,
    ) -> ArquivoRetornoItem:
        return ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=linha_numero,
            cpf_cnpj=associado.cpf_cnpj,
            matricula_servidor=associado.matricula_orgao or associado.matricula,
            nome_servidor=associado.nome_completo,
            competencia=competencia,
            valor_descontado=Decimal(valor),
            status_codigo="S",
            status_desconto=ArquivoRetornoItem.StatusDesconto.REJEITADO,
            status_descricao="Não descontado",
            associado=associado,
            parcela=parcela,
            processado=True,
            resultado_processamento=resultado,
        )

    def test_lista_pendentes_filtra_por_agente_data_e_search(self):
        parcela_match = self._create_parcela(
            associado=self._create_associado(
                cpf="11111111111",
                nome="Marcianita Michele Ramos Mendes",
                matricula="MAT-111",
                agente=self.agente_a,
            ),
            agente=self.agente_a,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 10),
            status=Parcela.Status.NAO_DESCONTADO,
            codigo="CTR-TESTE-111",
        )
        self._create_parcela(
            associado=self._create_associado(
                cpf="22222222222",
                nome="Outro Associado",
                matricula="MAT-222",
                agente=self.agente_b,
            ),
            agente=self.agente_b,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 15),
            status=Parcela.Status.EM_ABERTO,
            codigo="CTR-TESTE-222",
        )

        response = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {
                "agente": str(self.agente_a.id),
                "data_inicio": "2026-03-01",
                "data_fim": "2026-03-31",
                "search": "11111111111",
            },
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], parcela_match.id)
        self.assertEqual(payload["results"][0]["parcela_id"], parcela_match.id)
        self.assertEqual(payload["results"][0]["cpf_cnpj"], "11111111111")
        self.assertEqual(payload["kpis"]["total_pendentes"], 1)
        self.assertEqual(payload["kpis"]["nao_descontado"], 1)

    def test_lista_pendentes_ignora_parcelas_em_previsao(self):
        self._create_parcela(
            associado=self._create_associado(
                cpf="55555555555",
                nome="Associado Setembro",
                matricula="MAT-555",
                agente=self.agente_a,
            ),
            agente=self.agente_a,
            referencia=date(2025, 9, 1),
            vencimento=date(2025, 9, 10),
            status=Parcela.Status.EM_PREVISAO,
            codigo="CTR-PREV-555",
        )
        parcela_match = self._create_parcela(
            associado=self._create_associado(
                cpf="66666666666",
                nome="Associado Inadimplente",
                matricula="MAT-666",
                agente=self.agente_a,
            ),
            agente=self.agente_a,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 10),
            status=Parcela.Status.NAO_DESCONTADO,
            codigo="CTR-ND-666",
        )

        response = self.client.get("/api/v1/tesouraria/baixa-manual/")

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], parcela_match.id)
        self.assertEqual(payload["results"][0]["status"], Parcela.Status.NAO_DESCONTADO)

    def test_lista_pendentes_por_competencia_setembro_retorna_vazio(self):
        self._create_parcela(
            associado=self._create_associado(
                cpf="77777777777",
                nome="Associado Setembro",
                matricula="MAT-777",
                agente=self.agente_a,
            ),
            agente=self.agente_a,
            referencia=date(2025, 9, 1),
            vencimento=date(2025, 9, 10),
            status=Parcela.Status.EM_PREVISAO,
            codigo="CTR-PREV-777",
        )

        response = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {"competencia": "2025-09"},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["results"], [])

    def test_lista_pendentes_sem_competencia_soma_multiplos_meses_e_kpis_filtrados(self):
        outubro = self._create_parcela(
            associado=self._create_associado(
                cpf="88888888888",
                nome="Associado Outubro",
                matricula="MAT-888",
                agente=self.agente_a,
            ),
            agente=self.agente_a,
            referencia=date(2025, 10, 1),
            vencimento=date(2025, 10, 10),
            status=Parcela.Status.NAO_DESCONTADO,
            valor="200.00",
            codigo="CTR-ND-888",
        )
        marco = self._create_parcela(
            associado=self._create_associado(
                cpf="99999999999",
                nome="Associado Marco",
                matricula="MAT-999",
                agente=self.agente_a,
            ),
            agente=self.agente_a,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 10),
            status=Parcela.Status.NAO_DESCONTADO,
            valor="300.00",
            codigo="CTR-ND-999",
        )
        self._create_parcela(
            associado=self._create_associado(
                cpf="12121212121",
                nome="Associado Em Aberto",
                matricula="MAT-212",
                agente=self.agente_a,
            ),
            agente=self.agente_a,
            referencia=date(2026, 1, 1),
            vencimento=date(2026, 1, 10),
            status=Parcela.Status.EM_ABERTO,
            valor="150.00",
            codigo="CTR-AB-212",
        )

        response = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {"status": Parcela.Status.NAO_DESCONTADO},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        self.assertEqual(
            {item["referencia_mes"] for item in payload["results"]},
            {"2025-10-01", "2026-03-01"},
        )
        self.assertEqual(payload["kpis"]["total_pendentes"], 2)
        self.assertEqual(payload["kpis"]["nao_descontado"], 2)
        self.assertEqual(payload["kpis"]["em_aberto"], 0)
        self.assertEqual(payload["kpis"]["valor_total_pendente"], "500.00")
        self.assertEqual(payload["kpis"]["total_inadimplentes"], 2)
        self.assertEqual(
            {item["id"] for item in payload["results"]},
            {outubro.id, marco.id},
        )

    def test_lista_pendentes_considera_nao_descontado_do_arquivo_retorno(self):
        associado_marco = self._create_associado(
            cpf="13131313131",
            nome="Associado Marco Retorno",
            matricula="MAT-313",
            agente=self.agente_a,
        )
        parcela_marco = self._create_parcela(
            associado=associado_marco,
            agente=self.agente_a,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 10),
            status=Parcela.Status.NAO_DESCONTADO,
            valor="300.00",
            codigo="CTR-RET-313",
        )
        associado_sem_parcela = self._create_associado(
            cpf="14141414141",
            nome="Associado Sem Parcela",
            matricula="MAT-414",
            agente=self.agente_a,
        )
        arquivo = self._create_arquivo_retorno(
            competencia=date(2026, 3, 1),
            nome="Relatorio_D2102-03-2026.txt",
        )
        self._create_retorno_item(
            arquivo=arquivo,
            associado=associado_marco,
            linha_numero=1,
            competencia="03/2026",
            valor="300.00",
            parcela=parcela_marco,
        )
        item_sem_parcela = self._create_retorno_item(
            arquivo=arquivo,
            associado=associado_sem_parcela,
            linha_numero=2,
            competencia="03/2026",
            valor="150.00",
            parcela=None,
        )

        response = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {"status": Parcela.Status.NAO_DESCONTADO, "competencia": "2026-03"},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["kpis"]["nao_descontado"], 2)
        self.assertEqual(payload["kpis"]["valor_total_pendente"], "450.00")
        self.assertEqual(payload["kpis"]["total_inadimplentes"], 2)
        self.assertEqual(payload["kpis"]["total_pendentes_com_parcela"], 1)

        rows_by_cpf = {item["cpf_cnpj"]: item for item in payload["results"]}
        self.assertEqual(rows_by_cpf["13131313131"]["parcela_id"], parcela_marco.id)
        self.assertTrue(rows_by_cpf["13131313131"]["pode_dar_baixa"])
        self.assertEqual(rows_by_cpf["14141414141"]["parcela_id"], None)
        self.assertTrue(rows_by_cpf["14141414141"]["pode_dar_baixa"])
        self.assertEqual(
            rows_by_cpf["14141414141"]["arquivo_retorno_item_id"],
            item_sem_parcela.id,
        )

    def test_lista_pendentes_inclui_retorno_sem_parcela_de_associado_inativo(self):
        associado_inativo = self._create_associado(
            cpf="17171717171",
            nome="Associado Inativo Sem Parcela",
            matricula="MAT-7171",
            agente=self.agente_a,
            status=Associado.Status.INATIVO,
        )
        arquivo = self._create_arquivo_retorno(
            competencia=date(2026, 3, 1),
            nome="Relatorio_D2102-03-2026.txt",
        )
        item = self._create_retorno_item(
            arquivo=arquivo,
            associado=associado_inativo,
            linha_numero=1,
            competencia="03/2026",
            valor="150.00",
            parcela=None,
        )

        response = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {"status": Parcela.Status.NAO_DESCONTADO, "competencia": "2026-03"},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        rows_by_cpf = {row["cpf_cnpj"]: row for row in payload["results"]}
        self.assertIn("17171717171", rows_by_cpf)
        self.assertEqual(rows_by_cpf["17171717171"]["parcela_id"], None)
        self.assertEqual(
            rows_by_cpf["17171717171"]["arquivo_retorno_item_id"],
            item.id,
        )
        self.assertTrue(rows_by_cpf["17171717171"]["pode_dar_baixa"])

    def test_lista_pendentes_inclui_parcela_nao_descontada_de_associado_inativo(self):
        associado_inativo = self._create_associado(
            cpf="18181818181",
            nome="Associado Inativo Materializado",
            matricula="MAT-8181",
            agente=self.agente_a,
        )
        parcela = self._create_parcela(
            associado=associado_inativo,
            agente=self.agente_a,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 10),
            status=Parcela.Status.NAO_DESCONTADO,
            valor="220.00",
            codigo="CTR-INATIVO-8181",
        )
        associado_inativo.status = Associado.Status.INATIVO
        associado_inativo.save(update_fields=["status", "updated_at"])
        parcela.refresh_from_db()

        response = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {"status": Parcela.Status.NAO_DESCONTADO, "competencia": "2026-03"},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        rows_by_cpf = {row["cpf_cnpj"]: row for row in payload["results"]}
        self.assertIn("18181818181", rows_by_cpf)
        self.assertEqual(rows_by_cpf["18181818181"]["parcela_id"], parcela.id)
        self.assertTrue(rows_by_cpf["18181818181"]["pode_dar_baixa"])

    def test_lista_pendentes_preserva_parcela_materializada_sem_item_no_retorno(self):
        associado_retorno = self._create_associado(
            cpf="15151515150",
            nome="Associado Retorno Parcela",
            matricula="MAT-5150",
            agente=self.agente_a,
        )
        parcela_retorno = self._create_parcela(
            associado=associado_retorno,
            agente=self.agente_a,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 10),
            status=Parcela.Status.NAO_DESCONTADO,
            valor="300.00",
            codigo="CTR-RET-MATCH",
        )

        associado_materializado = self._create_associado(
            cpf="16161616161",
            nome="Associado Materializado",
            matricula="MAT-6161",
            agente=self.agente_a,
        )
        parcela_materializada = self._create_parcela(
            associado=associado_materializado,
            agente=self.agente_a,
            referencia=date(2025, 10, 1),
            vencimento=date(2025, 10, 10),
            status=Parcela.Status.NAO_DESCONTADO,
            valor="150.00",
            codigo="CTR-RET-FALLBACK",
        )

        arquivo = self._create_arquivo_retorno(
            competencia=date(2026, 3, 1),
            nome="Relatorio_D2102-03-2026.txt",
        )
        self._create_retorno_item(
            arquivo=arquivo,
            associado=associado_retorno,
            linha_numero=1,
            competencia="03/2026",
            valor="300.00",
            parcela=parcela_retorno,
        )

        response = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {"status": Parcela.Status.NAO_DESCONTADO},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        referencias = {
            (item["cpf_cnpj"], item["referencia_mes"])
            for item in payload["results"]
        }
        self.assertIn(("15151515150", "2026-03-01"), referencias)
        self.assertIn(("16161616161", "2025-10-01"), referencias)
        row_by_cpf = {
            item["cpf_cnpj"]: item
            for item in payload["results"]
            if item["cpf_cnpj"] in {"15151515150", "16161616161"}
        }
        self.assertEqual(
            row_by_cpf["15151515150"]["parcela_id"],
            parcela_retorno.id,
        )
        self.assertEqual(
            row_by_cpf["16161616161"]["parcela_id"],
            parcela_materializada.id,
        )

    def test_inativar_associado_baixa_parcelas_vencidas(self):
        associado = self._create_associado(
            cpf="15151515151",
            nome="Associado Inativado",
            matricula="MAT-515",
            agente=self.agente_a,
        )
        parcela_outubro = self._create_parcela(
            associado=associado,
            agente=self.agente_a,
            referencia=date(2025, 10, 1),
            vencimento=date(2025, 10, 10),
            status=Parcela.Status.NAO_DESCONTADO,
            valor="200.00",
            codigo="CTR-INAT-515",
        )
        parcela_novembro = self._create_parcela(
            associado=associado,
            agente=self.agente_a,
            referencia=date(2025, 11, 1),
            vencimento=date(2025, 11, 10),
            status=Parcela.Status.EM_ABERTO,
            valor="300.00",
            codigo="CTR-INAT-516",
        )

        response = self.client.post(
            "/api/v1/tesouraria/baixa-manual/inativar-associado/",
            {
                "associado_id": str(associado.id),
                "observacao": "Baixa com inativação",
                "comprovante": SimpleUploadedFile(
                    "inativacao.pdf",
                    b"arquivo",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201, response.json())
        associado.refresh_from_db()
        parcela_outubro.refresh_from_db()
        parcela_novembro.refresh_from_db()

        self.assertEqual(associado.status, Associado.Status.INATIVO)
        self.assertEqual(parcela_outubro.status, Parcela.Status.DESCONTADO)
        self.assertEqual(parcela_novembro.status, Parcela.Status.DESCONTADO)
        self.assertEqual(BaixaManual.objects.filter(parcela=parcela_outubro).count(), 1)
        self.assertEqual(BaixaManual.objects.filter(parcela=parcela_novembro).count(), 1)
        self.assertEqual(response.json()["parcelas_baixadas"], 2)
        self.assertEqual(response.json()["total_baixado"], "500.00")

    def test_registrar_inadimplencia_manual_para_associado_inativo_mantem_status_e_entrar_na_fila(self):
        associado = self._create_associado(
            cpf="19191919191",
            nome="Associado Inativo Manual",
            matricula="MAT-9191",
            agente=self.agente_a,
        )
        parcela_base = self._create_parcela(
            associado=associado,
            agente=self.agente_a,
            referencia=date(2025, 10, 1),
            vencimento=date(2025, 10, 10),
            status=Parcela.Status.DESCONTADO,
            valor="210.00",
            codigo="CTR-MANUAL-INATIVO",
        )
        associado.status = Associado.Status.INATIVO
        associado.save(update_fields=["status", "updated_at"])
        parcela_base.ciclo.contrato.refresh_from_db()

        response = self.client.post(
            "/api/v1/tesouraria/baixa-manual/registrar-inadimplencia/",
            {
                "associado_id": associado.id,
                "referencia_mes": "2026-03-01",
                "data_vencimento": "2026-03-10",
                "valor": "180.00",
                "status": Parcela.Status.NAO_DESCONTADO,
                "observacao": "Gerada manualmente.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.json())
        associado.refresh_from_db()
        self.assertEqual(associado.status, Associado.Status.INATIVO)

        parcela_manual = Parcela.objects.get(pk=response.json()["parcela_id"])
        self.assertEqual(parcela_manual.status, Parcela.Status.NAO_DESCONTADO)
        self.assertEqual(parcela_manual.layout_bucket, Parcela.LayoutBucket.UNPAID)
        self.assertIsNone(parcela_manual.deleted_at)

        pending = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {"status": Parcela.Status.NAO_DESCONTADO, "competencia": "2026-03"},
        )
        self.assertEqual(pending.status_code, 200, pending.json())
        rows_by_cpf = {row["cpf_cnpj"]: row for row in pending.json()["results"]}
        self.assertIn("19191919191", rows_by_cpf)
        self.assertEqual(rows_by_cpf["19191919191"]["origem"], "manual")

    def test_registrar_inadimplencia_manual_pode_quitar_direto(self):
        associado = self._create_associado(
            cpf="20202020202",
            nome="Associado Quitacao Direta",
            matricula="MAT-2020",
            agente=self.agente_a,
        )
        self._create_parcela(
            associado=associado,
            agente=self.agente_a,
            referencia=date(2025, 10, 1),
            vencimento=date(2025, 10, 10),
            status=Parcela.Status.DESCONTADO,
            valor="200.00",
            codigo="CTR-MANUAL-QUITADO",
        )

        response = self.client.post(
            "/api/v1/tesouraria/baixa-manual/registrar-inadimplencia/",
            {
                "associado_id": str(associado.id),
                "referencia_mes": "2026-03-01",
                "data_vencimento": "2026-03-10",
                "valor": "200.00",
                "status": Parcela.Status.NAO_DESCONTADO,
                "observacao": "Registrar e quitar direto.",
                "quitar_direto": "true",
                "valor_pago": "200.00",
                "comprovante": SimpleUploadedFile(
                    "quitacao-direta.pdf",
                    b"arquivo",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201, response.json())
        parcela_manual = Parcela.objects.get(pk=response.json()["parcela_id"])
        self.assertEqual(parcela_manual.status, Parcela.Status.DESCONTADO)
        self.assertEqual(BaixaManual.objects.filter(parcela=parcela_manual).count(), 1)

        pending = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {"status": Parcela.Status.NAO_DESCONTADO, "competencia": "2026-03"},
        )
        self.assertEqual(pending.status_code, 200, pending.json())
        self.assertNotIn(
            "20202020202",
            {row["cpf_cnpj"] for row in pending.json()["results"]},
        )

        quitados = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {"listing": "quitados", "competencia": "2026-03"},
        )
        self.assertEqual(quitados.status_code, 200, quitados.json())
        self.assertIn(
            "20202020202",
            {row["cpf_cnpj"] for row in quitados.json()["results"]},
        )

    def test_descartar_inadimplencia_manual_remove_da_fila_e_do_detalhe_do_associado(self):
        associado = self._create_associado(
            cpf="21212121212",
            nome="Associado Descarte Manual",
            matricula="MAT-2121",
            agente=self.agente_a,
        )
        parcela_base = self._create_parcela(
            associado=associado,
            agente=self.agente_a,
            referencia=date(2025, 10, 1),
            vencimento=date(2025, 10, 10),
            status=Parcela.Status.DESCONTADO,
            valor="205.00",
            codigo="CTR-DESCARTE-MANUAL",
        )
        contrato = parcela_base.ciclo.contrato

        registrar = self.client.post(
            "/api/v1/tesouraria/baixa-manual/registrar-inadimplencia/",
            {
                "associado_id": associado.id,
                "referencia_mes": "2026-03-01",
                "data_vencimento": "2026-03-10",
                "valor": "205.00",
                "status": Parcela.Status.NAO_DESCONTADO,
                "observacao": "Linha manual para descarte.",
            },
            format="json",
        )
        self.assertEqual(registrar.status_code, 201, registrar.json())
        parcela_manual = Parcela.all_objects.get(pk=registrar.json()["parcela_id"])

        response = self.client.post(
            f"/api/v1/tesouraria/baixa-manual/{parcela_manual.id}/descartar/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        parcela_manual.refresh_from_db()
        self.assertIsNotNone(parcela_manual.deleted_at)
        self.assertEqual(parcela_manual.status, Parcela.Status.CANCELADO)

        pending = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {"status": Parcela.Status.NAO_DESCONTADO, "competencia": "2026-03"},
        )
        self.assertEqual(pending.status_code, 200, pending.json())
        self.assertNotIn(
            parcela_manual.id,
            {row["parcela_id"] for row in pending.json()["results"]},
        )

        projection = build_contract_cycle_projection(contrato)
        self.assertNotIn(
            date(2026, 3, 1),
            [item["referencia_mes"] for item in projection["unpaid_months"]],
        )

    def test_lista_quitados_filtra_por_agente_data_e_search(self):
        parcela_match = self._create_parcela(
            associado=self._create_associado(
                cpf="33333333333",
                nome="Associado Quitado",
                matricula="MAT-333",
                agente=self.agente_a,
            ),
            agente=self.agente_a,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 10),
            status=Parcela.Status.DESCONTADO,
            codigo="CTR-QUIT-333",
        )
        baixa_match = BaixaManual.objects.create(
            parcela=parcela_match,
            realizado_por=self.tesoureiro,
            comprovante=SimpleUploadedFile(
                "comprovante.pdf",
                b"arquivo",
                content_type="application/pdf",
            ),
            nome_comprovante="comprovante.pdf",
            observacao="Quitado manualmente",
            valor_pago=Decimal("200.00"),
            data_baixa=date(2026, 4, 2),
        )

        parcela_outro = self._create_parcela(
            associado=self._create_associado(
                cpf="44444444444",
                nome="Associado Fora do Filtro",
                matricula="MAT-444",
                agente=self.agente_b,
            ),
            agente=self.agente_b,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 11),
            status=Parcela.Status.DESCONTADO,
            codigo="CTR-QUIT-444",
        )
        BaixaManual.objects.create(
            parcela=parcela_outro,
            realizado_por=self.tesoureiro,
            comprovante=SimpleUploadedFile(
                "comprovante-2.pdf",
                b"arquivo",
                content_type="application/pdf",
            ),
            nome_comprovante="comprovante-2.pdf",
            observacao="Baixa fora do agente",
            valor_pago=Decimal("200.00"),
            data_baixa=date(2026, 4, 5),
        )

        response = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {
                "listing": "quitados",
                "agente": str(self.agente_a.id),
                "data_inicio": "2026-04-01",
                "data_fim": "2026-04-30",
                "search": "MAT-333",
            },
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], baixa_match.id)
        self.assertEqual(payload["results"][0]["parcela_id"], parcela_match.id)
        self.assertEqual(payload["results"][0]["data_baixa"], "2026-04-02")
        self.assertEqual(payload["results"][0]["valor_pago"], "200.00")
        self.assertEqual(payload["results"][0]["realizado_por_nome"], "Tesouraria ABASE")
        self.assertEqual(payload["kpis"]["total_quitados"], 1)
        self.assertEqual(payload["kpis"]["valor_total_quitado"], "200.00")

    def test_dar_baixa_permita_item_retorno_sem_parcela_vinculada(self):
        associado = self._create_associado(
            cpf="99999999999",
            nome="Associado Sem Parcela",
            matricula="MAT-999",
            agente=self.agente_a,
        )
        arquivo = self._create_arquivo_retorno(competencia=date(2026, 3, 1))
        item = self._create_retorno_item(
            arquivo=arquivo,
            associado=associado,
            linha_numero=7,
            competencia="03/2026",
            valor="180.00",
            parcela=None,
        )

        response = self.client.post(
            f"/api/v1/tesouraria/baixa-manual/{-item.id}/dar-baixa/",
            {
                "observacao": "Quitado sem parcela materializada",
                "valor_pago": "180.00",
                "comprovante": SimpleUploadedFile(
                    "manual.pdf",
                    b"arquivo-manual",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201, response.json())
        item.refresh_from_db()
        pagamento = PagamentoMensalidade.objects.get(
            associado=associado,
            referencia_month=date(2026, 3, 1),
        )
        self.assertEqual(item.resultado_processamento, ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        self.assertEqual(pagamento.manual_status, PagamentoMensalidade.ManualStatus.PAGO)
        self.assertEqual(pagamento.recebido_manual, Decimal("180.00"))
        self.assertEqual(pagamento.status_code, "M")
        self.assertTrue(pagamento.manual_comprovante_path.endswith(".pdf"))

    def test_lista_quitados_inclui_quitacao_manual_sem_parcela(self):
        associado = self._create_associado(
            cpf="88888888888",
            nome="Quitado Sem Parcela",
            matricula="MAT-888",
            agente=self.agente_a,
        )
        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="manual-quitado-888",
            referencia_month=date(2026, 3, 1),
            status_code="M",
            matricula=associado.matricula_orgao,
            orgao_pagto="SEFAZ",
            nome_relatorio=associado.nome_completo,
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=Decimal("210.00"),
            recebido_manual=Decimal("210.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=datetime(2026, 4, 8, 12, 0, 0),
            manual_forma_pagamento="baixa_manual",
            manual_comprovante_path="baixas_manuais/manual-quitado.pdf",
            manual_by=self.tesoureiro,
            source_file_path="manual/baixa-manual",
        )

        response = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {
                "listing": "quitados",
                "agente": str(self.agente_a.id),
                "data_inicio": "2026-04-01",
                "data_fim": "2026-04-30",
                "search": "MAT-888",
            },
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertIsNone(payload["results"][0]["parcela_id"])
        self.assertEqual(payload["results"][0]["origem"], "pagamento_manual")
        self.assertEqual(payload["results"][0]["valor_pago"], "210.00")
        self.assertEqual(payload["results"][0]["nome_comprovante"], "manual-quitado.pdf")
        self.assertEqual(payload["kpis"]["total_quitados"], 1)
        self.assertEqual(payload["kpis"]["valor_total_quitado"], "210.00")
