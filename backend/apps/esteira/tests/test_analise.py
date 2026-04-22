from __future__ import annotations

import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado, Documento
from apps.contratos.models import Contrato
from apps.esteira.models import DocIssue, DocReupload, EsteiraItem, Pendencia
from apps.tesouraria.models import Pagamento


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AnaliseViewSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.role_analista = Role.objects.create(codigo="ANALISTA", nome="Analista")
        cls.role_coord = Role.objects.create(codigo="COORDENADOR", nome="Coordenador")

        cls.admin = cls._create_user("admin@abase.local", cls.role_admin, "Admin")
        cls.agente = cls._create_user("agente@abase.local", cls.role_agente, "Agente")
        cls.analista = cls._create_user(
            "analista@abase.local",
            cls.role_analista,
            "Analista",
        )
        cls.coordenador = cls._create_user(
            "coord@abase.local",
            cls.role_coord,
            "Coordenador",
        )
        cls.outro_agente = cls._create_user(
            "agente2@abase.local",
            cls.role_agente,
            "Agente Dois",
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

        self.coord_client = APIClient()
        self.coord_client.force_authenticate(self.coordenador)

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
        agente: User | None = None,
        contrato_status: str = Contrato.Status.EM_ANALISE,
        associado_status: str = Associado.Status.EM_ANALISE,
        origem_operacional: str = Contrato.OrigemOperacional.CADASTRO,
    ) -> EsteiraItem:
        agente_responsavel = agente or self.agente
        associado = Associado.objects.create(
            nome_completo=f"Associado {suffix}",
            cpf_cnpj=f"000000000{suffix}",
            matricula=f"MAT-{suffix}",
            status=associado_status,
            agente_responsavel=agente_responsavel,
            orgao_publico="SEFAZ",
        )
        Contrato.objects.create(
            associado=associado,
            agente=agente_responsavel,
            codigo=f"CTR-{suffix}",
            valor_bruto="1500.00",
            valor_liquido="1200.00",
            valor_mensalidade="500.00",
            prazo_meses=3,
            margem_disponivel="900.00",
            valor_total_antecipacao="1500.00",
            status=contrato_status,
            origem_operacional=origem_operacional,
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
        pendente_documentos = self._create_item(suffix="101", documentos=0)
        pendencia_aberta = self._create_item(suffix="102", documentos=1)
        Pendencia.objects.create(
            esteira_item=pendencia_aberta,
            tipo="documentacao",
            descricao="Documento faltando.",
        )
        corrigida = self._create_item(suffix="103", documentos=1)
        Pendencia.objects.create(
            esteira_item=corrigida,
            tipo="documentacao",
            descricao="Retorno do agente.",
            status=Pendencia.Status.RESOLVIDA,
            resolvida_em=timezone.now(),
            resolvida_por=self.analista,
        )
        novo_contrato = self._create_item(
            suffix="1030",
            etapa=EsteiraItem.Etapa.ANALISE,
            status=EsteiraItem.Situacao.AGUARDANDO,
            documentos=1,
        )
        reativacao = self._create_item(
            suffix="1031",
            etapa=EsteiraItem.Etapa.ANALISE,
            status=EsteiraItem.Situacao.AGUARDANDO,
            documentos=1,
            origem_operacional=Contrato.OrigemOperacional.REATIVACAO,
        )
        enviado_coord = self._create_item(
            suffix="104",
            etapa=EsteiraItem.Etapa.COORDENACAO,
            status=EsteiraItem.Situacao.AGUARDANDO,
            documentos=1,
        )
        enviado_tesouraria = self._create_item(
            suffix="105",
            etapa=EsteiraItem.Etapa.TESOURARIA,
            status=EsteiraItem.Situacao.AGUARDANDO,
            documentos=1,
        )
        efetivado = self._create_item(
            suffix="106",
            etapa=EsteiraItem.Etapa.CONCLUIDO,
            status=EsteiraItem.Situacao.APROVADO,
            documentos=1,
            contrato_status=Contrato.Status.ATIVO,
            associado_status=Associado.Status.ATIVO,
        )
        cancelado = self._create_item(
            suffix="107",
            etapa=EsteiraItem.Etapa.CONCLUIDO,
            status=EsteiraItem.Situacao.APROVADO,
            documentos=1,
            contrato_status=Contrato.Status.CANCELADO,
            associado_status=Associado.Status.INATIVO,
        )

        response = self.analyst_client.get("/api/v1/analise/")
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["filas"]["novos_contratos"], 2)
        self.assertEqual(payload["filas"]["contratos_reativacao"], 1)
        self.assertEqual(payload["filas"]["ver_todos"], 9)
        self.assertEqual(payload["filas"]["pendencias"], 2)
        self.assertEqual(payload["filas"]["pendencias_corrigidas"], 1)
        self.assertEqual(payload["filas"]["enviado_tesouraria"], 1)
        self.assertEqual(payload["filas"]["enviado_coordenacao"], 1)
        self.assertEqual(payload["filas"]["efetivados"], 1)
        self.assertEqual(payload["filas"]["cancelados"], 1)

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=novos_contratos")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["results"][0]["id"], novo_contrato.id)
        self.assertIn("created_at", response.json()["results"][0])

        response = self.analyst_client.get(
            "/api/v1/analise/filas/?secao=contratos_reativacao"
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["results"][0]["id"], reativacao.id)

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=ver_todos")
        self.assertEqual(response.status_code, 200, response.json())
        ids = {row["id"] for row in response.json()["results"]}
        self.assertTrue(
            {
                pendente_documentos.id,
                pendencia_aberta.id,
                corrigida.id,
                novo_contrato.id,
                reativacao.id,
                enviado_coord.id,
                enviado_tesouraria.id,
                efetivado.id,
                cancelado.id,
            }.issubset(ids)
        )

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=pendencias")
        self.assertEqual(response.status_code, 200, response.json())
        pendencias_rows = response.json()["results"]
        ids = {row["id"] for row in pendencias_rows}
        self.assertIn(pendente_documentos.id, ids)
        self.assertIn(pendencia_aberta.id, ids)
        pendente_documentos_row = next(
            row for row in pendencias_rows if row["id"] == pendente_documentos.id
        )
        self.assertEqual(
            pendente_documentos_row["associado_id"],
            pendente_documentos.associado_id,
        )

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=pendencias_corrigidas")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["results"][0]["id"], corrigida.id)

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=enviado_coordenacao")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["results"][0]["id"], enviado_coord.id)

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=enviado_tesouraria")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["results"][0]["id"], enviado_tesouraria.id)

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=efetivados")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["results"][0]["id"], efetivado.id)

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=cancelados")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["results"][0]["id"], cancelado.id)

    def test_item_assumido_por_outro_analista_some_da_recebida(self):
        item_meu = self._create_item(
            suffix="201",
            documentos=1,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
            analista=self.analista,
        )
        item_outro = self._create_item(
            suffix="202",
            documentos=1,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
            analista=self.outro_analista,
        )

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=ver_todos")
        self.assertEqual(response.status_code, 200, response.json())
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(item_meu.id, ids)
        self.assertNotIn(item_outro.id, ids)
        self.assertEqual(len(ids), 1)

    def test_coordenador_tem_acesso_ao_modulo_analise(self):
        self._create_item(suffix="203", documentos=1)

        response = self.coord_client.get("/api/v1/analise/")
        self.assertEqual(response.status_code, 200, response.json())

        filas = self.coord_client.get("/api/v1/analise/filas/?secao=ver_todos")
        self.assertEqual(filas.status_code, 200, filas.json())
        self.assertEqual(filas.json()["count"], 1)

    def test_resumo_e_filas_respeitam_filtros_avancados_e_analista_responsavel(self):
        sem_responsavel = self._create_item(
            suffix="210",
            documentos=1,
            analista=None,
            agente=self.agente,
        )
        meu_item = self._create_item(
            suffix="211",
            documentos=1,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
            analista=self.analista,
            agente=self.agente,
        )
        self._create_item(
            suffix="212",
            documentos=1,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
            analista=self.outro_analista,
            agente=self.outro_agente,
        )

        response = self.analyst_client.get("/api/v1/analise/")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["filas"]["ver_todos"], 2)

        today = timezone.localdate().isoformat()
        response = self.admin_client.get(
            "/api/v1/analise/filas/",
            {
                "secao": "ver_todos",
                "analista": "sem_responsavel",
                "agente": self.agente.first_name,
                "etapa": EsteiraItem.Etapa.ANALISE,
                "data_inicio": today,
                "data_fim": today,
                "page_size": 10,
            },
        )
        self.assertEqual(response.status_code, 200, response.json())
        rows = response.json()["results"]
        self.assertEqual([row["id"] for row in rows], [sem_responsavel.id])
        self.assertIsNone(rows[0]["analista_responsavel"])

        response = self.admin_client.get(
            "/api/v1/analise/filas/",
            {
                "secao": "ver_todos",
                "analista": str(self.analista.id),
                "status": EsteiraItem.Situacao.EM_ANDAMENTO,
                "page_size": 10,
            },
        )
        self.assertEqual(response.status_code, 200, response.json())
        rows = response.json()["results"]
        self.assertEqual([row["id"] for row in rows], [meu_item.id])
        self.assertEqual(
            rows[0]["analista_responsavel"]["id"],
            self.analista.id,
        )

    def test_status_documentacao_fica_completa_quando_ha_anexos_sem_pendencia(self):
        item = self._create_item(suffix="250", documentos=2)

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=ver_todos")
        self.assertEqual(response.status_code, 200, response.json())

        row = next(
            registro
            for registro in response.json()["results"]
            if registro["id"] == item.id
        )
        self.assertEqual(row["status_documentacao"], "completa")

    def test_anexos_extras_livres_nao_satisfazem_documentacao_obrigatoria(self):
        item = self._create_item(suffix="2501", documentos=0)
        Documento.objects.create(
            associado=item.associado,
            tipo=Documento.Tipo.ANEXO_EXTRA_1,
            arquivo=SimpleUploadedFile(
                "anexo-extra-1.pdf",
                b"conteudo",
                content_type="application/pdf",
            ),
            status=Documento.Status.PENDENTE,
        )
        Documento.objects.create(
            associado=item.associado,
            tipo=Documento.Tipo.ANEXO_EXTRA_2,
            arquivo=SimpleUploadedFile(
                "anexo-extra-2.pdf",
                b"conteudo",
                content_type="application/pdf",
            ),
            status=Documento.Status.PENDENTE,
        )

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=ver_todos")
        self.assertEqual(response.status_code, 200, response.json())
        row = next(
            registro
            for registro in response.json()["results"]
            if registro["id"] == item.id
        )
        self.assertEqual(row["status_documentacao"], "incompleta")

        pendencias = self.analyst_client.get("/api/v1/analise/filas/?secao=pendencias")
        self.assertEqual(pendencias.status_code, 200, pendencias.json())
        ids = {registro["id"] for registro in pendencias.json()["results"]}
        self.assertIn(item.id, ids)

    def test_pendencias_inclui_doc_issue_aberta(self):
        item = self._create_item(suffix="251", documentos=1)
        DocIssue.objects.create(
            associado=item.associado,
            cpf_cnpj=item.associado.cpf_cnpj,
            contrato_codigo=item.associado.contratos.get().codigo,
            analista=self.analista,
            mensagem="Documento inconsistente.",
            status=DocIssue.Status.INCOMPLETO,
        )

        response = self.analyst_client.get("/api/v1/analise/filas/?secao=pendencias")
        self.assertEqual(response.status_code, 200, response.json())
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(item.id, ids)

    def test_pendencias_corrigidas_inclui_reenvio_recebido(self):
        item = self._create_item(suffix="252", documentos=1)
        issue = DocIssue.objects.create(
            associado=item.associado,
            cpf_cnpj=item.associado.cpf_cnpj,
            contrato_codigo=item.associado.contratos.get().codigo,
            analista=self.analista,
            mensagem="Atualizar comprovante.",
            status=DocIssue.Status.INCOMPLETO,
        )
        DocReupload.objects.create(
            doc_issue=issue,
            associado=item.associado,
            uploaded_by=self.agente,
            cpf_cnpj=item.associado.cpf_cnpj,
            contrato_codigo=item.associado.contratos.get().codigo,
            file_original_name="doc.pdf",
            file_stored_name="doc-252.pdf",
            status=DocReupload.Status.RECEBIDO,
        )

        response = self.analyst_client.get(
            "/api/v1/analise/filas/?secao=pendencias_corrigidas"
        )
        self.assertEqual(response.status_code, 200, response.json())
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(item.id, ids)

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
        pagamento_local = timezone.localtime(pagamento.paid_at)
        self.assertEqual(pagamento_local.year, 2026)
        self.assertEqual(pagamento_local.month, 3)
        self.assertEqual(pagamento_local.day, 10)
        self.assertEqual(pagamento_local.hour, 12)
        self.assertEqual(pagamento_local.minute, 30)

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
        self.assertEqual(response.json()["associado_id"], item.associado_id)
        self.assertEqual(len(response.json()["documentos"]), 1)
        self.assertTrue(response.json()["documentos"][0]["arquivo"])

    def test_detalhe_da_esteira_bloqueia_item_assumido_por_outro_analista(self):
        item = self._create_item(
            suffix="4021",
            documentos=1,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
            analista=self.outro_analista,
        )

        response = self.analyst_client.get(f"/api/v1/esteira/{item.id}/")
        self.assertEqual(response.status_code, 404, response.json())

    def test_excluir_solicitacao_aguardando_faz_soft_delete_do_pacote(self):
        item = self._create_item(suffix="4022", documentos=1)
        contrato = item.associado.contratos.get()
        ciclos = list(contrato.ciclos.all())
        parcelas = [parcela for ciclo in ciclos for parcela in ciclo.parcelas.all()]

        response = self.coord_client.delete(f"/api/v1/esteira/{item.id}/")
        self.assertEqual(response.status_code, 204)

        self.assertFalse(EsteiraItem.objects.filter(pk=item.id).exists())
        self.assertIsNotNone(EsteiraItem.all_objects.get(pk=item.id).deleted_at)
        self.assertFalse(Associado.objects.filter(pk=item.associado_id).exists())
        self.assertIsNotNone(Associado.all_objects.get(pk=item.associado_id).deleted_at)
        self.assertIsNotNone(Contrato.all_objects.get(pk=contrato.id).deleted_at)
        for ciclo in ciclos:
            self.assertIsNotNone(type(ciclo).all_objects.get(pk=ciclo.id).deleted_at)
        for parcela in parcelas:
            self.assertIsNotNone(type(parcela).all_objects.get(pk=parcela.id).deleted_at)
        self.assertEqual(
            list(EsteiraItem.all_objects.get(pk=item.id).pendencias.all()),
            [],
        )

    def test_remover_fila_preserva_associado_documentos_e_historico(self):
        item = self._create_item(
            suffix="40220",
            documentos=1,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
            analista=self.analista,
        )
        associado_id = item.associado_id
        documento_id = item.associado.documentos.get().id

        response = self.analyst_client.post(
            f"/api/v1/esteira/{item.id}/remover-fila/",
            {"observacao": "Linha duplicada na análise"},
            format="json",
        )
        self.assertEqual(response.status_code, 204)

        item = EsteiraItem.all_objects.get(pk=item.id)
        self.assertIsNotNone(item.deleted_at)
        self.assertEqual(item.etapa_atual, EsteiraItem.Etapa.CONCLUIDO)
        self.assertEqual(item.status, EsteiraItem.Situacao.REJEITADO)
        self.assertEqual(item.observacao, "Linha duplicada na análise")
        self.assertTrue(Associado.objects.filter(pk=associado_id).exists())
        self.assertTrue(Documento.objects.filter(pk=documento_id).exists())
        self.assertTrue(
            item.transicoes.filter(acao="remover_fila_operacional").exists()
        )

    def test_admin_exclui_item_consolidado_preservando_historico(self):
        item = self._create_item(
            suffix="40221",
            etapa=EsteiraItem.Etapa.ANALISE,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
            documentos=1,
            analista=self.analista,
            contrato_status=Contrato.Status.ATIVO,
            associado_status=Associado.Status.ATIVO,
        )
        contrato = item.associado.contratos.get()
        pendencia = Pendencia.objects.create(
            esteira_item=item,
            tipo="documentacao",
            descricao="Aguardando revisão final.",
        )

        response = self.admin_client.delete(f"/api/v1/esteira/{item.id}/")
        self.assertEqual(response.status_code, 204)

        item.refresh_from_db()
        item.associado.refresh_from_db()
        contrato.refresh_from_db()
        pendencia.refresh_from_db()
        self.assertIsNone(item.deleted_at)
        self.assertEqual(item.etapa_atual, EsteiraItem.Etapa.CONCLUIDO)
        self.assertEqual(item.status, EsteiraItem.Situacao.APROVADO)
        self.assertIsNotNone(item.concluido_em)
        self.assertEqual(item.associado.status, Associado.Status.ATIVO)
        self.assertEqual(contrato.status, Contrato.Status.ATIVO)
        self.assertEqual(pendencia.status, Pendencia.Status.CANCELADA)
        self.assertIsNotNone(pendencia.resolvida_em)

    def test_coordenador_exclui_item_cancelado_preservando_historico(self):
        item = self._create_item(
            suffix="40222",
            etapa=EsteiraItem.Etapa.TESOURARIA,
            status=EsteiraItem.Situacao.PENDENCIADO,
            documentos=1,
            contrato_status=Contrato.Status.CANCELADO,
            associado_status=Associado.Status.INATIVO,
        )
        contrato = item.associado.contratos.get()
        pendencia = Pendencia.objects.create(
            esteira_item=item,
            tipo="documentacao",
            descricao="Fila inconsistente após cancelamento.",
        )

        response = self.coord_client.delete(f"/api/v1/esteira/{item.id}/")
        self.assertEqual(response.status_code, 204)

        item.refresh_from_db()
        item.associado.refresh_from_db()
        contrato.refresh_from_db()
        pendencia.refresh_from_db()
        self.assertIsNone(item.deleted_at)
        self.assertEqual(item.etapa_atual, EsteiraItem.Etapa.CONCLUIDO)
        self.assertEqual(item.status, EsteiraItem.Situacao.REJEITADO)
        self.assertEqual(item.associado.status, Associado.Status.INATIVO)
        self.assertEqual(contrato.status, Contrato.Status.CANCELADO)
        self.assertEqual(pendencia.status, Pendencia.Status.CANCELADA)

    def test_excluir_solicitacao_recusa_item_assumido(self):
        item = self._create_item(
            suffix="4023",
            documentos=1,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
            analista=self.analista,
        )

        response = self.analyst_client.delete(f"/api/v1/esteira/{item.id}/")
        self.assertEqual(response.status_code, 400, response.json())

    def test_acoes_disponiveis_exibem_excluir_para_coordenador_em_item_consolidado(self):
        item = self._create_item(
            suffix="40231",
            documentos=1,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
            analista=self.analista,
            contrato_status=Contrato.Status.ATIVO,
            associado_status=Associado.Status.ATIVO,
        )

        coord_response = self.coord_client.get("/api/v1/analise/filas/?secao=ver_todos")
        self.assertEqual(coord_response.status_code, 200, coord_response.json())
        coord_row = next(
            row for row in coord_response.json()["results"] if row["id"] == item.id
        )
        self.assertIn("excluir", coord_row["acoes_disponiveis"])

        analyst_response = self.analyst_client.get(
            "/api/v1/analise/filas/?secao=ver_todos"
        )
        self.assertEqual(analyst_response.status_code, 200, analyst_response.json())
        analyst_row = next(
            row for row in analyst_response.json()["results"] if row["id"] == item.id
        )
        self.assertNotIn("excluir", analyst_row["acoes_disponiveis"])

    def test_reprovar_item_em_analise_remove_cadastro_completo(self):
        item = self._create_item(
            suffix="4024",
            documentos=1,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
            analista=self.analista,
        )
        contrato = item.associado.contratos.get()
        ciclos = list(contrato.ciclos.all())
        parcelas = [parcela for ciclo in ciclos for parcela in ciclo.parcelas.all()]

        fila = self.analyst_client.get("/api/v1/analise/filas/?secao=ver_todos")
        self.assertEqual(fila.status_code, 200, fila.json())
        row = next(registro for registro in fila.json()["results"] if registro["id"] == item.id)
        self.assertIn("reprovar", row["acoes_disponiveis"])

        response = self.analyst_client.post(
            f"/api/v1/esteira/{item.id}/reprovar/",
            {"observacao": "Cadastro inconsistente para aprovação."},
            format="json",
        )
        self.assertEqual(response.status_code, 204)

        self.assertFalse(EsteiraItem.objects.filter(pk=item.id).exists())
        self.assertIsNotNone(EsteiraItem.all_objects.get(pk=item.id).deleted_at)
        self.assertFalse(Associado.objects.filter(pk=item.associado_id).exists())
        self.assertIsNotNone(Associado.all_objects.get(pk=item.associado_id).deleted_at)
        self.assertIsNotNone(Contrato.all_objects.get(pk=contrato.id).deleted_at)
        for ciclo in ciclos:
            self.assertIsNotNone(type(ciclo).all_objects.get(pk=ciclo.id).deleted_at)
        for parcela in parcelas:
            self.assertIsNotNone(type(parcela).all_objects.get(pk=parcela.id).deleted_at)

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

    def test_pendencias_retorna_esteira_item_id_para_correcao(self):
        item = self._create_item(
            suffix="404",
            etapa=EsteiraItem.Etapa.CADASTRO,
            status=EsteiraItem.Situacao.PENDENCIADO,
        )
        pendencia = Pendencia.objects.create(
            esteira_item=item,
            tipo="documentacao",
            descricao="Atualizar comprovante.",
            retornado_para_agente=True,
        )

        response = self.agent_client.get("/api/v1/esteira/pendencias/")
        self.assertEqual(response.status_code, 200, response.json())

        row = next(
            registro
            for registro in response.json()["results"]
            if registro["id"] == pendencia.id
        )
        self.assertEqual(row["esteira_item_id"], item.id)

    def test_correcao_retorna_payload_completo_para_agente(self):
        item = self._create_item(
            suffix="405",
            etapa=EsteiraItem.Etapa.CADASTRO,
            status=EsteiraItem.Situacao.PENDENCIADO,
            documentos=1,
        )
        Pendencia.objects.create(
            esteira_item=item,
            tipo="documentacao",
            descricao="Corrigir cadastro e anexos.",
            retornado_para_agente=True,
        )

        response = self.agent_client.get(f"/api/v1/esteira/{item.id}/correcao/")
        self.assertEqual(response.status_code, 200, response.json())

        payload = response.json()
        self.assertEqual(payload["id"], item.associado_id)
        self.assertIn("documentos", payload)
        self.assertEqual(len(payload["documentos"]), 1)
        self.assertIn("esteira", payload)
        self.assertEqual(payload["esteira"]["id"], item.id)

    def test_agente_nao_tem_acesso_ao_modulo_analise(self):
        response = self.agent_client.get("/api/v1/analise/")
        self.assertEqual(response.status_code, 403)

    def test_resumo_de_pendencias_da_esteira_respeita_recorte_do_agente(self):
        item_retorno = self._create_item(
            suffix="501",
            etapa=EsteiraItem.Etapa.CADASTRO,
            status=EsteiraItem.Situacao.PENDENCIADO,
        )
        Pendencia.objects.create(
            esteira_item=item_retorno,
            tipo="documentacao",
            descricao="Corrigir comprovante.",
            retornado_para_agente=True,
        )

        item_interno = self._create_item(
            suffix="502",
            etapa=EsteiraItem.Etapa.CADASTRO,
            status=EsteiraItem.Situacao.PENDENCIADO,
        )
        Pendencia.objects.create(
            esteira_item=item_interno,
            tipo="cadastro",
            descricao="Validação interna pendente.",
            retornado_para_agente=False,
        )

        item_outro_agente = self._create_item(
            suffix="503",
            etapa=EsteiraItem.Etapa.CADASTRO,
            status=EsteiraItem.Situacao.PENDENCIADO,
            agente=self.outro_agente,
        )
        Pendencia.objects.create(
            esteira_item=item_outro_agente,
            tipo="documentacao",
            descricao="Outro agente.",
            retornado_para_agente=True,
        )

        response = self.agent_client.get("/api/v1/esteira/pendencias-resumo/")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["total"], 2)
        self.assertEqual(response.json()["retornadas_agente"], 1)
        self.assertEqual(response.json()["internas"], 1)
        self.assertEqual(response.json()["associados_impactados"], 2)

        filtered_response = self.agent_client.get(
            "/api/v1/esteira/pendencias-resumo/?search=502"
        )
        self.assertEqual(filtered_response.status_code, 200, filtered_response.json())
        self.assertEqual(filtered_response.json()["total"], 1)
        self.assertEqual(filtered_response.json()["retornadas_agente"], 0)
        self.assertEqual(filtered_response.json()["internas"], 1)
        self.assertEqual(filtered_response.json()["associados_impactados"], 1)
