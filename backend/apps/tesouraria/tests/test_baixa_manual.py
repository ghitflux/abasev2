from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem
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

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.tesoureiro)

    def _create_associado(
        self,
        *,
        cpf: str,
        nome: str,
        matricula: str,
        agente: User,
    ) -> Associado:
        return Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula=matricula,
            matricula_orgao=matricula,
            status=Associado.Status.ATIVO,
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
        self.assertFalse(rows_by_cpf["14141414141"]["pode_dar_baixa"])
        self.assertEqual(
            rows_by_cpf["14141414141"]["arquivo_retorno_item_id"],
            item_sem_parcela.id,
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
