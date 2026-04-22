from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado, Documento
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import EsteiraItem, Pendencia
from apps.importacao.models import PagamentoMensalidade
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.initial_payment import InitialPaymentPayload
from apps.tesouraria.models import Confirmacao
from apps.tesouraria.serializers import TesourariaContratoListSerializer


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TestFluxoCompleto(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.role_analista = Role.objects.create(codigo="ANALISTA", nome="Analista")
        cls.role_coord = Role.objects.create(codigo="COORDENADOR", nome="Coordenador")
        cls.role_tes = Role.objects.create(codigo="TESOUREIRO", nome="Tesoureiro")

        cls.admin = cls._create_user("admin@abase.local", cls.role_admin, "Admin")
        cls.agente = cls._create_user("agente@abase.local", cls.role_agente, "Agente")
        cls.analista = cls._create_user(
            "analista@abase.local", cls.role_analista, "Analista"
        )
        cls.coordenador = cls._create_user(
            "coord@abase.local", cls.role_coord, "Coordenador"
        )
        cls.tesoureiro = cls._create_user(
            "tes@abase.local", cls.role_tes, "Tesoureiro"
        )

    @classmethod
    def _create_user(cls, email: str, role: Role, first_name: str) -> User:
        user = User.objects.create_user(
            email=email,
            password="Senha@123",
            first_name=first_name,
            last_name="ABASE",
            is_active=True,
        )
        user.roles.add(role)
        return user

    def setUp(self):
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)

        self.agent_client = APIClient()
        self.agent_client.force_authenticate(self.agente)

        self.analyst_client = APIClient()
        self.analyst_client.force_authenticate(self.analista)

        self.coord_client = APIClient()
        self.coord_client.force_authenticate(self.coordenador)

        self.tes_client = APIClient()
        self.tes_client.force_authenticate(self.tesoureiro)

    def _cadastro_payload(
        self,
        cpf: str = "12345678901",
        *,
        data_aprovacao: str | None = None,
        mensalidade: str = "500.00",
    ):
        payload = {
            "tipo_documento": "CPF",
            "cpf_cnpj": cpf,
            "nome_completo": "Associado Teste",
            "rg": "1234567",
            "orgao_expedidor": "SSP",
            "profissao": "Servidor",
            "estado_civil": "solteiro",
            "cargo": "Analista",
            "endereco": {
                "cep": "64000000",
                "endereco": "Rua Teste",
                "numero": "100",
                "complemento": "",
                "bairro": "Centro",
                "cidade": "Teresina",
                "uf": "PI",
            },
            "dados_bancarios": {
                "banco": "Banco do Brasil",
                "agencia": "1234",
                "conta": "98765-0",
                "tipo_conta": "corrente",
                "chave_pix": "pix@teste.com",
            },
            "contato": {
                "celular": "86999999999",
                "email": "associado@teste.com",
                "orgao_publico": "SEFAZ",
                "situacao_servidor": "ativo",
                "matricula_servidor": "MAT-ORG-1",
            },
            "agente_responsavel_id": self.agente.id,
            "valor_bruto_total": "1500.00",
            "valor_liquido": "1200.00",
            "prazo_meses": 3,
            "taxa_antecipacao": "1.50",
            "mensalidade": mensalidade,
            "margem_disponivel": "900.00",
        }
        if data_aprovacao:
            payload["data_aprovacao"] = data_aprovacao
        return payload

    def _criar_associado(
        self,
        cpf: str = "12345678901",
        *,
        data_aprovacao: str | None = None,
        mensalidade: str = "500.00",
    ) -> Associado:
        response = self.admin_client.post(
            "/api/v1/associados/",
            self._cadastro_payload(
                cpf,
                data_aprovacao=data_aprovacao,
                mensalidade=mensalidade,
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        associado = Associado.objects.get(cpf_cnpj=cpf)
        associado.agente_responsavel = self.agente
        associado.save(update_fields=["agente_responsavel"])

        contrato = associado.contratos.get()
        contrato.agente = self.agente
        contrato.save(update_fields=["agente"])

        return associado

    def _levar_para_tesouraria(self, associado: Associado) -> Contrato:
        esteira = associado.esteira_item

        response = self.analyst_client.post(f"/api/v1/esteira/{esteira.id}/assumir/")
        self.assertEqual(response.status_code, 200, response.json())
        response = self.analyst_client.post(f"/api/v1/esteira/{esteira.id}/aprovar/", {"observacao": "Ok"}, format="json")
        self.assertEqual(response.status_code, 200, response.json())

        esteira.refresh_from_db()
        self.assertEqual(esteira.etapa_atual, EsteiraItem.Etapa.TESOURARIA)
        self.assertEqual(esteira.status, EsteiraItem.Situacao.AGUARDANDO)

        return associado.contratos.get()

    def test_aprovacao_do_analista_envia_cadastro_para_tesouraria(self):
        associado = self._criar_associado("17345678901")
        esteira = associado.esteira_item

        response = self.analyst_client.post(f"/api/v1/esteira/{esteira.id}/assumir/")
        self.assertEqual(response.status_code, 200, response.json())

        response = self.analyst_client.post(f"/api/v1/esteira/{esteira.id}/aprovar/", format="json")
        self.assertEqual(response.status_code, 200, response.json())

        esteira.refresh_from_db()
        self.assertEqual(esteira.etapa_atual, EsteiraItem.Etapa.TESOURARIA)
        self.assertEqual(esteira.status, EsteiraItem.Situacao.AGUARDANDO)

    def test_aprovacao_do_analista_aprova_documentos_anexados(self):
        associado = self._criar_associado("17345678902")
        Documento.objects.create(
            associado=associado,
            tipo=Documento.Tipo.CONTRACHEQUE,
            arquivo=SimpleUploadedFile(
                "contracheque.pdf",
                b"arquivo",
                content_type="application/pdf",
            ),
            status=Documento.Status.PENDENTE,
        )
        esteira = associado.esteira_item

        response = self.analyst_client.post(f"/api/v1/esteira/{esteira.id}/assumir/")
        self.assertEqual(response.status_code, 200, response.json())
        response = self.analyst_client.post(f"/api/v1/esteira/{esteira.id}/aprovar/", format="json")
        self.assertEqual(response.status_code, 200, response.json())

        self.assertEqual(
            associado.documentos.filter(status=Documento.Status.APROVADO).count(),
            1,
        )

    def test_tesouraria_lista_pendentes_mesmo_com_primeiro_ciclo_em_competencia_futura(self):
        associado = self._criar_associado(
            "17345678903",
            data_aprovacao="2026-03-11",
        )
        contrato = associado.contratos.get()
        self._levar_para_tesouraria(associado)

        response = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {"competencia": "2026-03", "pagamento": "pendente"},
        )
        self.assertEqual(response.status_code, 200, response.json())

        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(contrato.id, ids)

    def test_tesouraria_filtra_periodo_pela_data_de_solicitacao_da_fila(self):
        associado_no_recorte = self._criar_associado("17345678930")
        contrato_no_recorte = self._levar_para_tesouraria(associado_no_recorte)
        Contrato.objects.filter(pk=contrato_no_recorte.pk).update(
            created_at=timezone.make_aware(datetime(2026, 4, 10, 9, 30)),
            data_contrato=date(2025, 12, 15),
        )

        associado_fora_recorte = self._criar_associado("17345678931")
        contrato_fora_recorte = self._levar_para_tesouraria(associado_fora_recorte)
        Contrato.objects.filter(pk=contrato_fora_recorte.pk).update(
            created_at=timezone.make_aware(datetime(2026, 3, 25, 14, 0)),
            data_contrato=date(2026, 4, 12),
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {
                "competencia": "2026-04",
                "pagamento": "pendente",
                "data_inicio": "2026-04-01",
                "data_fim": "2026-04-30",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())

        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(contrato_no_recorte.id, ids)
        self.assertNotIn(contrato_fora_recorte.id, ids)

    def test_tesouraria_lista_efetivado_mesmo_sem_mover_esteira_para_concluido(self):
        associado = self._criar_associado("17345678932")
        contrato = self._levar_para_tesouraria(associado)
        contrato.status = Contrato.Status.ATIVO
        contrato.auxilio_liberado_em = date(2026, 4, 12)
        contrato.save(update_fields=["status", "auxilio_liberado_em", "updated_at"])

        response = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {"competencia": "2026-04", "pagamento": "concluido"},
        )
        self.assertEqual(response.status_code, 200, response.json())
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(contrato.id, ids)

        response = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {"competencia": "2026-04", "pagamento": "pendente"},
        )
        self.assertEqual(response.status_code, 200, response.json())
        ids = {row["id"] for row in response.json()["results"]}
        self.assertNotIn(contrato.id, ids)

    def test_tesouraria_separa_concluidos_e_cancelados(self):
        associado_pago = self._criar_associado("17345678904")
        contrato_pago = self._levar_para_tesouraria(associado_pago)
        self._efetivar_contrato(contrato_pago)

        associado_cancelado = self._criar_associado("17345678905")
        contrato_cancelado = self._levar_para_tesouraria(associado_cancelado)
        contrato_cancelado.status = Contrato.Status.CANCELADO
        contrato_cancelado.cancelado_em = timezone.now()
        contrato_cancelado.save(update_fields=["status", "cancelado_em", "updated_at"])

        competencia = timezone.localdate().strftime("%Y-%m")

        response_concluido = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {"competencia": competencia, "pagamento": "concluido"},
        )
        self.assertEqual(response_concluido.status_code, 200, response_concluido.json())

        payload_concluido = response_concluido.json()["results"]
        ids_concluidos = {row["id"] for row in payload_concluido}
        self.assertIn(contrato_pago.id, ids_concluidos)
        self.assertNotIn(contrato_cancelado.id, ids_concluidos)
        contrato_pago_row = next(row for row in payload_concluido if row["id"] == contrato_pago.id)
        self.assertEqual(contrato_pago_row["status"], "concluido")
        self.assertEqual(contrato_pago_row["comissao_agente"], "105.00")

        response_cancelado = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {"competencia": competencia, "pagamento": "cancelado"},
        )
        self.assertEqual(response_cancelado.status_code, 200, response_cancelado.json())

        payload_cancelado = response_cancelado.json()["results"]
        ids_cancelados = {row["id"] for row in payload_cancelado}
        self.assertIn(contrato_cancelado.id, ids_cancelados)
        self.assertNotIn(contrato_pago.id, ids_cancelados)
        contrato_cancelado_row = next(
            row for row in payload_cancelado if row["id"] == contrato_cancelado.id
        )
        self.assertEqual(contrato_cancelado_row["status"], "cancelado")

    def test_tesouraria_periodo_explicito_sobrepoe_competencia_para_concluidos(self):
        associado_pago = self._criar_associado("17345678940")
        contrato_pago = self._levar_para_tesouraria(associado_pago)
        self._efetivar_contrato(contrato_pago)
        Contrato.objects.filter(pk=contrato_pago.pk).update(
            created_at=timezone.make_aware(datetime(2025, 11, 4, 16, 0)),
            auxilio_liberado_em=date(2025, 11, 4),
        )

        response_sem_periodo = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {"competencia": "2026-04", "pagamento": "concluido"},
        )
        self.assertEqual(response_sem_periodo.status_code, 200, response_sem_periodo.json())
        ids_sem_periodo = {row["id"] for row in response_sem_periodo.json()["results"]}
        self.assertNotIn(contrato_pago.id, ids_sem_periodo)

        response_com_periodo = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {
                "competencia": "2026-04",
                "pagamento": "concluido",
                "data_inicio": "2025-11-01",
                "data_fim": "2025-11-30",
            },
        )
        self.assertEqual(response_com_periodo.status_code, 200, response_com_periodo.json())
        ids_com_periodo = {row["id"] for row in response_com_periodo.json()["results"]}
        self.assertIn(contrato_pago.id, ids_com_periodo)

    def test_tesouraria_sem_competencia_lista_concluidos_historicos(self):
        associado_pago = self._criar_associado("17345678941")
        contrato_pago = self._levar_para_tesouraria(associado_pago)
        self._efetivar_contrato(contrato_pago)
        Contrato.objects.filter(pk=contrato_pago.pk).update(
            created_at=timezone.make_aware(datetime(2025, 11, 7, 10, 0)),
            auxilio_liberado_em=date(2025, 11, 7),
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {"pagamento": "concluido"},
        )
        self.assertEqual(response.status_code, 200, response.json())
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(contrato_pago.id, ids)

    def test_tesouraria_serializer_expoe_evidencias_canonicas_nos_comprovantes(self):
        associado = self._criar_associado("17345678942")
        contrato = self._levar_para_tesouraria(associado)

        payload = InitialPaymentPayload(
            status="pago",
            status_label="Pago",
            valor=Decimal("120.00"),
            paid_at=timezone.now(),
            evidencia_status="arquivo_local",
            evidencias=[
                {
                    "id": "legacy-associado",
                    "nome": "comprovante-associado.pdf",
                    "url": "/media/tesouraria/comprovante-associado.pdf",
                    "arquivo_referencia": "tesouraria/comprovante-associado.pdf",
                    "arquivo_disponivel_localmente": True,
                    "tipo_referencia": "local",
                    "origem": "legado",
                    "papel": "associado",
                    "tipo": "comprovante_pagamento_associado",
                    "status": "pago",
                    "competencia": None,
                    "created_at": timezone.now(),
                },
                {
                    "id": "legacy-agente",
                    "nome": "comprovante-agente.pdf",
                    "url": "/media/tesouraria/comprovante-agente.pdf",
                    "arquivo_referencia": "tesouraria/comprovante-agente.pdf",
                    "arquivo_disponivel_localmente": True,
                    "tipo_referencia": "local",
                    "origem": "legado",
                    "papel": "agente",
                    "tipo": "comprovante_pagamento_agente",
                    "status": "pago",
                    "competencia": None,
                    "created_at": timezone.now(),
                },
            ],
        )

        with patch(
            "apps.tesouraria.serializers.build_initial_payment_payload",
            return_value=payload,
        ):
            row = TesourariaContratoListSerializer(contrato).data

        self.assertEqual(len(row["comprovantes"]), 2)
        self.assertEqual(row["comprovantes"][0]["arquivo"], "/media/tesouraria/comprovante-associado.pdf")
        self.assertEqual(row["comprovantes"][0]["nome_original"], "comprovante-associado.pdf")
        self.assertTrue(row["comprovantes"][0]["arquivo_disponivel_localmente"])
        self.assertEqual(row["comprovantes"][1]["papel"], "agente")

    def test_tesouraria_retorna_matricula_e_percentual_repasse_na_listagem(self):
        associado = self._criar_associado("17345678906")
        associado.matricula_orgao = ""
        associado.matricula = "MAT-LEGACY-99"
        associado.auxilio_taxa = Decimal("12.50")
        associado.save(update_fields=["matricula_orgao", "matricula", "auxilio_taxa", "updated_at"])
        contrato = self._levar_para_tesouraria(associado)

        response = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {"competencia": timezone.localdate().strftime("%Y-%m"), "pagamento": "pendente"},
        )
        self.assertEqual(response.status_code, 200, response.json())

        row = next(item for item in response.json()["results"] if item["id"] == contrato.id)
        self.assertEqual(row["matricula"], "MAT-LEGACY-99")
        self.assertEqual(row["percentual_repasse"], "12.50")

    def test_tesouraria_lista_usuarios_do_filtro_agente_com_responsaveis_de_outros_papeis(self):
        associado_agente = self._criar_associado("17345678960")
        self._levar_para_tesouraria(associado_agente)

        associado_coord = self._criar_associado("17345678961")
        associado_coord.agente_responsavel = self.coordenador
        associado_coord.save(update_fields=["agente_responsavel", "updated_at"])
        contrato_coord = self._levar_para_tesouraria(associado_coord)
        Contrato.objects.filter(pk=contrato_coord.pk).update(agente=None)

        response_agentes = self.tes_client.get("/api/v1/tesouraria/contratos/agentes/")
        self.assertEqual(response_agentes.status_code, 200, response_agentes.json())

        payload = response_agentes.json()
        ids = {item["id"] for item in payload}
        self.assertIn(self.agente.id, ids)
        self.assertIn(self.coordenador.id, ids)

        response_filtrado = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {
                "pagamento": "pendente",
                "agente": str(self.coordenador.id),
            },
        )
        self.assertEqual(response_filtrado.status_code, 200, response_filtrado.json())
        ids_filtrados = {row["id"] for row in response_filtrado.json()["results"]}
        self.assertIn(contrato_coord.id, ids_filtrados)

    def test_tesouraria_filtra_status_congelado(self):
        associado_congelado = self._criar_associado("17345678962")
        contrato_congelado = self._levar_para_tesouraria(associado_congelado)
        response_congelar = self.tes_client.post(
            f"/api/v1/tesouraria/contratos/{contrato_congelado.id}/congelar/",
            {"motivo": "Aguardando correção documental."},
            format="json",
        )
        self.assertEqual(response_congelar.status_code, 200, response_congelar.json())

        associado_aberto = self._criar_associado("17345678963")
        contrato_aberto = self._levar_para_tesouraria(associado_aberto)

        response = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {
                "pagamento": "pendente",
                "status_contrato": "congelado",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())

        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(contrato_congelado.id, ids)
        self.assertNotIn(contrato_aberto.id, ids)

    def test_tesouraria_pode_devolver_contrato_para_analise(self):
        associado = self._criar_associado("17345678964")
        contrato = self._levar_para_tesouraria(associado)

        response = self.tes_client.post(
            f"/api/v1/tesouraria/contratos/{contrato.id}/pendenciar/",
            {
                "tipo": "tesouraria",
                "descricao": "Revisar anexos e validar a divergência antes da efetivação.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        esteira = associado.esteira_item
        esteira.refresh_from_db()
        pendencia = Pendencia.objects.get(esteira_item=esteira)

        self.assertEqual(esteira.etapa_atual, EsteiraItem.Etapa.ANALISE)
        self.assertEqual(esteira.status, EsteiraItem.Situacao.PENDENCIADO)
        self.assertFalse(pendencia.retornado_para_agente)
        self.assertEqual(pendencia.tipo, "tesouraria")

    def test_tesouraria_pode_devolver_reativacao_para_analise(self):
        associado = self._criar_associado("17345678965")
        contrato = associado.contratos.get()
        contrato.origem_operacional = Contrato.OrigemOperacional.REATIVACAO
        contrato.save(update_fields=["origem_operacional", "updated_at"])
        contrato = self._levar_para_tesouraria(associado)

        response = self.tes_client.post(
            f"/api/v1/tesouraria/contratos/{contrato.id}/pendenciar/",
            {
                "tipo": "tesouraria",
                "descricao": "Reativação voltou para análise para ajuste documental.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        esteira = associado.esteira_item
        esteira.refresh_from_db()

        self.assertEqual(esteira.etapa_atual, EsteiraItem.Etapa.ANALISE)
        self.assertEqual(esteira.status, EsteiraItem.Situacao.PENDENCIADO)

    def test_tesouraria_pode_cancelar_contrato_e_listar_liquidado_com_alias_visual(self):
        associado_cancelado = self._criar_associado("17345678907")
        contrato_cancelado = self._levar_para_tesouraria(associado_cancelado)

        cancelamento = self.tes_client.post(
            f"/api/v1/tesouraria/contratos/{contrato_cancelado.id}/cancelar/",
            {
                "tipo": "desistente",
                "motivo": "Cliente desistiu antes da ativação.",
            },
            format="json",
        )
        self.assertEqual(cancelamento.status_code, 200, cancelamento.json())
        contrato_cancelado.refresh_from_db()
        self.assertEqual(contrato_cancelado.status, Contrato.Status.CANCELADO)
        self.assertEqual(contrato_cancelado.cancelamento_tipo, "desistente")

        associado_liquidado = self._criar_associado("17345678908")
        contrato_liquidado = self._levar_para_tesouraria(associado_liquidado)
        contrato_liquidado.status = Contrato.Status.ENCERRADO
        contrato_liquidado.save(update_fields=["status", "updated_at"])

        competencia = timezone.localdate().strftime("%Y-%m")
        response = self.tes_client.get(
            "/api/v1/tesouraria/contratos/",
            {"competencia": competencia, "pagamento": "liquidado"},
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()["results"]
        row = next(item for item in payload if item["id"] == contrato_liquidado.id)
        self.assertEqual(row["status"], "liquidado")

    def _efetivar_contrato(self, contrato: Contrato):
        response = self.tes_client.post(
            f"/api/v1/tesouraria/contratos/{contrato.id}/efetivar/",
            {
                "comprovante_associado": SimpleUploadedFile(
                    "associado.pdf", b"comprovante associado", content_type="application/pdf"
                ),
                "comprovante_agente": SimpleUploadedFile(
                    "agente.pdf", b"comprovante agente", content_type="application/pdf"
                ),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.json())

    def _registrar_pagamentos_refinanciamento(
        self, contrato: Contrato, referencias: list[date]
    ):
        for referencia in referencias:
            PagamentoMensalidade.objects.create(
                created_by=self.admin,
                import_uuid=f"teste-{contrato.id}-{referencia.isoformat()}",
                referencia_month=referencia,
                status_code="1",
                matricula=contrato.associado.matricula_orgao or contrato.associado.matricula,
                orgao_pagto=contrato.associado.orgao_publico,
                nome_relatorio=contrato.associado.nome_completo,
                cpf_cnpj=contrato.associado.cpf_cnpj,
                associado=contrato.associado,
                valor=contrato.valor_mensalidade,
                source_file_path=f"retornos/{referencia.strftime('%Y-%m')}.txt",
            )

    def test_fluxo_cadastro_ate_efetivacao(self):
        associado = self._criar_associado()
        contrato = self._levar_para_tesouraria(associado)

        self._efetivar_contrato(contrato)

        contrato.refresh_from_db()
        associado.refresh_from_db()
        esteira = associado.esteira_item
        ciclo = contrato.ciclos.get()

        self.assertEqual(contrato.status, Contrato.Status.ATIVO)
        self.assertEqual(associado.status, Associado.Status.ATIVO)
        self.assertEqual(esteira.etapa_atual, EsteiraItem.Etapa.CONCLUIDO)
        self.assertEqual(ciclo.status, Ciclo.Status.ABERTO)
        self.assertEqual(
            Comprovante.objects.filter(contrato=contrato, refinanciamento__isnull=True).count(),
            2,
        )

    def test_pendenciamento_e_retorno(self):
        associado = self._criar_associado("22345678901")
        esteira = associado.esteira_item

        response = self.analyst_client.post(f"/api/v1/esteira/{esteira.id}/assumir/")
        self.assertEqual(response.status_code, 200, response.json())
        response = self.analyst_client.post(
            f"/api/v1/esteira/{esteira.id}/pendenciar/",
            {"tipo": "documentacao", "descricao": "Falta documento."},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())

        response = self.agent_client.post(f"/api/v1/esteira/{esteira.id}/validar-documento/")
        self.assertEqual(response.status_code, 200, response.json())

        esteira.refresh_from_db()
        pendencia = Pendencia.objects.get(esteira_item=esteira)

        self.assertEqual(esteira.etapa_atual, EsteiraItem.Etapa.ANALISE)
        self.assertEqual(esteira.status, EsteiraItem.Situacao.AGUARDANDO)
        self.assertEqual(pendencia.status, Pendencia.Status.RESOLVIDA)

    def test_refinanciamento_completo(self):
        associado = self._criar_associado("32345678901")
        contrato = self._levar_para_tesouraria(associado)
        self._efetivar_contrato(contrato)

        ciclo = contrato.ciclos.get()
        ciclo.parcelas.update(status=Parcela.Status.DESCONTADO, data_pagamento=timezone.localdate())
        self._registrar_pagamentos_refinanciamento(
            contrato,
            list(ciclo.parcelas.order_by("numero").values_list("referencia_mes", flat=True)),
        )

        response = self.agent_client.post(f"/api/v1/refinanciamentos/{contrato.id}/solicitar/")
        self.assertEqual(response.status_code, 201, response.json())
        refinanciamento_id = response.json()["id"]

        response = self.coord_client.post(f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar/")
        self.assertEqual(response.status_code, 200, response.json())

        refinanciamento = Refinanciamento.objects.get(pk=refinanciamento_id)
        refinanciamento.refresh_from_db()

        self.assertEqual(refinanciamento.status, Refinanciamento.Status.CONCLUIDO)
        self.assertIsNotNone(refinanciamento.ciclo_destino)
        self.assertEqual(refinanciamento.ciclo_destino.status, Ciclo.Status.FUTURO)
        self.assertEqual(refinanciamento.ciclo_destino.parcelas.count(), 3)

        response = self.admin_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/efetivar/",
            {
                "comprovante_associado": SimpleUploadedFile(
                    "associado-refi.pdf",
                    b"comprovante associado",
                    content_type="application/pdf",
                ),
                "comprovante_agente": SimpleUploadedFile(
                    "agente-refi.pdf",
                    b"comprovante agente",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.json())

        refinanciamento.refresh_from_db()
        self.assertEqual(refinanciamento.status, Refinanciamento.Status.EFETIVADO)
        self.assertEqual(refinanciamento.ciclo_destino.status, Ciclo.Status.ABERTO)

    def test_refinanciamento_bloqueado_cpf_duplicado(self):
        associado = self._criar_associado("42345678901")
        contrato = self._levar_para_tesouraria(associado)
        self._efetivar_contrato(contrato)

        contrato.ciclos.get().parcelas.update(
            status=Parcela.Status.DESCONTADO,
            data_pagamento=timezone.localdate(),
        )
        self._registrar_pagamentos_refinanciamento(
            contrato,
            list(
                contrato.ciclos.get()
                .parcelas.order_by("numero")
                .values_list("referencia_mes", flat=True)
            ),
        )

        response = self.agent_client.post(f"/api/v1/refinanciamentos/{contrato.id}/solicitar/")
        self.assertEqual(response.status_code, 201, response.json())

        response = self.agent_client.post(f"/api/v1/refinanciamentos/{contrato.id}/solicitar/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("CPF já possui refinanciamento ativo", " ".join(response.json()))

    def test_efetivacao_sem_comprovante_do_agente_falha(self):
        associado = self._criar_associado("52345678901")
        status_inicial = associado.status
        contrato = self._levar_para_tesouraria(associado)

        response = self.tes_client.post(
            f"/api/v1/tesouraria/contratos/{contrato.id}/efetivar/",
            {
                "comprovante_associado": SimpleUploadedFile(
                    "associado.pdf", b"arquivo", content_type="application/pdf"
                )
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400, response.json())
        self.assertEqual(
            response.json()["comprovante_agente"][0],
            "O comprovante do agente é obrigatório para efetivar o contrato.",
        )
        contrato.refresh_from_db()
        associado.refresh_from_db()
        self.assertNotEqual(contrato.status, Contrato.Status.ATIVO)
        self.assertIsNone(contrato.auxilio_liberado_em)
        self.assertEqual(associado.status, status_inicial)
        comprovantes = {
            comprovante.papel: comprovante
            for comprovante in contrato.comprovantes.filter(
                refinanciamento__isnull=True,
                deleted_at__isnull=True,
            )
        }
        self.assertNotIn(Comprovante.Papel.ASSOCIADO, comprovantes)
        self.assertNotIn(Comprovante.Papel.AGENTE, comprovantes)

    def test_substituir_comprovante_nao_efetiva_sem_acao_explicita(self):
        associado = self._criar_associado("52345678911")
        status_inicial = associado.status
        contrato = self._levar_para_tesouraria(associado)

        response = self.tes_client.post(
            f"/api/v1/tesouraria/contratos/{contrato.id}/substituir-comprovante/",
            {
                "papel": Comprovante.Papel.ASSOCIADO,
                "arquivo": SimpleUploadedFile(
                    "associado.pdf",
                    b"arquivo",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.json())

        contrato.refresh_from_db()
        associado.refresh_from_db()
        self.assertNotEqual(contrato.status, Contrato.Status.ATIVO)
        self.assertIsNone(contrato.auxilio_liberado_em)
        self.assertEqual(associado.status, status_inicial)
        self.assertEqual(
            contrato.comprovantes.filter(
                refinanciamento__isnull=True,
                deleted_at__isnull=True,
            ).count(),
            1,
        )

    def test_efetivacao_com_comprovantes_ja_anexados_exige_acao_explicita(self):
        associado = self._criar_associado("52345678912")
        status_inicial = associado.status
        contrato = self._levar_para_tesouraria(associado)

        for papel in [Comprovante.Papel.ASSOCIADO, Comprovante.Papel.AGENTE]:
            response = self.tes_client.post(
                f"/api/v1/tesouraria/contratos/{contrato.id}/substituir-comprovante/",
                {
                    "papel": papel,
                    "arquivo": SimpleUploadedFile(
                        f"{papel}.pdf",
                        b"arquivo",
                        content_type="application/pdf",
                    ),
                },
                format="multipart",
            )
            self.assertEqual(response.status_code, 200, response.json())

        contrato.refresh_from_db()
        associado.refresh_from_db()
        self.assertNotEqual(contrato.status, Contrato.Status.ATIVO)
        self.assertEqual(associado.status, status_inicial)

        efetivar = self.tes_client.post(
            f"/api/v1/tesouraria/contratos/{contrato.id}/efetivar/",
            {},
            format="json",
        )
        self.assertEqual(efetivar.status_code, 200, efetivar.json())

        contrato.refresh_from_db()
        associado.refresh_from_db()
        self.assertEqual(contrato.status, Contrato.Status.ATIVO)
        self.assertIsNotNone(contrato.auxilio_liberado_em)
        self.assertEqual(associado.status, Associado.Status.ATIVO)

    def test_confirmacao_sequencial(self):
        associado = self._criar_associado("62345678901")
        contrato = self._levar_para_tesouraria(associado)
        self._efetivar_contrato(contrato)

        competencia = timezone.localdate().strftime("%Y-%m")
        response = self.tes_client.get(f"/api/v1/tesouraria/confirmacoes/?competencia={competencia}")
        self.assertEqual(response.status_code, 200, response.json())
        row = response.json()["results"][0]

        response = self.tes_client.post(
            f"/api/v1/tesouraria/confirmacoes/{row['id']}/confirmar-averbacao/"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Confirme a ligação", " ".join(response.json()))

        response = self.tes_client.post(
            f"/api/v1/tesouraria/confirmacoes/{row['id']}/link/",
            {"link": "https://nuvidio.me/rfc2j6"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())

        response = self.tes_client.post(
            f"/api/v1/tesouraria/confirmacoes/{row['id']}/confirmar-ligacao/"
        )
        self.assertEqual(response.status_code, 200, response.json())

        response = self.tes_client.post(
            f"/api/v1/tesouraria/confirmacoes/{row['id']}/confirmar-averbacao/"
        )
        self.assertEqual(response.status_code, 200, response.json())

        ligacao = Confirmacao.objects.get(pk=row["id"])
        averbacao = Confirmacao.objects.get(
            contrato=ligacao.contrato,
            competencia=ligacao.competencia,
            tipo=Confirmacao.Tipo.AVERBACAO,
        )
        self.assertEqual(ligacao.status, Confirmacao.Status.CONFIRMADO)
        self.assertEqual(averbacao.status, Confirmacao.Status.CONFIRMADO)

    def test_contrato_sem_mensalidade_pode_ser_averbado_diretamente(self):
        associado = self._criar_associado("62345678902")
        contrato = self._levar_para_tesouraria(associado)
        Contrato.objects.filter(pk=contrato.pk).update(valor_mensalidade=Decimal("0.00"))

        response = self.tes_client.post(f"/api/v1/tesouraria/contratos/{contrato.id}/averbar/")
        self.assertEqual(response.status_code, 200, response.json())

        contrato.refresh_from_db()
        associado.refresh_from_db()
        associado.esteira_item.refresh_from_db()
        self.assertEqual(contrato.status, Contrato.Status.ATIVO)
        self.assertIsNotNone(contrato.auxilio_liberado_em)
        self.assertEqual(associado.status, Associado.Status.ATIVO)
        self.assertEqual(associado.esteira_item.etapa_atual, EsteiraItem.Etapa.CONCLUIDO)

    def test_coordenador_pode_excluir_contrato_operacional_preservando_historico(self):
        associado = self._criar_associado("62345678921")
        contrato = self._levar_para_tesouraria(associado)
        associado.status = Associado.Status.ATIVO
        associado.save(update_fields=["status", "updated_at"])
        contrato.status = Contrato.Status.ATIVO
        contrato.save(update_fields=["status", "updated_at"])
        esteira_id = associado.esteira_item.id

        response = self.coord_client.post(
            f"/api/v1/tesouraria/contratos/{contrato.id}/excluir/"
        )
        self.assertEqual(response.status_code, 200, response.json())

        associado.refresh_from_db()
        contrato.refresh_from_db()
        esteira_item = EsteiraItem.all_objects.get(pk=esteira_id)
        self.assertEqual(associado.status, Associado.Status.ATIVO)
        self.assertEqual(contrato.status, Contrato.Status.ATIVO)
        self.assertEqual(esteira_item.etapa_atual, EsteiraItem.Etapa.CONCLUIDO)
        self.assertEqual(esteira_item.status, EsteiraItem.Situacao.REJEITADO)
        self.assertIsNotNone(esteira_item.concluido_em)
        self.assertIsNotNone(esteira_item.deleted_at)

    def test_coordenacao_tem_acesso_de_leitura_as_rotas_da_tesouraria(self):
        associado = self._criar_associado("62345678903")
        contrato = self._levar_para_tesouraria(associado)

        contratos = self.coord_client.get("/api/v1/tesouraria/contratos/")
        self.assertEqual(contratos.status_code, 200, contratos.json())

        pagamentos = self.coord_client.get("/api/v1/tesouraria/pagamentos/")
        self.assertEqual(pagamentos.status_code, 200, pagamentos.json())

        confirmacoes = self.coord_client.get(
            "/api/v1/tesouraria/confirmacoes/",
            {"competencia": timezone.localdate().strftime("%Y-%m")},
        )
        self.assertEqual(confirmacoes.status_code, 200, confirmacoes.json())

        despesas = self.coord_client.get("/api/v1/tesouraria/despesas/")
        self.assertEqual(despesas.status_code, 200, despesas.json())

        cancelar = self.coord_client.post(
            f"/api/v1/tesouraria/contratos/{contrato.id}/cancelar/",
            {"tipo": "cancelado", "motivo": "sem permissao"},
            format="json",
        )
        self.assertEqual(cancelar.status_code, 403)
