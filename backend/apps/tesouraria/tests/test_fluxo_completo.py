from __future__ import annotations

from datetime import date
from decimal import Decimal
import tempfile

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
from apps.tesouraria.models import Confirmacao


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
            "mensalidade": "500.00",
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
    ) -> Associado:
        response = self.admin_client.post(
            "/api/v1/associados/",
            self._cadastro_payload(cpf, data_aprovacao=data_aprovacao),
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

    def test_tesouraria_separa_concluidos_e_cancelados(self):
        associado_pago = self._criar_associado("17345678904")
        contrato_pago = self._levar_para_tesouraria(associado_pago)
        self._efetivar_contrato(contrato_pago)

        associado_cancelado = self._criar_associado("17345678905")
        contrato_cancelado = self._levar_para_tesouraria(associado_cancelado)
        contrato_cancelado.status = Contrato.Status.CANCELADO
        contrato_cancelado.save(update_fields=["status", "updated_at"])

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
        self.assertEqual(contrato_pago_row["comissao_agente"], "50.00")

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

    def test_efetivacao_sem_comprovante_falha(self):
        associado = self._criar_associado("52345678901")
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

        self.assertEqual(response.status_code, 400)
        self.assertIn("comprovante_agente", response.json())

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
