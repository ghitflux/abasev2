import json
import tempfile
from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import AdminOverrideEvent, Associado, Documento
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import EsteiraItem
from apps.refinanciamento.models import Comprovante


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AdminOverrideApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        admin_role = Role.objects.create(codigo="ADMIN", nome="Administrador")
        agent_role = Role.objects.create(codigo="AGENTE", nome="Agente")
        coordinator_role = Role.objects.create(codigo="COORDENADOR", nome="Coordenador")

        cls.admin = User.objects.create_user(
            email="admin@teste.local",
            password="Senha@123",
            first_name="Admin",
            last_name="ABASE",
        )
        cls.admin.roles.add(admin_role)

        cls.agent = User.objects.create_user(
            email="agente@teste.local",
            password="Senha@123",
            first_name="Agente",
            last_name="ABASE",
        )
        cls.agent.roles.add(agent_role)

        cls.coordinator = User.objects.create_user(
            email="coordenador@teste.local",
            password="Senha@123",
            first_name="Coordenador",
            last_name="ABASE",
        )
        cls.coordinator.roles.add(coordinator_role)

        cls.associado = Associado.objects.create(
            nome_completo="Associado Admin",
            cpf_cnpj="12345678901",
            email="assoc@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            agente_responsavel=cls.agent,
            status=Associado.Status.ATIVO,
        )
        cls.esteira = EsteiraItem.objects.create(
            associado=cls.associado,
            etapa_atual=EsteiraItem.Etapa.ANALISE,
            status=EsteiraItem.Situacao.AGUARDANDO,
        )
        cls.contrato = Contrato.objects.create(
            associado=cls.associado,
            agente=cls.agent,
            status=Contrato.Status.ATIVO,
            valor_bruto=Decimal("1500.00"),
            valor_liquido=Decimal("1200.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("900.00"),
            valor_total_antecipacao=Decimal("900.00"),
            doacao_associado=Decimal("0.00"),
            comissao_agente=Decimal("30.00"),
            data_contrato=date(2026, 1, 1),
        )
        cls.ciclo = Ciclo.objects.create(
            contrato=cls.contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        cls.parcela_jan = Parcela.objects.create(
            ciclo=cls.ciclo,
            associado=cls.associado,
            numero=1,
            referencia_mes=date(2026, 1, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 1, 5),
            status=Parcela.Status.DESCONTADO,
        )
        cls.parcela_fev = Parcela.objects.create(
            ciclo=cls.ciclo,
            associado=cls.associado,
            numero=2,
            referencia_mes=date(2026, 2, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 2, 5),
            status=Parcela.Status.EM_PREVISAO,
        )
        cls.parcela_mar = Parcela.objects.create(
            ciclo=cls.ciclo,
            associado=cls.associado,
            numero=3,
            referencia_mes=date(2026, 3, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 3, 5),
            status=Parcela.Status.EM_PREVISAO,
        )
        cls.documento = Documento.objects.create(
            associado=cls.associado,
            tipo=Documento.Tipo.CPF,
            arquivo=SimpleUploadedFile("doc.pdf", b"doc", content_type="application/pdf"),
        )

    def setUp(self):
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)

        self.agent_client = APIClient()
        self.agent_client.force_authenticate(self.agent)

        self.coordinator_client = APIClient()
        self.coordinator_client.force_authenticate(self.coordinator)

    def test_admin_override_endpoints_are_admin_only(self):
        response = self.agent_client.get(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/editor/"
        )
        self.assertEqual(response.status_code, 403)

    def test_coordenador_can_access_editor_and_save_cycle_layout(self):
        editor = self.coordinator_client.get(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/editor/"
        )
        self.assertEqual(editor.status_code, 200, editor.json())

        response = self.coordinator_client.post(
            f"/api/v1/admin-overrides/contratos/{self.contrato.id}/cycles/layout/",
            {
                "updated_at": self.contrato.updated_at.isoformat(),
                "motivo": "Ajuste operacional pela coordenação",
                "cycles": [
                    {
                        "id": self.ciclo.id,
                        "numero": 1,
                        "data_inicio": "2026-01-01",
                        "data_fim": "2026-03-01",
                        "status": "pendencia",
                        "valor_total": "900.00",
                    }
                ],
                "parcelas": [
                    {
                        "id": self.parcela_jan.id,
                        "cycle_ref": str(self.ciclo.id),
                        "numero": 1,
                        "referencia_mes": "2026-01-01",
                        "valor": "300.00",
                        "data_vencimento": "2026-01-05",
                        "status": "descontado",
                        "layout_bucket": "cycle",
                    },
                    {
                        "id": self.parcela_fev.id,
                        "cycle_ref": str(self.ciclo.id),
                        "numero": 2,
                        "referencia_mes": "2026-02-01",
                        "valor": "300.00",
                        "data_vencimento": "2026-02-05",
                        "status": "nao_descontado",
                        "layout_bucket": "cycle",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.ciclo.refresh_from_db()
        self.assertEqual(self.ciclo.status, Ciclo.Status.PENDENCIA)

    def test_save_all_returns_non_blocking_warnings_for_duplicate_competencia(self):
        response = self.admin_client.post(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/save-all/",
            {
                "motivo": "Salvar com aviso de sobreposição",
                "contratos": [
                    {
                        "id": self.contrato.id,
                        "cycles": {
                            "updated_at": self.contrato.updated_at.isoformat(),
                            "cycles": [
                                {
                                    "id": self.ciclo.id,
                                    "numero": 1,
                                    "data_inicio": "2026-01-01",
                                    "data_fim": "2026-03-01",
                                    "status": "pendencia",
                                    "valor_total": "900.00",
                                },
                                {
                                    "client_key": "ciclo-extra",
                                    "numero": 2,
                                    "data_inicio": "2026-02-01",
                                    "data_fim": "2026-04-01",
                                    "status": "aberto",
                                    "valor_total": "300.00",
                                },
                            ],
                            "parcelas": [
                                {
                                    "id": self.parcela_jan.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 1,
                                    "referencia_mes": "2026-01-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2026-01-05",
                                    "status": "descontado",
                                    "layout_bucket": "cycle",
                                },
                                {
                                    "id": self.parcela_fev.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 2,
                                    "referencia_mes": "2026-02-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2026-02-05",
                                    "status": "nao_descontado",
                                    "layout_bucket": "cycle",
                                },
                                {
                                    "id": self.parcela_mar.id,
                                    "cycle_ref": "ciclo-extra",
                                    "numero": 1,
                                    "referencia_mes": "2026-02-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2026-03-05",
                                    "status": "em_previsao",
                                    "layout_bucket": "cycle",
                                },
                            ],
                        },
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertTrue(payload["warnings"])
        warning_codes = {item["code"] for item in payload["warnings"]}
        self.assertIn("cycle_date_overlap", warning_codes)
        self.assertIn("duplicate_reference_month", warning_codes)

    def test_save_all_returns_structured_validation_error_instead_of_500(self):
        response = self.admin_client.post(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/save-all/",
            {
                "motivo": "Payload inválido do editor",
                "contratos": [
                    {
                        "id": self.contrato.id,
                        "cycles": {
                            "updated_at": self.contrato.updated_at.isoformat(),
                            "cycles": [],
                            "parcelas": [],
                        },
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.json())
        self.assertEqual(response.json()["detail"], "Informe ao menos um ciclo no layout.")

    def test_save_all_allows_november_reference_inside_cycle(self):
        response = self.admin_client.post(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/save-all/",
            {
                "motivo": "Permitir novembro dentro do ciclo",
                "contratos": [
                    {
                        "id": self.contrato.id,
                        "cycles": {
                            "updated_at": self.contrato.updated_at.isoformat(),
                            "cycles": [
                                {
                                    "id": self.ciclo.id,
                                    "numero": 1,
                                    "data_inicio": "2025-11-01",
                                    "data_fim": "2026-01-01",
                                    "status": "aberto",
                                    "valor_total": "900.00",
                                }
                            ],
                            "parcelas": [
                                {
                                    "id": self.parcela_jan.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 1,
                                    "referencia_mes": "2025-11-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2025-11-05",
                                    "status": "descontado",
                                    "layout_bucket": "cycle",
                                },
                                {
                                    "id": self.parcela_fev.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 2,
                                    "referencia_mes": "2025-12-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2025-12-05",
                                    "status": "em_previsao",
                                    "layout_bucket": "cycle",
                                },
                                {
                                    "id": self.parcela_mar.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 3,
                                    "referencia_mes": "2026-01-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2026-01-05",
                                    "status": "em_previsao",
                                    "layout_bucket": "cycle",
                                },
                            ],
                        },
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        contrato_payload = next(
            item for item in response.json()["contratos"] if item["id"] == self.contrato.id
        )
        self.assertEqual(
            [
                parcela["referencia_mes"]
                for parcela in contrato_payload["ciclos"][0]["parcelas"]
            ],
            ["2025-11-01", "2025-12-01", "2026-01-01"],
        )
        self.assertFalse(
            any(
                parcela["referencia_mes"] == "2025-11-01"
                for parcela in contrato_payload["meses_nao_pagos"]
            )
        )
        self.contrato.refresh_from_db()
        self.ciclo.refresh_from_db()
        self.assertTrue(self.contrato.admin_manual_layout_enabled)
        self.assertEqual(self.ciclo.data_inicio, date(2025, 11, 1))
        self.assertEqual(self.ciclo.data_fim, date(2026, 1, 1))
        referencias = list(
            Parcela.all_objects.filter(
                ciclo=self.ciclo,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("numero")
            .values_list("referencia_mes", flat=True)
        )
        self.assertEqual(
            [referencia.isoformat() for referencia in referencias],
            ["2025-11-01", "2025-12-01", "2026-01-01"],
        )

    def test_save_all_recreates_anchor_cycle_when_only_unpaid_rows_are_visible(self):
        contrato = Contrato.objects.create(
            associado=self.associado,
            agente=self.agent,
            status=Contrato.Status.ATIVO,
            valor_bruto=Decimal("500.00"),
            valor_liquido=Decimal("400.00"),
            valor_mensalidade=Decimal("100.00"),
            prazo_meses=1,
            taxa_antecipacao=Decimal("10.00"),
            margem_disponivel=Decimal("200.00"),
            valor_total_antecipacao=Decimal("100.00"),
            doacao_associado=Decimal("0.00"),
            comissao_agente=Decimal("10.00"),
            data_contrato=date(2025, 11, 1),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 11, 1),
            data_fim=date(2025, 11, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("100.00"),
        )
        parcela = Parcela.objects.create(
            ciclo=ciclo,
            associado=self.associado,
            numero=1,
            referencia_mes=date(2025, 11, 1),
            valor=Decimal("100.00"),
            data_vencimento=date(2025, 11, 5),
            status=Parcela.Status.NAO_DESCONTADO,
            layout_bucket=Parcela.LayoutBucket.UNPAID,
        )
        ciclo.soft_delete()

        response = self.admin_client.post(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/save-all/",
            {
                "motivo": "Ajuste sem rebuild para contrato sem ciclo visível",
                "contratos": [
                    {
                        "id": contrato.id,
                        "cycles": {
                            "updated_at": contrato.updated_at.isoformat(),
                            "cycles": [],
                            "parcelas": [
                                {
                                    "id": parcela.id,
                                    "cycle_ref": "",
                                    "numero": 1,
                                    "referencia_mes": "2025-11-01",
                                    "valor": "120.00",
                                    "data_vencimento": "2025-11-05",
                                    "status": "nao_descontado",
                                    "layout_bucket": "unpaid",
                                }
                            ],
                        },
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        contrato.refresh_from_db()
        parcela.refresh_from_db()
        ciclos_ativos = list(contrato.ciclos.filter(deleted_at__isnull=True).order_by("numero", "id"))
        self.assertEqual(len(ciclos_ativos), 1)
        self.assertEqual(parcela.ciclo_id, ciclos_ativos[0].id)
        self.assertEqual(parcela.valor, Decimal("120.00"))
        self.assertTrue(contrato.admin_manual_layout_enabled)

    def test_manual_projection_keeps_november_inside_cycle_when_layout_is_cycle(self):
        contrato = Contrato.objects.create(
            associado=self.associado,
            agente=self.agent,
            status=Contrato.Status.ATIVO,
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("700.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("300.00"),
            valor_total_antecipacao=Decimal("300.00"),
            doacao_associado=Decimal("0.00"),
            comissao_agente=Decimal("30.00"),
            data_contrato=date(2025, 10, 1),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 10, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        for numero, referencia in enumerate(
            [date(2025, 10, 1), date(2025, 11, 1), date(2025, 12, 1)],
            start=1,
        ):
            Parcela.objects.create(
                ciclo=ciclo,
                associado=self.associado,
                numero=numero,
                referencia_mes=referencia,
                valor=Decimal("300.00"),
                data_vencimento=referencia,
                status=Parcela.Status.DESCONTADO if referencia.month < 12 else Parcela.Status.EM_ABERTO,
                data_pagamento=referencia if referencia.month < 12 else None,
                layout_bucket=Parcela.LayoutBucket.CYCLE,
            )

        contrato.admin_manual_layout_enabled = True
        contrato.save(update_fields=["admin_manual_layout_enabled", "updated_at"])

        projection = build_contract_cycle_projection(contrato)

        self.assertTrue(
            any(
                parcela["referencia_mes"] == date(2025, 11, 1)
                for ciclo_payload in projection["cycles"]
                for parcela in ciclo_payload["parcelas"]
            )
        )
        self.assertFalse(
            any(
                row["referencia_mes"] == date(2025, 11, 1)
                for row in projection["unpaid_months"]
            )
        )

    def test_save_all_handles_unpaid_month_without_duplicate_parcela_number(self):
        self.parcela_fev.soft_delete()
        response = self.admin_client.post(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/save-all/",
            {
                "motivo": "Salvar mês não descontado sem colisão de numeração",
                "contratos": [
                    {
                        "id": self.contrato.id,
                        "cycles": {
                            "updated_at": self.contrato.updated_at.isoformat(),
                            "cycles": [
                                {
                                    "id": self.ciclo.id,
                                    "numero": 1,
                                    "data_inicio": "2026-01-01",
                                    "data_fim": "2026-03-01",
                                    "status": "pendencia",
                                    "valor_total": "900.00",
                                }
                            ],
                            "parcelas": [
                                {
                                    "id": self.parcela_jan.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 1,
                                    "referencia_mes": "2026-01-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2026-01-05",
                                    "status": "descontado",
                                    "data_pagamento": None,
                                    "observacao": "",
                                    "layout_bucket": "cycle",
                                },
                                {
                                    "id": self.parcela_mar.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 2,
                                    "referencia_mes": "2026-03-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2026-03-05",
                                    "status": "em_previsao",
                                    "data_pagamento": None,
                                    "observacao": "",
                                    "layout_bucket": "cycle",
                                },
                                {
                                    "id": None,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 1,
                                    "referencia_mes": "2026-02-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2026-02-05",
                                    "status": "nao_descontado",
                                    "data_pagamento": None,
                                    "observacao": "Competência fora do ciclo regular",
                                    "layout_bucket": "unpaid",
                                },
                            ],
                        },
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        active_parcelas = list(
            Parcela.all_objects.filter(
                ciclo=self.ciclo,
                deleted_at__isnull=True,
            ).order_by("numero", "id")
        )
        numeros = [parcela.numero for parcela in active_parcelas]
        self.assertEqual(len(numeros), len(set(numeros)))
        unpaid_refs = [
            parcela.referencia_mes.isoformat()
            for parcela in active_parcelas
            if parcela.layout_bucket == Parcela.LayoutBucket.UNPAID
        ]
        self.assertIn("2026-02-01", unpaid_refs)

    def test_save_all_returns_validation_message_for_invalid_cycle_reference(self):
        response = self.admin_client.post(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/save-all/",
            {
                "motivo": "Salvar com ciclo inválido",
                "contratos": [
                    {
                        "id": self.contrato.id,
                        "cycles": {
                            "updated_at": self.contrato.updated_at.isoformat(),
                            "cycles": [
                                {
                                    "id": self.ciclo.id,
                                    "numero": 1,
                                    "data_inicio": "2026-01-01",
                                    "data_fim": "2026-03-01",
                                    "status": "aberto",
                                    "valor_total": "900.00",
                                }
                            ],
                            "parcelas": [
                                {
                                    "id": self.parcela_jan.id,
                                    "cycle_ref": "ciclo-inexistente",
                                    "numero": 1,
                                    "referencia_mes": "2026-01-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2026-01-05",
                                    "status": "descontado",
                                    "layout_bucket": "cycle",
                                }
                            ],
                        },
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn(
            "Parcela sem ciclo de destino válido.",
            json.dumps(response.json(), ensure_ascii=False),
        )

    def test_admin_can_save_manual_cycle_layout_and_rebuild_keeps_it(self):
        response = self.admin_client.post(
            f"/api/v1/admin-overrides/contratos/{self.contrato.id}/cycles/layout/",
            {
                "updated_at": self.contrato.updated_at.isoformat(),
                "motivo": "Organização manual dos ciclos",
                "cycles": [
                    {
                        "id": self.ciclo.id,
                        "numero": 1,
                        "data_inicio": "2026-01-01",
                        "data_fim": "2026-03-01",
                        "status": "aberto",
                        "valor_total": "600.00",
                    },
                    {
                        "client_key": "novo-ciclo",
                        "numero": 2,
                        "data_inicio": "2026-02-01",
                        "data_fim": "2026-02-01",
                        "status": "futuro",
                        "valor_total": "300.00",
                    },
                ],
                "parcelas": [
                    {
                        "id": self.parcela_jan.id,
                        "cycle_ref": str(self.ciclo.id),
                        "numero": 1,
                        "referencia_mes": "2026-01-01",
                        "valor": "300.00",
                        "data_vencimento": "2026-01-05",
                        "status": "descontado",
                        "layout_bucket": "cycle",
                    },
                    {
                        "id": self.parcela_mar.id,
                        "cycle_ref": str(self.ciclo.id),
                        "numero": 2,
                        "referencia_mes": "2026-03-01",
                        "valor": "300.00",
                        "data_vencimento": "2026-03-05",
                        "status": "em_previsao",
                        "layout_bucket": "cycle",
                    },
                    {
                        "id": self.parcela_fev.id,
                        "cycle_ref": "novo-ciclo",
                        "numero": 1,
                        "referencia_mes": "2026-02-01",
                        "valor": "300.00",
                        "data_vencimento": "2026-02-05",
                        "status": "em_previsao",
                        "layout_bucket": "cycle",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.contrato.refresh_from_db()
        self.assertTrue(self.contrato.admin_manual_layout_enabled)

        projection = build_contract_cycle_projection(self.contrato)
        ordered_cycles = sorted(projection["cycles"], key=lambda item: item["numero"])
        self.assertEqual(len(ordered_cycles), 2)
        self.assertEqual(
            [parcela["referencia_mes"].isoformat() for parcela in ordered_cycles[0]["parcelas"]],
            ["2026-01-01", "2026-03-01"],
        )
        self.assertEqual(
            [parcela["referencia_mes"].isoformat() for parcela in ordered_cycles[1]["parcelas"]],
            ["2026-02-01"],
        )

        rebuild_contract_cycle_state(self.contrato, execute=True)
        projection_after_rebuild = build_contract_cycle_projection(self.contrato)
        ordered_after_rebuild = sorted(
            projection_after_rebuild["cycles"],
            key=lambda item: item["numero"],
        )
        self.assertEqual(
            [parcela["referencia_mes"].isoformat() for parcela in ordered_after_rebuild[0]["parcelas"]],
            ["2026-01-01", "2026-03-01"],
        )
        self.assertEqual(
            [parcela["referencia_mes"].isoformat() for parcela in ordered_after_rebuild[1]["parcelas"]],
            ["2026-02-01"],
        )
        self.assertTrue(
            AdminOverrideEvent.objects.filter(
                associado=self.associado,
                escopo=AdminOverrideEvent.Scope.CICLOS,
            ).exists()
        )

    def test_admin_save_all_keeps_november_2025_inside_cycle_for_manual_layout(self):
        self.contrato.data_contrato = date(2025, 10, 1)
        self.contrato.data_aprovacao = date(2025, 10, 1)
        self.contrato.data_primeira_mensalidade = date(2025, 10, 1)
        self.contrato.mes_averbacao = date(2025, 10, 1)
        self.contrato.auxilio_liberado_em = date(2025, 10, 1)
        self.contrato.save(
            update_fields=[
                "data_contrato",
                "data_aprovacao",
                "data_primeira_mensalidade",
                "mes_averbacao",
                "auxilio_liberado_em",
                "updated_at",
            ]
        )
        self.ciclo.data_inicio = date(2025, 10, 1)
        self.ciclo.data_fim = date(2025, 12, 1)
        self.ciclo.save(update_fields=["data_inicio", "data_fim", "updated_at"])
        self.parcela_jan.referencia_mes = date(2025, 10, 1)
        self.parcela_jan.data_vencimento = date(2025, 10, 5)
        self.parcela_jan.save(update_fields=["referencia_mes", "data_vencimento", "updated_at"])
        self.parcela_fev.referencia_mes = date(2025, 11, 1)
        self.parcela_fev.data_vencimento = date(2025, 11, 5)
        self.parcela_fev.status = Parcela.Status.DESCONTADO
        self.parcela_fev.data_pagamento = date(2025, 11, 5)
        self.parcela_fev.save(
            update_fields=[
                "referencia_mes",
                "data_vencimento",
                "status",
                "data_pagamento",
                "updated_at",
            ]
        )
        self.parcela_mar.referencia_mes = date(2025, 12, 1)
        self.parcela_mar.data_vencimento = date(2025, 12, 5)
        self.parcela_mar.status = Parcela.Status.DESCONTADO
        self.parcela_mar.data_pagamento = date(2025, 12, 5)
        self.parcela_mar.save(
            update_fields=[
                "referencia_mes",
                "data_vencimento",
                "status",
                "data_pagamento",
                "updated_at",
            ]
        )

        response = self.admin_client.post(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/save-all/",
            {
                "motivo": "Ajuste manual para manter novembro no ciclo",
                "contratos": [
                    {
                        "id": self.contrato.id,
                        "cycles": {
                            "updated_at": self.contrato.updated_at.isoformat(),
                            "cycles": [
                                {
                                    "id": self.ciclo.id,
                                    "numero": 1,
                                    "data_inicio": "2025-10-01",
                                    "data_fim": "2025-12-01",
                                    "status": "aberto",
                                    "valor_total": "900.00",
                                }
                            ],
                            "parcelas": [
                                {
                                    "id": self.parcela_jan.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 1,
                                    "referencia_mes": "2025-10-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2025-10-05",
                                    "status": "descontado",
                                    "layout_bucket": "cycle",
                                },
                                {
                                    "id": self.parcela_fev.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 2,
                                    "referencia_mes": "2025-11-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2025-11-05",
                                    "status": "descontado",
                                    "data_pagamento": "2025-11-05",
                                    "layout_bucket": "cycle",
                                },
                                {
                                    "id": self.parcela_mar.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 3,
                                    "referencia_mes": "2025-12-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2025-12-05",
                                    "status": "descontado",
                                    "data_pagamento": "2025-12-05",
                                    "layout_bucket": "cycle",
                                },
                            ],
                        },
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.contrato.refresh_from_db()
        self.assertTrue(self.contrato.admin_manual_layout_enabled)

        projection = build_contract_cycle_projection(self.contrato)
        ordered_cycles = sorted(projection["cycles"], key=lambda item: item["numero"])
        self.assertEqual(len(ordered_cycles), 1)
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in ordered_cycles[0]["parcelas"]],
            [date(2025, 10, 1), date(2025, 11, 1), date(2025, 12, 1)],
        )
        self.assertFalse(
            any(
                row["referencia_mes"] == date(2025, 11, 1)
                for row in projection["unpaid_months"]
            )
        )

    def test_admin_can_override_associado_and_contract_core_with_audit(self):
        response = self.admin_client.post(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/core/",
            {
                "updated_at": self.associado.updated_at.isoformat(),
                "contrato_updated_at": self.contrato.updated_at.isoformat(),
                "motivo": "Correção operacional do cadastro",
                "nome_completo": "Associado Admin Ajustado",
                "status": Associado.Status.INADIMPLENTE,
                "percentual_repasse": "12.50",
                "dados_bancarios": {
                    "banco": "001",
                    "agencia": "1234",
                    "conta": "998877",
                    "tipo_conta": "corrente",
                },
                "valor_bruto_total": "1800.00",
                "mensalidade": "350.00",
                "status_contrato": Contrato.Status.ENCERRADO,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.associado.refresh_from_db()
        self.contrato.refresh_from_db()
        self.assertEqual(self.associado.nome_completo, "Associado Admin Ajustado")
        self.assertEqual(self.associado.status, Associado.Status.INADIMPLENTE)
        self.assertEqual(self.associado.agencia, "1234")
        self.assertEqual(self.associado.auxilio_taxa, Decimal("12.50"))
        self.assertEqual(self.contrato.valor_bruto, Decimal("1800.00"))
        self.assertEqual(self.contrato.valor_mensalidade, Decimal("350.00"))
        self.assertEqual(self.contrato.status, Contrato.Status.ENCERRADO)
        self.assertTrue(
            AdminOverrideEvent.objects.filter(
                associado=self.associado,
                escopo=AdminOverrideEvent.Scope.ASSOCIADO,
            ).exists()
        )

    def test_admin_can_override_esteira_and_register_transition(self):
        response = self.admin_client.post(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/esteira/status/",
            {
                "updated_at": self.esteira.updated_at.isoformat(),
                "motivo": "Reclassificação administrativa",
                "etapa_atual": EsteiraItem.Etapa.COORDENACAO,
                "status": EsteiraItem.Situacao.EM_ANDAMENTO,
                "prioridade": 1,
                "observacao": "Ajuste direto pelo admin",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.esteira.refresh_from_db()
        self.assertEqual(self.esteira.etapa_atual, EsteiraItem.Etapa.COORDENACAO)
        self.assertEqual(self.esteira.status, EsteiraItem.Situacao.EM_ANDAMENTO)
        self.assertEqual(self.esteira.prioridade, 1)
        self.assertEqual(self.esteira.observacao, "Ajuste direto pelo admin")
        self.assertTrue(
            self.esteira.transicoes.filter(
                acao="admin_override",
                observacao="Reclassificação administrativa",
            ).exists()
        )
        self.assertTrue(
            AdminOverrideEvent.objects.filter(
                associado=self.associado,
                escopo=AdminOverrideEvent.Scope.ESTEIRA,
            ).exists()
        )

    def test_admin_can_save_all_pending_blocks_in_single_request(self):
        response = self.admin_client.post(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/save-all/",
            {
                "motivo": "Ajuste administrativo consolidado",
                "contratos": [
                    {
                        "id": self.contrato.id,
                        "core": {
                            "updated_at": self.contrato.updated_at.isoformat(),
                            "status": Contrato.Status.ENCERRADO,
                            "valor_liquido": "1400.00",
                        },
                        "cycles": {
                            "updated_at": self.contrato.updated_at.isoformat(),
                            "cycles": [
                                {
                                    "id": self.ciclo.id,
                                    "numero": 1,
                                    "data_inicio": "2026-01-01",
                                    "data_fim": "2026-03-01",
                                    "status": "aberto",
                                    "valor_total": "900.00",
                                }
                            ],
                            "parcelas": [
                                {
                                    "id": self.parcela_jan.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 1,
                                    "referencia_mes": "2026-01-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2026-01-05",
                                    "status": "descontado",
                                    "layout_bucket": "cycle",
                                },
                                {
                                    "id": self.parcela_fev.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 2,
                                    "referencia_mes": "2026-02-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2026-02-10",
                                    "status": "em_previsao",
                                    "layout_bucket": "cycle",
                                },
                                {
                                    "id": self.parcela_mar.id,
                                    "cycle_ref": str(self.ciclo.id),
                                    "numero": 3,
                                    "referencia_mes": "2026-03-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2026-03-05",
                                    "status": "em_previsao",
                                    "layout_bucket": "cycle",
                                },
                            ],
                        },
                    }
                ],
                "esteira": {
                    "updated_at": self.esteira.updated_at.isoformat(),
                    "etapa_atual": EsteiraItem.Etapa.COORDENACAO,
                    "status": EsteiraItem.Situacao.EM_ANDAMENTO,
                    "prioridade": 2,
                    "observacao": "Reclassificado no mesmo salvamento",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.contrato.refresh_from_db()
        self.parcela_fev.refresh_from_db()
        self.esteira.refresh_from_db()
        self.assertEqual(self.contrato.status, Contrato.Status.ENCERRADO)
        self.assertEqual(self.contrato.valor_liquido, Decimal("1400.00"))
        self.assertEqual(self.parcela_fev.data_vencimento, date(2026, 2, 10))
        self.assertEqual(self.esteira.etapa_atual, EsteiraItem.Etapa.COORDENACAO)
        self.assertEqual(self.esteira.status, EsteiraItem.Situacao.EM_ANDAMENTO)
        self.assertEqual(
            AdminOverrideEvent.objects.filter(
                associado=self.associado,
                escopo=AdminOverrideEvent.Scope.CONTRATO,
            ).count(),
            1,
        )
        self.assertEqual(
            AdminOverrideEvent.objects.filter(
                associado=self.associado,
                escopo=AdminOverrideEvent.Scope.CICLOS,
            ).count(),
            1,
        )
        self.assertEqual(
            AdminOverrideEvent.objects.filter(
                associado=self.associado,
                escopo=AdminOverrideEvent.Scope.ESTEIRA,
            ).count(),
            1,
        )

    def test_admin_save_all_keeps_november_2025_inside_manual_cycle_when_marked_as_cycle(self):
        associado = Associado.objects.create(
            nome_completo="Associado Novembro Manual",
            cpf_cnpj="12345678909",
            email="novembro@teste.local",
            telefone="86999999998",
            orgao_publico="SEFAZ",
            agente_responsavel=self.agent,
            status=Associado.Status.ATIVO,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agent,
            status=Contrato.Status.ATIVO,
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("900.00"),
            valor_total_antecipacao=Decimal("900.00"),
            doacao_associado=Decimal("0.00"),
            comissao_agente=Decimal("30.00"),
            data_contrato=date(2025, 10, 1),
            data_aprovacao=date(2025, 10, 1),
            data_primeira_mensalidade=date(2025, 10, 1),
            mes_averbacao=date(2025, 10, 1),
            auxilio_liberado_em=date(2025, 10, 1),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 10, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.FECHADO,
            valor_total=Decimal("900.00"),
        )
        parcela_out = Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=date(2025, 10, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 10, 5),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 10, 5),
        )
        parcela_nov = Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=2,
            referencia_mes=date(2025, 11, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 11, 5),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 11, 5),
        )
        parcela_dec = Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=3,
            referencia_mes=date(2025, 12, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 12, 5),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 12, 5),
        )

        response = self.admin_client.post(
            f"/api/v1/admin-overrides/associados/{associado.id}/save-all/",
            {
                "motivo": "Manter novembro dentro do ciclo manual",
                "contratos": [
                    {
                        "id": contrato.id,
                        "cycles": {
                            "updated_at": contrato.updated_at.isoformat(),
                            "cycles": [
                                {
                                    "id": ciclo.id,
                                    "numero": 1,
                                    "data_inicio": "2025-10-01",
                                    "data_fim": "2025-12-01",
                                    "status": "concluido",
                                    "valor_total": "900.00",
                                }
                            ],
                            "parcelas": [
                                {
                                    "id": parcela_out.id,
                                    "cycle_ref": str(ciclo.id),
                                    "numero": 1,
                                    "referencia_mes": "2025-10-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2025-10-05",
                                    "status": "descontado",
                                    "data_pagamento": "2025-10-05",
                                    "observacao": "",
                                    "layout_bucket": "cycle",
                                },
                                {
                                    "id": parcela_nov.id,
                                    "cycle_ref": str(ciclo.id),
                                    "numero": 2,
                                    "referencia_mes": "2025-11-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2025-11-05",
                                    "status": "descontado",
                                    "data_pagamento": "2025-11-05",
                                    "observacao": "",
                                    "layout_bucket": "cycle",
                                },
                                {
                                    "id": parcela_dec.id,
                                    "cycle_ref": str(ciclo.id),
                                    "numero": 3,
                                    "referencia_mes": "2025-12-01",
                                    "valor": "300.00",
                                    "data_vencimento": "2025-12-05",
                                    "status": "descontado",
                                    "data_pagamento": "2025-12-05",
                                    "observacao": "",
                                    "layout_bucket": "cycle",
                                },
                            ],
                        },
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        contrato.refresh_from_db()
        ciclo.refresh_from_db()
        self.assertTrue(contrato.admin_manual_layout_enabled)
        self.assertEqual(ciclo.status, Ciclo.Status.FECHADO)

        payload = response.json()
        contrato_payload = payload["contratos"][0]
        ciclo_payload = contrato_payload["ciclos"][0]
        self.assertEqual(ciclo_payload["status"], Ciclo.Status.FECHADO)
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in ciclo_payload["parcelas"]],
            ["2025-10-01", "2025-11-01", "2025-12-01"],
        )
        projection = build_contract_cycle_projection(contrato)
        self.assertEqual(projection["cycles"][0]["status"], Ciclo.Status.FECHADO)
        self.assertEqual(projection["cycles"][0]["status_visual_label"], "Concluído")
        self.assertEqual(projection["cycles"][0]["fase_ciclo"], "ciclo_renovado")
        self.assertNotIn(
            "2025-11-01",
            [item["referencia_mes"] for item in contrato_payload["meses_nao_pagos"]],
        )

        projection = build_contract_cycle_projection(contrato)
        ordered_cycles = sorted(projection["cycles"], key=lambda item: item["numero"])
        self.assertEqual(
            [parcela["referencia_mes"].isoformat() for parcela in ordered_cycles[0]["parcelas"]],
            ["2025-10-01", "2025-11-01", "2025-12-01"],
        )
        self.assertNotIn(
            date(2025, 11, 1),
            [item["referencia_mes"] for item in projection["unpaid_months"]],
        )

        detail = self.admin_client.get(f"/api/v1/associados/{associado.id}/")
        self.assertEqual(detail.status_code, 200, detail.json())
        detail_contrato = detail.json()["contratos"][0]
        detail_ciclo = detail_contrato["ciclos"][0]
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in detail_ciclo["parcelas"]],
            ["2025-10-01", "2025-11-01", "2025-12-01"],
        )
        self.assertNotIn(
            "2025-11-01",
            [item["referencia_mes"] for item in detail_contrato["meses_nao_pagos"]],
        )

    def test_admin_save_all_aborts_everything_on_conflict(self):
        response = self.admin_client.post(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/save-all/",
            {
                "motivo": "Tentativa com versao desatualizada",
                "contratos": [
                    {
                        "id": self.contrato.id,
                        "core": {
                            "updated_at": "2020-01-01T00:00:00Z",
                            "status": Contrato.Status.ENCERRADO,
                        },
                    }
                ],
                "esteira": {
                    "updated_at": self.esteira.updated_at.isoformat(),
                    "etapa_atual": EsteiraItem.Etapa.COORDENACAO,
                    "status": EsteiraItem.Situacao.EM_ANDAMENTO,
                    "prioridade": 1,
                    "observacao": "Nao deve persistir",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409, response.json())
        self.contrato.refresh_from_db()
        self.esteira.refresh_from_db()
        self.assertEqual(self.contrato.status, Contrato.Status.ATIVO)
        self.assertEqual(self.esteira.etapa_atual, EsteiraItem.Etapa.ANALISE)
        self.assertFalse(
            AdminOverrideEvent.objects.filter(
                associado=self.associado,
                motivo="Tentativa com versao desatualizada",
            ).exists()
        )

    def test_admin_can_version_document_and_keep_history(self):
        response = self.admin_client.post(
            f"/api/v1/admin-overrides/documentos/{self.documento.id}/versionar/",
            {
                "motivo": "Atualização do documento",
                "status": Documento.Status.APROVADO,
                "arquivo": SimpleUploadedFile(
                    "novo.pdf",
                    b"novo-conteudo",
                    content_type="application/pdf",
                ),
            },
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.documento.refresh_from_db()
        self.assertIsNotNone(self.documento.deleted_at)
        self.assertEqual(
            Documento.objects.filter(
                associado=self.associado,
                tipo=Documento.Tipo.CPF,
                deleted_at__isnull=True,
            ).count(),
            1,
        )
        self.assertTrue(
            AdminOverrideEvent.objects.filter(
                associado=self.associado,
                escopo=AdminOverrideEvent.Scope.DOCUMENTO,
            ).exists()
        )

    def test_admin_can_attach_cycle_comprovantes_and_editor_payload_returns_them(self):
        response = self.admin_client.post(
            "/api/v1/admin-overrides/comprovantes/",
            {
                "ciclo_id": str(self.ciclo.id),
                "motivo": "Inclusão de comprovantes no ciclo",
                "tipo": Comprovante.Tipo.OUTRO,
                "papel": Comprovante.Papel.OPERACIONAL,
                "origem": Comprovante.Origem.OUTRO,
                "status_validacao": Comprovante.StatusValidacao.PENDENTE,
                "arquivos": [
                    SimpleUploadedFile(
                        "ciclo-1.pdf",
                        b"arquivo-1",
                        content_type="application/pdf",
                    ),
                    SimpleUploadedFile(
                        "ciclo-2.pdf",
                        b"arquivo-2",
                        content_type="application/pdf",
                    ),
                ],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(
            Comprovante.objects.filter(ciclo=self.ciclo, deleted_at__isnull=True).count(),
            2,
        )
        contrato_payload = response.json()["contratos"][0]
        ciclo_payload = contrato_payload["ciclos"][0]
        self.assertEqual(len(ciclo_payload["comprovantes_ciclo"]), 2)
        self.assertEqual(ciclo_payload["comprovantes_ciclo"][0]["status_validacao"], "pendente")

    def test_editor_endpoint_returns_manual_layout_comprovantes_with_expected_shape(self):
        self.contrato.admin_manual_layout_enabled = True
        self.contrato.save(update_fields=["admin_manual_layout_enabled", "updated_at"])

        comprovante = Comprovante.objects.create(
            contrato=self.contrato,
            ciclo=self.ciclo,
            tipo=Comprovante.Tipo.OUTRO,
            papel=Comprovante.Papel.OPERACIONAL,
            arquivo=SimpleUploadedFile(
                "manual-layout.pdf",
                b"manual-layout",
                content_type="application/pdf",
            ),
            nome_original="manual-layout.pdf",
            origem=Comprovante.Origem.OUTRO,
            enviado_por=self.admin,
        )

        response = self.admin_client.get(
            f"/api/v1/admin-overrides/associados/{self.associado.id}/editor/"
        )

        self.assertEqual(response.status_code, 200, response.json())
        ciclo_payload = response.json()["contratos"][0]["ciclos"][0]
        self.assertEqual(len(ciclo_payload["comprovantes_ciclo"]), 1)
        comprovante_payload = ciclo_payload["comprovantes_ciclo"][0]
        self.assertEqual(comprovante_payload["id"], comprovante.id)
        self.assertEqual(comprovante_payload["nome_original"], "manual-layout.pdf")
        self.assertIn("arquivo", comprovante_payload)
        self.assertTrue(comprovante_payload["arquivo"])
