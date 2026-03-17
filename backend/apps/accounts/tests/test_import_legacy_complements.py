from __future__ import annotations

from datetime import date

from django.test import TestCase

from apps.accounts.management.commands.import_legacy_complements import Command
from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Contrato
from apps.esteira.models import DocIssue, DocReupload, EsteiraItem
from apps.tesouraria.models import Confirmacao


class ImportLegacyComplementsCommandTestCase(TestCase):
    def make_command(self) -> Command:
        command = Command()
        command.stdout.write = lambda *_args, **_kwargs: None
        command.stderr.write = lambda *_args, **_kwargs: None
        command._ensure_runtime_state()
        return command

    def setUp(self):
        super().setUp()
        self.role_analista = Role.objects.create(codigo="ANALISTA", nome="Analista")
        self.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")

        self.analista = User.objects.create_user(
            email="analista@example.com",
            password="senha",
            first_name="Analista",
        )
        self.analista.roles.add(self.role_analista)

        self.agente = User.objects.create_user(
            email="agente@example.com",
            password="senha",
            first_name="Agente",
        )
        self.agente.roles.add(self.role_agente)

    def test_tesouraria_confirmacao_usa_mes_da_averbacao_quando_ambas_confirmadas(self):
        associado = Associado.objects.create(
            cpf_cnpj="12345678900",
            nome_completo="Associado Confirmacao",
        )
        contrato = Contrato.objects.create(
            associado=associado,
            codigo="CTR-CONF-001",
            data_contrato=date(2026, 1, 1),
            data_aprovacao=date(2026, 1, 1),
        )
        command = self.make_command()
        command._cad_map[10] = associado.pk
        command._legacy_cad_contract_codes[10] = contrato.codigo

        summary = {"source_rows": 1, "created": 0, "updated": 0, "processed": 0, "skipped": 0}
        command._import_tesouraria_confirmacoes(
            [
                {
                    "cad_id": "10",
                    "ligacao_recebida": "1",
                    "ligacao_recebida_at": "'2026-01-20 09:00:00'",
                    "averbacao_confirmada": "1",
                    "averbacao_confirmada_at": "'2026-02-05 10:30:00'",
                    "created_at": "'2026-01-19 08:00:00'",
                    "updated_at": "'2026-02-05 10:30:00'",
                    "link_chamada": "'https://exemplo.test/chamada'",
                }
            ],
            summary,
        )

        confirmacoes = list(Confirmacao.objects.all())
        self.assertEqual(len(confirmacoes), 1)
        self.assertEqual(confirmacoes[0].tipo, Confirmacao.Tipo.AVERBACAO)
        self.assertEqual(confirmacoes[0].competencia, date(2026, 2, 1))
        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["created"], 1)

    def test_assumption_resolve_associadodois_com_esteira_auxiliar(self):
        command = self.make_command()
        command._user_map[33] = self.analista.pk
        command._associadodois_rows[3] = {
            "id": "3",
            "doc_type": "'CPF'",
            "cpf_cnpj": "'32747519368'",
            "full_name": "'Associado Auxiliar'",
            "email": "'auxiliar@example.com'",
            "cellphone": "'(86) 99999-9999'",
            "created_at": "'2026-01-22 08:27:59'",
            "updated_at": "'2026-01-22 08:31:24'",
            "contrato_codigo_contrato": "'CTR-AUX-001'",
        }

        summary = {"source_rows": 1, "created": 0, "updated": 0, "processed": 0, "skipped": 0}
        command._import_agente_cadastro_assumptions(
            [
                {
                    "agente_cadastro_id": "NULL",
                    "associadodois_cadastro_id": "3",
                    "analista_id": "33",
                    "status": "'assumido'",
                    "assumido_em": "'2026-01-22 08:31:24'",
                    "heartbeat_at": "'2026-01-22 08:31:24'",
                    "created_at": "'2026-01-22 08:27:59'",
                    "updated_at": "'2026-01-22 08:31:24'",
                }
            ],
            summary,
        )

        associado = Associado.objects.get(cpf_cnpj="32747519368")
        esteira = EsteiraItem.objects.get(associado=associado)
        self.assertEqual(esteira.analista_responsavel_id, self.analista.id)
        self.assertEqual(esteira.status, EsteiraItem.Situacao.EM_ANDAMENTO)
        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["skipped"], 0)

    def test_reupload_sem_issue_legacy_cria_issue_sintetica_estavel_e_idempotente(self):
        associado = Associado.objects.create(
            cpf_cnpj="69923574334",
            nome_completo="Associado Reupload",
        )
        command = self.make_command()
        command._cad_map[512] = associado.pk
        command._user_map[304] = self.agente.pk

        row = {
            "id": "482",
            "agente_doc_issue_id": "399",
            "agente_cadastro_id": "512",
            "uploaded_by_user_id": "304",
            "cpf_cnpj": "'69923574334'",
            "contrato_codigo_contrato": "'CTR-20251201150505-UIPZK'",
            "file_original_name": "'almeida rg frente.jpg'",
            "file_stored_name": "'20251201_151848-m1MRP5s3.jpg'",
            "file_relative_path": "'storage/agent-reuploads/399/20251201_151848-m1MRP5s3.jpg'",
            "file_mime": "'image/jpeg'",
            "file_size_bytes": "107448",
            "status": "'accepted'",
            "uploaded_at": "'2025-12-01 15:18:48'",
            "notes": "'Reenvio via formulário do agente (documento nomeado: cpf_frente).'",
            "extras": "'{}'",
            "created_at": "'2025-12-01 15:18:48'",
            "updated_at": "'2025-12-01 15:28:24'",
        }

        first_summary = {"source_rows": 1, "created": 0, "updated": 0, "processed": 0, "skipped": 0}
        second_summary = {"source_rows": 1, "created": 0, "updated": 0, "processed": 0, "skipped": 0}

        command._import_agente_doc_reuploads([row], first_summary)
        second_command = self.make_command()
        second_command._cad_map[512] = associado.pk
        second_command._user_map[304] = self.agente.pk
        second_command._bootstrap_doc_issue_map([])
        second_command._import_agente_doc_reuploads([row], second_summary)

        issue = DocIssue.objects.get(associado=associado)
        self.assertIn("[legacy-missing-issue:399]", issue.mensagem)
        self.assertEqual(DocIssue.objects.count(), 1)
        self.assertEqual(DocReupload.objects.count(), 1)
        self.assertEqual(first_summary["processed"], 1)
        self.assertEqual(second_summary["processed"], 1)
        self.assertEqual(second_summary["created"], 0)

    def test_margem_snapshot_preserva_linhas_duplicadas_exatas_sem_reduplicar(self):
        associado = Associado.objects.create(
            cpf_cnpj="01117539377",
            nome_completo="Associado Snapshot",
        )
        command = self.make_command()
        command._cad_map[1] = associado.pk
        command._user_map[2] = self.agente.pk

        row = {
            "agente_cadastro_id": "1",
            "agente_user_id": "2",
            "percentual_anterior": "NULL",
            "percentual_novo": "10.00",
            "mensalidade": "150.00",
            "margem_disponivel": "315.00",
            "auxilio_valor_anterior": "NULL",
            "auxilio_valor_novo": "0.00",
            "changed_by_user_id": "NULL",
            "motivo": "''",
            "created_at": "'2026-03-05 15:55:25'",
            "updated_at": "'2026-03-05 15:55:25'",
        }

        first_summary = {"source_rows": 2, "created": 0, "updated": 0, "processed": 0, "skipped": 0}
        second_summary = {"source_rows": 2, "created": 0, "updated": 0, "processed": 0, "skipped": 0}

        command._import_agente_margem_snapshots([row, row], first_summary)
        second_command = self.make_command()
        second_command._cad_map[1] = associado.pk
        second_command._user_map[2] = self.agente.pk
        second_command._import_agente_margem_snapshots([row, row], second_summary)

        self.assertEqual(associado.margem_snapshots.count(), 2)
        self.assertEqual(first_summary["created"], 2)
        self.assertEqual(second_summary["created"], 0)
