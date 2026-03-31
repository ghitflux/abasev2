from __future__ import annotations

from datetime import date
from decimal import Decimal
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.tesouraria.models import (
    DevolucaoAssociado,
    DevolucaoAssociadoAnexo,
    LiquidacaoContrato,
    Pagamento,
)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DevolucaoAssociadoViewSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_tesoureiro = Role.objects.create(codigo="TESOUREIRO", nome="Tesoureiro")
        cls.role_coordenador = Role.objects.create(
            codigo="COORDENADOR",
            nome="Coordenador",
        )
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")

        cls.admin = cls._create_user("admin.devolucao@abase.local", cls.role_admin, "Admin")
        cls.tesoureiro = cls._create_user(
            "tes.devolucao@abase.local",
            cls.role_tesoureiro,
            "Tesoureiro",
        )
        cls.coordenador = cls._create_user(
            "coord.devolucao@abase.local",
            cls.role_coordenador,
            "Coordenador",
        )
        cls.agente = cls._create_user("agente.devolucao@abase.local", cls.role_agente, "Agente")

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

        self.tes_client = APIClient()
        self.tes_client.force_authenticate(self.tesoureiro)

        self.coord_client = APIClient()
        self.coord_client.force_authenticate(self.coordenador)

    def _create_contract_fixture(self, cpf: str = "77852621368") -> tuple[Associado, Contrato, Parcela]:
        associado = Associado.objects.create(
            nome_completo=f"Associado {cpf[-4:]}",
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo=f"CTR-{cpf[-6:]}",
            valor_bruto=Decimal("18000.00"),
            valor_liquido=Decimal("10000.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("630.00"),
            valor_total_antecipacao=Decimal("900.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2026, 1, 3),
            data_aprovacao=date(2026, 1, 3),
            data_primeira_mensalidade=date(2026, 1, 1),
            mes_averbacao=date(2026, 1, 1),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        parcela = Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 2, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 2, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 2, 5),
            observacao="Desconto confirmado pelo retorno.",
        )
        return associado, contrato, parcela

    def test_lista_contratos_para_registrar_devolucao(self):
        associado_parcela, contrato_parcela, _parcela = self._create_contract_fixture()
        associado_pagamento, contrato_pagamento, parcela_em_aberto = self._create_contract_fixture(
            cpf="77852621366"
        )
        parcela_em_aberto.status = Parcela.Status.EM_ABERTO
        parcela_em_aberto.data_pagamento = None
        parcela_em_aberto.observacao = ""
        parcela_em_aberto.save(update_fields=["status", "data_pagamento", "observacao", "updated_at"])
        Pagamento.objects.create(
            cadastro=associado_pagamento,
            created_by=self.tesoureiro,
            cpf_cnpj=associado_pagamento.cpf_cnpj,
            full_name=associado_pagamento.nome_completo,
            agente_responsavel=self.agente.full_name,
            contrato_codigo=contrato_pagamento.codigo,
            valor_pago=Decimal("300.00"),
            status=Pagamento.Status.PAGO,
        )
        _associado_invalido, contrato_invalido, parcela_invalida = self._create_contract_fixture(
            cpf="77852621365"
        )
        parcela_invalida.status = Parcela.Status.EM_ABERTO
        parcela_invalida.data_pagamento = None
        parcela_invalida.observacao = ""
        parcela_invalida.save(
            update_fields=["status", "data_pagamento", "observacao", "updated_at"]
        )

        response = self.tes_client.get("/api/v1/tesouraria/devolucoes/contratos/")

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        ids = {row["contrato_id"] for row in payload["results"]}
        self.assertIn(contrato_parcela.id, ids)
        self.assertIn(contrato_pagamento.id, ids)
        self.assertNotIn(contrato_invalido.id, ids)
        row = next(row for row in payload["results"] if row["contrato_id"] == contrato_parcela.id)
        self.assertEqual(row["status_contrato"], Contrato.Status.ATIVO)
        self.assertEqual(row["matricula"], associado_parcela.matricula_orgao)

    def test_tesoureiro_registra_pagamento_indevido_sem_alterar_parcela(self):
        associado, contrato, parcela = self._create_contract_fixture()
        status_anterior = parcela.status
        pagamento_anterior = parcela.data_pagamento
        observacao_anterior = parcela.observacao

        response = self.tes_client.post(
            f"/api/v1/tesouraria/devolucoes/contratos/{contrato.id}/registrar/",
            {
                "tipo": DevolucaoAssociado.Tipo.PAGAMENTO_INDEVIDO,
                "data_devolucao": "2026-03-21",
                "quantidade_parcelas": 2,
                "valor": "300.00",
                "motivo": "Pagamento duplicado ao associado.",
                "comprovantes": [
                    SimpleUploadedFile(
                        "devolucao.pdf",
                        b"arquivo",
                        content_type="application/pdf",
                    ),
                    SimpleUploadedFile(
                        "devolucao-extra.pdf",
                        b"arquivo-extra",
                        content_type="application/pdf",
                    ),
                ],
            },
        )

        self.assertEqual(response.status_code, 201, response.json())
        parcela.refresh_from_db()
        self.assertEqual(parcela.status, status_anterior)
        self.assertEqual(parcela.data_pagamento, pagamento_anterior)
        self.assertEqual(parcela.observacao, observacao_anterior)

        devolucao = DevolucaoAssociado.objects.get(contrato=contrato)
        self.assertEqual(devolucao.associado, associado)
        self.assertEqual(devolucao.status, "registrada")
        self.assertEqual(devolucao.nome_snapshot, associado.nome_completo)
        self.assertEqual(devolucao.cpf_cnpj_snapshot, associado.cpf_cnpj)
        self.assertEqual(devolucao.matricula_snapshot, associado.matricula_orgao)
        self.assertEqual(devolucao.agente_snapshot, self.agente.full_name)
        self.assertEqual(devolucao.contrato_codigo_snapshot, contrato.codigo)
        self.assertEqual(devolucao.realizado_por, self.tesoureiro)
        self.assertEqual(devolucao.quantidade_parcelas, 2)
        self.assertEqual(devolucao.anexos.count(), 1)

    def test_coordenador_registra_desconto_indevido_com_competencia(self):
        _associado, contrato, _parcela = self._create_contract_fixture(cpf="77852621369")

        response = self.coord_client.post(
            f"/api/v1/tesouraria/devolucoes/contratos/{contrato.id}/registrar/",
            {
                "tipo": DevolucaoAssociado.Tipo.DESCONTO_INDEVIDO,
                "data_devolucao": "2026-03-21",
                "quantidade_parcelas": 1,
                "valor": "300.00",
                "motivo": "Desconto realizado em folha após cancelamento.",
                "competencia_referencia": "2026-02-01",
                "comprovantes": [
                    SimpleUploadedFile(
                        "desconto-indevido.pdf",
                        b"arquivo",
                        content_type="application/pdf",
                    )
                ],
            },
        )

        self.assertEqual(response.status_code, 201, response.json())
        devolucao = DevolucaoAssociado.objects.get(contrato=contrato)
        self.assertEqual(devolucao.competencia_referencia, date(2026, 2, 1))
        self.assertEqual(devolucao.realizado_por, self.coordenador)

    def test_historico_filtra_status_e_tipo(self):
        _associado, contrato, _parcela = self._create_contract_fixture(cpf="77852621370")
        devolucao = DevolucaoAssociado.objects.create(
            contrato=contrato,
            associado=contrato.associado,
            tipo=DevolucaoAssociado.Tipo.DESCONTO_INDEVIDO,
            data_devolucao=date(2026, 3, 21),
            valor=Decimal("300.00"),
            motivo="Desconto indevido confirmado.",
            comprovante=SimpleUploadedFile("hist.pdf", b"arquivo", content_type="application/pdf"),
            nome_comprovante="hist.pdf",
            competencia_referencia=date(2026, 2, 1),
            nome_snapshot=contrato.associado.nome_completo,
            cpf_cnpj_snapshot=contrato.associado.cpf_cnpj,
            matricula_snapshot=contrato.associado.matricula_orgao,
            agente_snapshot=self.agente.full_name,
            contrato_codigo_snapshot=contrato.codigo,
            realizado_por=self.tesoureiro,
        )
        devolucao.revertida_em = devolucao.created_at
        devolucao.revertida_por = self.admin
        devolucao.motivo_reversao = "Estorno cancelado"
        devolucao.save(
            update_fields=["revertida_em", "revertida_por", "motivo_reversao", "updated_at"]
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/devolucoes/",
            {"status": "revertida", "tipo": DevolucaoAssociado.Tipo.DESCONTO_INDEVIDO},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["status_devolucao"], "revertida")
        self.assertEqual(payload["results"][0]["tipo"], DevolucaoAssociado.Tipo.DESCONTO_INDEVIDO)

    def test_tesoureiro_pode_editar_devolucao_ativa(self):
        associado, contrato, _parcela = self._create_contract_fixture(cpf="77852621379")
        devolucao = DevolucaoAssociado.objects.create(
            contrato=contrato,
            associado=associado,
            tipo=DevolucaoAssociado.Tipo.PAGAMENTO_INDEVIDO,
            data_devolucao=date(2026, 3, 21),
            quantidade_parcelas=1,
            valor=Decimal("150.00"),
            motivo="Depósito em conta divergente.",
            comprovante=SimpleUploadedFile("assoc.pdf", b"arquivo", content_type="application/pdf"),
            nome_comprovante="assoc.pdf",
            nome_snapshot=associado.nome_completo,
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            matricula_snapshot=associado.matricula_orgao,
            agente_snapshot=self.agente.full_name,
            contrato_codigo_snapshot=contrato.codigo,
            realizado_por=self.tesoureiro,
        )
        anexo_extra = DevolucaoAssociadoAnexo.objects.create(
            devolucao=devolucao,
            arquivo=SimpleUploadedFile("extra-antigo.pdf", b"arquivo", content_type="application/pdf"),
            nome_arquivo="extra-antigo.pdf",
        )

        response = self.tes_client.patch(
            f"/api/v1/tesouraria/devolucoes/{devolucao.id}/",
            {
                "tipo": DevolucaoAssociado.Tipo.DESCONTO_INDEVIDO,
                "data_devolucao": "2026-03-25",
                "quantidade_parcelas": 2,
                "valor": "180.00",
                "motivo": "Desconto indevido revisado.",
                "competencia_referencia": "2026-02-01",
                "comprovante": SimpleUploadedFile(
                    "principal-atualizado.pdf",
                    b"novo-principal",
                    content_type="application/pdf",
                ),
                "novos_comprovantes": [
                    SimpleUploadedFile(
                        "apoio-novo.pdf",
                        b"apoio",
                        content_type="application/pdf",
                    )
                ],
                "remover_anexos_ids": [str(anexo_extra.id)],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200, response.json())
        devolucao.refresh_from_db()
        self.assertEqual(devolucao.tipo, DevolucaoAssociado.Tipo.DESCONTO_INDEVIDO)
        self.assertEqual(devolucao.data_devolucao, date(2026, 3, 25))
        self.assertEqual(devolucao.quantidade_parcelas, 2)
        self.assertEqual(devolucao.valor, Decimal("180.00"))
        self.assertEqual(devolucao.motivo, "Desconto indevido revisado.")
        self.assertEqual(devolucao.competencia_referencia, date(2026, 2, 1))
        self.assertEqual(devolucao.nome_comprovante, "principal-atualizado.pdf")
        self.assertEqual(devolucao.anexos.count(), 2)
        self.assertFalse(devolucao.anexos.filter(id=anexo_extra.id).exists())
        self.assertTrue(
            devolucao.anexos.filter(nome_arquivo="assoc.pdf").exists(),
            "o comprovante principal antigo deve ser preservado como anexo extra",
        )
        self.assertTrue(devolucao.anexos.filter(nome_arquivo="apoio-novo.pdf").exists())

    def test_nao_permite_editar_devolucao_revertida_ou_excluida(self):
        associado, contrato, _parcela = self._create_contract_fixture(cpf="77852621380")
        devolucao_revertida = DevolucaoAssociado.objects.create(
            contrato=contrato,
            associado=associado,
            tipo=DevolucaoAssociado.Tipo.PAGAMENTO_INDEVIDO,
            data_devolucao=date(2026, 3, 21),
            valor=Decimal("150.00"),
            motivo="Registro revertido.",
            comprovante=SimpleUploadedFile("revertida.pdf", b"arquivo", content_type="application/pdf"),
            nome_comprovante="revertida.pdf",
            nome_snapshot=associado.nome_completo,
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            matricula_snapshot=associado.matricula_orgao,
            agente_snapshot=self.agente.full_name,
            contrato_codigo_snapshot=contrato.codigo,
            realizado_por=self.tesoureiro,
            revertida_em=self.admin.created_at,
            revertida_por=self.admin,
            motivo_reversao="Ajuste administrativo.",
        )
        devolucao_excluida = DevolucaoAssociado.objects.create(
            contrato=contrato,
            associado=associado,
            tipo=DevolucaoAssociado.Tipo.PAGAMENTO_INDEVIDO,
            data_devolucao=date(2026, 3, 22),
            valor=Decimal("120.00"),
            motivo="Registro excluído.",
            comprovante=SimpleUploadedFile("excluida.pdf", b"arquivo", content_type="application/pdf"),
            nome_comprovante="excluida.pdf",
            nome_snapshot=associado.nome_completo,
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            matricula_snapshot=associado.matricula_orgao,
            agente_snapshot=self.agente.full_name,
            contrato_codigo_snapshot=contrato.codigo,
            realizado_por=self.tesoureiro,
        )
        devolucao_excluida.delete()

        revertida_response = self.coord_client.patch(
            f"/api/v1/tesouraria/devolucoes/{devolucao_revertida.id}/",
            {
                "tipo": DevolucaoAssociado.Tipo.PAGAMENTO_INDEVIDO,
                "data_devolucao": "2026-03-23",
                "quantidade_parcelas": 1,
                "valor": "150.00",
                "motivo": "Tentativa inválida.",
            },
            format="multipart",
        )
        excluida_response = self.coord_client.patch(
            f"/api/v1/tesouraria/devolucoes/{devolucao_excluida.id}/",
            {
                "tipo": DevolucaoAssociado.Tipo.PAGAMENTO_INDEVIDO,
                "data_devolucao": "2026-03-23",
                "quantidade_parcelas": 1,
                "valor": "120.00",
                "motivo": "Tentativa inválida.",
            },
            format="multipart",
        )

        self.assertEqual(revertida_response.status_code, 400, revertida_response.json())
        self.assertIn(
            "Não é possível editar uma devolução já revertida.",
            str(revertida_response.json()),
        )
        self.assertEqual(excluida_response.status_code, 400, excluida_response.json())
        self.assertIn("Registro de devolução não encontrado.", str(excluida_response.json()))

    def test_reversao_e_admin_only(self):
        _associado, contrato, _parcela = self._create_contract_fixture(cpf="77852621371")
        devolucao = DevolucaoAssociado.objects.create(
            contrato=contrato,
            associado=contrato.associado,
            tipo=DevolucaoAssociado.Tipo.PAGAMENTO_INDEVIDO,
            data_devolucao=date(2026, 3, 21),
            valor=Decimal("200.00"),
            motivo="Pagamento em duplicidade.",
            comprovante=SimpleUploadedFile("dup.pdf", b"arquivo", content_type="application/pdf"),
            nome_comprovante="dup.pdf",
            nome_snapshot=contrato.associado.nome_completo,
            cpf_cnpj_snapshot=contrato.associado.cpf_cnpj,
            matricula_snapshot=contrato.associado.matricula_orgao,
            agente_snapshot=self.agente.full_name,
            contrato_codigo_snapshot=contrato.codigo,
            realizado_por=self.tesoureiro,
        )

        forbidden_response = self.tes_client.post(
            f"/api/v1/tesouraria/devolucoes/{devolucao.id}/reverter/",
            {"motivo_reversao": "Teste sem permissão"},
            format="json",
        )
        self.assertEqual(forbidden_response.status_code, 400, forbidden_response.json())

        response = self.admin_client.post(
            f"/api/v1/tesouraria/devolucoes/{devolucao.id}/reverter/",
            {"motivo_reversao": "Correção administrativa"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        devolucao.refresh_from_db()
        self.assertIsNotNone(devolucao.revertida_em)
        self.assertEqual(devolucao.revertida_por, self.admin)
        self.assertEqual(devolucao.motivo_reversao, "Correção administrativa")

    def test_detalhe_do_associado_expoe_devolucoes(self):
        associado, contrato, _parcela = self._create_contract_fixture(cpf="77852621372")
        DevolucaoAssociado.objects.create(
            contrato=contrato,
            associado=associado,
            tipo=DevolucaoAssociado.Tipo.PAGAMENTO_INDEVIDO,
            data_devolucao=date(2026, 3, 21),
            valor=Decimal("150.00"),
            motivo="Depósito em conta divergente.",
            comprovante=SimpleUploadedFile("assoc.pdf", b"arquivo", content_type="application/pdf"),
            nome_comprovante="assoc.pdf",
            nome_snapshot=associado.nome_completo,
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            matricula_snapshot=associado.matricula_orgao,
            agente_snapshot=self.agente.full_name,
            contrato_codigo_snapshot=contrato.codigo,
            realizado_por=self.tesoureiro,
        )

        response = self.admin_client.get(f"/api/v1/associados/{associado.id}/")

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(len(payload["contratos"]), 1)
        self.assertEqual(len(payload["contratos"][0]["devolucoes_associado"]), 1)
        self.assertEqual(
            payload["contratos"][0]["devolucoes_associado"][0]["tipo"],
            DevolucaoAssociado.Tipo.PAGAMENTO_INDEVIDO,
        )
        self.assertEqual(
            len(payload["contratos"][0]["devolucoes_associado"][0]["anexos"]),
            1,
        )

    def test_admin_pode_excluir_devolucao(self):
        associado, contrato, _parcela = self._create_contract_fixture(cpf="77852621373")
        devolucao = DevolucaoAssociado.objects.create(
            contrato=contrato,
            associado=associado,
            tipo=DevolucaoAssociado.Tipo.PAGAMENTO_INDEVIDO,
            data_devolucao=date(2026, 3, 21),
            valor=Decimal("150.00"),
            motivo="Registro para exclusão.",
            comprovante=SimpleUploadedFile("excluir.pdf", b"arquivo", content_type="application/pdf"),
            nome_comprovante="excluir.pdf",
            nome_snapshot=associado.nome_completo,
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            matricula_snapshot=associado.matricula_orgao,
            agente_snapshot=self.agente.full_name,
            contrato_codigo_snapshot=contrato.codigo,
            realizado_por=self.tesoureiro,
        )

        response = self.admin_client.post(
            f"/api/v1/tesouraria/devolucoes/{devolucao.id}/excluir/",
            {"motivo_exclusao": "Registro duplicado."},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        devolucao.refresh_from_db()
        self.assertFalse(DevolucaoAssociado.objects.filter(pk=devolucao.pk).exists())
        self.assertIsNotNone(devolucao.revertida_em)
        self.assertIsNotNone(devolucao.deleted_at)

    def test_fluxo_pos_liquidacao_filtra_contratos_e_registra_desistencia(self):
        associado, contrato, _parcela = self._create_contract_fixture(cpf="77852621374")
        LiquidacaoContrato.objects.create(
            contrato=contrato,
            realizado_por=self.tesoureiro,
            data_liquidacao=date(2026, 3, 15),
            valor_total=Decimal("300.00"),
            comprovante=SimpleUploadedFile(
                "liquidacao.pdf",
                b"arquivo",
                content_type="application/pdf",
            ),
            nome_comprovante="liquidacao.pdf",
            origem_solicitacao=LiquidacaoContrato.OrigemSolicitacao.ADMINISTRACAO,
            observacao="Encerramento operacional",
        )
        Pagamento.objects.create(
            cadastro=associado,
            created_by=self.tesoureiro,
            cpf_cnpj=associado.cpf_cnpj,
            full_name=associado.nome_completo,
            agente_responsavel=self.agente.full_name,
            contrato_codigo=contrato.codigo,
            valor_pago=Decimal("300.00"),
            status=Pagamento.Status.PAGO,
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/devolucoes/contratos/",
            {"fluxo": DevolucaoAssociado.Tipo.DESISTENCIA_POS_LIQUIDACAO},
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["count"], 1)
        row = response.json()["results"][0]
        self.assertEqual(row["contrato_id"], contrato.id)
        self.assertEqual(
            row["tipo_sugerido"],
            DevolucaoAssociado.Tipo.DESISTENCIA_POS_LIQUIDACAO,
        )

        response = self.coord_client.post(
            f"/api/v1/tesouraria/devolucoes/contratos/{contrato.id}/registrar/",
            {
                "tipo": DevolucaoAssociado.Tipo.DESISTENCIA_POS_LIQUIDACAO,
                "data_devolucao": "2026-03-22",
                "quantidade_parcelas": 1,
                "valor": "300.00",
                "motivo": "Cliente desistiu após liquidação e pagamento.",
                "comprovantes": [
                    SimpleUploadedFile(
                        "desistencia.pdf",
                        b"arquivo",
                        content_type="application/pdf",
                    )
                ],
            },
        )
        self.assertEqual(response.status_code, 201, response.json())

        devolucao = DevolucaoAssociado.objects.get(contrato=contrato)
        self.assertEqual(
            devolucao.tipo,
            DevolucaoAssociado.Tipo.DESISTENCIA_POS_LIQUIDACAO,
        )
        self.assertIsNone(devolucao.competencia_referencia)

        response = self.tes_client.get(
            "/api/v1/tesouraria/devolucoes/",
            {"fluxo": DevolucaoAssociado.Tipo.DESISTENCIA_POS_LIQUIDACAO},
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(
            response.json()["results"][0]["tipo"],
            DevolucaoAssociado.Tipo.DESISTENCIA_POS_LIQUIDACAO,
        )
