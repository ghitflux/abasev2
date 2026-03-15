from __future__ import annotations

from django.test import TestCase

from apps.accounts.management.commands.import_legacy_data import (
    Command,
    _json,
    extract_table_data,
)
from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Contrato


class ImportLegacyDataCommandTestCase(TestCase):
    def make_command(self) -> Command:
        command = Command()
        command.stdout.write = lambda *_args, **_kwargs: None
        command.stderr.write = lambda *_args, **_kwargs: None
        command._user_map = {}
        command._role_map = {}
        command._cad_map = {}
        command._refi_map = {}
        command._pag_map = {}
        command._tes_pag_map = {}
        command._doc_issue_map = {}
        command._esteira_map = {}
        command._legacy_user_rows = {}
        command._agent_lookup = {}
        command._agent_first_token_lookup = {}
        command._agent_lookup_built = False
        return command

    def test_import_role_user_maps_supported_roles_and_sets_admin_flags(self):
        command = self.make_command()

        command._import_roles(
            [
                {"id": "1", "name": "'admin'"},
                {"id": "2", "name": "'associado'"},
            ]
        )
        command._import_users(
            [
                {
                    "id": "7",
                    "name": "'Admin Legacy'",
                    "email": "'admin@abase.com'",
                    "password": "NULL",
                    "must_set_password": "0",
                    "profile_photo_path": "NULL",
                }
            ]
        )
        command._import_role_user([{"user_id": "7", "role_id": "1"}])

        user = User.objects.get(email="admin@abase.com")
        self.assertEqual(list(user.roles.values_list("codigo", flat=True)), ["ADMIN"])
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(list(Role.objects.order_by("codigo").values_list("codigo", flat=True)), ["ADMIN"])

    def test_extract_table_data_handles_parentheses_inside_strings(self):
        sql = """
        INSERT INTO `roles` (`id`, `name`) VALUES
        (1, 'admin'),
        (2, 'analista (temporario)');
        """

        rows = extract_table_data(sql, "roles")

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["name"], "'analista (temporario)'")

    def test_json_helper_parses_mysql_escaped_json_blob(self):
        raw = (
            "'[{\\\"field\\\":\\\"cpf_frente\\\","
            "\\\"relative_path\\\":\\\"uploads\\\\/associados\\\\/2\\\\/arquivo.pdf\\\"}]'"
        )

        parsed = _json(raw)

        self.assertEqual(parsed[0]["field"], "cpf_frente")
        self.assertEqual(
            parsed[0]["relative_path"],
            "uploads/associados/2/arquivo.pdf",
        )

    def test_import_agente_cadastros_resolves_agent_by_normalized_snapshot(self):
        command = self.make_command()

        command._import_roles([{"id": "3", "name": "'agente'"}])
        command._import_users(
            [
                {
                    "id": "4",
                    "name": "'Agente Padrão'",
                    "email": "'agente@abase.com'",
                    "password": "NULL",
                    "must_set_password": "0",
                    "profile_photo_path": "NULL",
                }
            ]
        )
        command._import_role_user([{"user_id": "4", "role_id": "3"}])
        command._import_agente_cadastros(
            [
                {
                    "id": "99",
                    "cpf_cnpj": "'123.456.789-00'",
                    "full_name": "'Associado Teste'",
                    "agente_responsavel": "'Agente Padrao'",
                    "agente_filial": "'agentepadrao'",
                }
            ]
        )

        associado = Associado.objects.get(cpf_cnpj="12345678900")
        agente = User.objects.get(email="agente@abase.com")
        self.assertEqual(associado.agente_responsavel_id, agente.pk)

    def test_import_agente_cadastros_keeps_multiple_contracts_for_same_cpf(self):
        command = self.make_command()

        command._import_agente_cadastros(
            [
                {
                    "id": "1",
                    "cpf_cnpj": "'713.394.773-00'",
                    "full_name": "'Associado Duplicado'",
                    "contrato_codigo_contrato": "'CTR-001'",
                },
                {
                    "id": "2",
                    "cpf_cnpj": "'71339477300'",
                    "full_name": "'Associado Duplicado'",
                    "contrato_codigo_contrato": "'CTR-002'",
                },
            ]
        )

        associado = Associado.objects.get(cpf_cnpj="71339477300")
        self.assertEqual(Associado.objects.count(), 1)
        self.assertEqual(
            list(
                Contrato.objects.filter(associado=associado)
                .order_by("codigo")
                .values_list("codigo", flat=True)
            ),
            ["CTR-001", "CTR-002"],
        )
