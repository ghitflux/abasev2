from __future__ import annotations

import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado, Documento
from apps.contratos.models import Contrato
from apps.esteira.models import DocIssue, EsteiraItem, Pendencia
from apps.tesouraria.models import Pagamento


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AnaliseViewSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.role_analista = Role.objects.create(codigo="ANALISTA", nome="Analista")

        cls.admin = cls._create_user("admin@abase.local", cls.role_admin, "Admin")
        cls.agente = cls._create_user("agente@abase.local", cls.role_agente, "Agente")
        cls.analista = cls._create_user(
            "analista@abase.local",
            cls.role_analista,
            "Analista",
        )
        cls.outro_analista = cls._create_user(
            "analista2@abase.local",
            cls.role_analista,
            "Analista Dois",
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

        self.analyst_client = APIClient()
        self.analyst_client.force_authenticate(self.analista)

        self.agent_client = APIClient()
        self.agent_client.force_authenticate(self.agente)

    def _create_item(
        self,
        *,
        suffix: str,
        etapa: str = EsteiraItem.Etapa.ANALISE,
        status: str = EsteiraItem.Situacao.AGUARDANDO,
        documentos: int = 0,
        analista: User | None = None,
    ) -> EsteiraItem:
        associado = Associado.objects.create(
            nome_completo=f"Associado {suffix}",
            cpf_cnpj=f"000000000{suffix}",
            matricula=f"MAT-{suffix}",
            status=Associado.Status.EM_ANALISE,
            agente_responsavel=self.agente,
            orgao_publico="SEFAZ",
        )
        Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo=f"CTR-{suffix}",
            valor_bruto="1500.00",
            valor_liquido="1200.00",
            valor_mensalidade="500.00",
            prazo_meses=3,
            margem_disponivel="900.00",
            valor_total_antecipacao="1500.00",
            status=Contrato.Status.EM_ANALISE,
        )
        esteira = EsteiraItem.objects.create(
            associado=associado,
            etapa_atual=etapa,
            status=status,
            analista_responsavel=analista,
            assumido_em=timezone.now() if analista else None,
        )
        for index in range(documentos):
            Documento.objects.create(
                associado=associado,
                tipo=Documento.Tipo.CPF if index == 0 else Documento.Tipo.CONTRACHEQUE,
                arquivo=SimpleUploadedFile(
                    f"doc-{suffix}-{index}.pdf",
                    b"conteudo",
                    content_type="application/pdf",
                ),
                status=Documento.Status.PENDENTE,
            )
        return esteira

    def test_resumo_e_filas_principais(self):
        pendente = self._create_item(suffix="101", documentos=0)
        recebidos = self._create_item(suffix="102", documentos=2)
        incompleta = self._create_item(suffix="103", documentos=1)
        Pendencia.objects.create(
            esteira_item=incompleta,
            tipo="documentacao",
            descricao="Documento faltando.",
        )
        reenvio = self._create_item(suffix="104", documentos=1)
        Pendencia.objects.create(
            esteira_item=reenvio,
            tipo="documentacao",
            descricao="Retorno do agente.",
            status=Pendencia.Status.RESOLVIDA,
            resolvida_em=timezone.now(),
            resolvida_por=self.analista,
        )

        response = self.analyst_client.get("/api/v1/analise/")
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["filas"]["pendente"], 1)
        self.assertEqual(payload["filas"]["recebidos"], 2)
        self.assertEqual(payload["filas"]["incompleta"], 1)
        self.assertEqual(payload["filas"]["reenvio"], 1)

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=pendente")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["results"][0]["id"], pendente.id)

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=incompleta")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["results"][0]["id"], incompleta.id)

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=reenvio")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["results"][0]["id"], reenvio.id)

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=recebidos")
        self.assertEqual(response.status_code, 200, response.json())
        received_ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(recebidos.id, received_ids)

    def test_item_assumido_por_outro_analista_some_da_recebida(self):
        item_meu = self._create_item(
            suffix="201",
            documentos=1,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
            analista=self.analista,
        )
        self._create_item(
            suffix="202",
            documentos=1,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
            analista=self.outro_analista,
        )

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=recebida")
        self.assertEqual(response.status_code, 200, response.json())
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(item_meu.id, ids)
        self.assertEqual(len(ids), 1)

    def test_status_documentacao_fica_completa_quando_ha_anexos_sem_pendencia(self):
        item = self._create_item(suffix="250", documentos=2)

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=recebidos")
        self.assertEqual(response.status_code, 200, response.json())

        row = next(
            registro
            for registro in response.json()["results"]
            if registro["id"] == item.id
        )
        self.assertEqual(row["status_documentacao"], "completa")

    def test_atualiza_data_pagamento_legado(self):
        item = self._create_item(suffix="301", documentos=1)
        pagamento = Pagamento.objects.create(
            cadastro=item.associado,
            created_by=self.admin,
            contrato_codigo=item.associado.contratos.get().codigo,
            cpf_cnpj=item.associado.cpf_cnpj,
            full_name=item.associado.nome_completo,
            agente_responsavel=self.agente.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago="1500.00",
            paid_at=timezone.now(),
        )

        response = self.analyst_client.patch(
            f"/api/v1/analise/ajustes/{pagamento.id}/data-pagamento/",
            {"new_date": "2026-03-10T12:30"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())

        pagamento.refresh_from_db()
        self.assertEqual(pagamento.paid_at.year, 2026)
        self.assertEqual(pagamento.paid_at.month, 3)
        self.assertEqual(pagamento.paid_at.day, 10)
        self.assertEqual(pagamento.paid_at.hour, 12)
        self.assertEqual(pagamento.paid_at.minute, 30)

    def test_atualiza_nome_no_ajuste_de_dados(self):
        item = self._create_item(suffix="401", documentos=1)

        response = self.analyst_client.patch(
            f"/api/v1/analise/dados/{item.associado_id}/nome/",
            {"nome_completo": "Maria das dores"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())

        item.associado.refresh_from_db()
        self.assertEqual(item.associado.nome_completo, "MARIA DAS DORES")

    def test_detalhe_da_esteira_retorna_documentos_do_associado(self):
        item = self._create_item(suffix="402", documentos=1)

        response = self.analyst_client.get(f"/api/v1/esteira/{item.id}/")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(len(response.json()["documentos"]), 1)
        self.assertTrue(response.json()["documentos"][0]["arquivo"])

    def test_agente_reenvia_correcao_e_item_volta_para_analise(self):
        item = self._create_item(
            suffix="403",
            etapa=EsteiraItem.Etapa.CADASTRO,
            status=EsteiraItem.Situacao.PENDENCIADO,
            documentos=1,
        )
        Pendencia.objects.create(
            esteira_item=item,
            tipo="documentacao",
            descricao="Atualizar cadastro e comprovantes.",
        )
        DocIssue.objects.create(
            associado=item.associado,
            cpf_cnpj=item.associado.cpf_cnpj,
            contrato_codigo=item.associado.contratos.get().codigo,
            analista=self.analista,
            mensagem="Documento incompleto.",
            status=DocIssue.Status.INCOMPLETO,
        )

        response = self.agent_client.post(f"/api/v1/esteira/{item.id}/validar-documento/")
        self.assertEqual(response.status_code, 200, response.json())

        item.refresh_from_db()
        item.associado.refresh_from_db()
        pendencia = item.pendencias.get()
        doc_issue = item.associado.doc_issues.get()
        documento = item.associado.documentos.get()

        self.assertEqual(item.etapa_atual, EsteiraItem.Etapa.ANALISE)
        self.assertEqual(item.status, EsteiraItem.Situacao.AGUARDANDO)
        self.assertEqual(item.associado.status, Associado.Status.EM_ANALISE)
        self.assertEqual(pendencia.status, Pendencia.Status.RESOLVIDA)
        self.assertEqual(doc_issue.status, DocIssue.Status.RESOLVIDO)
        self.assertEqual(documento.status, Documento.Status.APROVADO)

    def test_agente_nao_tem_acesso_ao_modulo_analise(self):
        response = self.agent_client.get("/api/v1/analise/")
        self.assertEqual(response.status_code, 403)
