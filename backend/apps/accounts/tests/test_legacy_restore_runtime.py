from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings

from apps.accounts.legacy_restore_runtime import (
    RETURN_MONTHS,
    capture_preserved_auth_snapshot,
    select_restore_uploaded_by,
    stage_return_files,
    validate_preserved_auth_snapshot,
)
from apps.accounts.models import Role, User
from apps.importacao.models import ArquivoRetorno


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class LegacyRestoreRuntimeTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_role = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.coord_role = Role.objects.create(codigo="COORDENADOR", nome="Coordenador")

    def test_select_restore_uploaded_by_prefers_admin_local(self):
        coord = User.objects.create_user(
            email="coord@abase.local",
            password="Senha@123",
            first_name="Coord",
            last_name="ABASE",
            is_active=True,
        )
        coord.roles.add(self.coord_role)

        admin = User.objects.create_user(
            email="admin@abase.local",
            password="Senha@123",
            first_name="Admin",
            last_name="ABASE",
            is_active=True,
        )
        admin.roles.add(self.admin_role)

        self.assertEqual(select_restore_uploaded_by().pk, admin.pk)

    def test_stage_return_files_copies_manifest_and_payload(self):
        admin = User.objects.create_user(
            email="admin@abase.local",
            password="Senha@123",
            first_name="Admin",
            last_name="ABASE",
            is_active=True,
        )
        admin.roles.add(self.admin_role)

        for competencia in RETURN_MONTHS:
            storage_name = default_storage.save(
                f"arquivos_retorno/{competencia.isoformat()}.txt",
                ContentFile(
                    f"retorno-{competencia.isoformat()}".encode("utf-8"),
                    name=f"{competencia.isoformat()}.txt",
                ),
            )
            ArquivoRetorno.objects.create(
                arquivo_nome=f"retorno_{competencia.isoformat()}.txt",
                arquivo_url=storage_name,
                formato=ArquivoRetorno.Formato.TXT,
                orgao_origem="ETIPI",
                competencia=competencia,
                uploaded_by=admin,
                status=ArquivoRetorno.Status.CONCLUIDO,
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            payload = stage_return_files(temp_dir)

            self.assertEqual(len(payload["files"]), len(RETURN_MONTHS))
            manifest_path = Path(payload["manifest_path"])
            self.assertTrue(manifest_path.exists())

            first_file = payload["files"][0]
            staged_path = Path(temp_dir) / first_file["staged_path"]
            self.assertTrue(staged_path.exists())
            self.assertEqual(
                staged_path.read_bytes(),
                b"retorno-2025-10-01",
            )

    def test_validate_preserved_auth_snapshot_allows_extra_associado_users(self):
        admin = User.objects.create_user(
            email="admin@abase.local",
            password="Senha@123",
            first_name="Admin",
            last_name="ABASE",
            is_active=True,
        )
        admin.roles.add(self.admin_role)

        snapshot = capture_preserved_auth_snapshot()

        associado_role = Role.objects.create(codigo="ASSOCIADO", nome="Associado")
        associado_user = User.objects.create_user(
            email="12345678900@app.abase.local",
            password="12345678900",
            first_name="Associado",
            last_name="Teste",
            is_active=True,
        )
        associado_user.roles.add(associado_role)

        validation = validate_preserved_auth_snapshot(snapshot)

        self.assertTrue(validation["ok"])
        self.assertEqual(validation["count_delta"]["accounts_user"], 1)
        self.assertEqual(validation["count_delta"]["accounts_userrole"], 1)

    def test_validate_preserved_auth_snapshot_flags_existing_password_change(self):
        admin = User.objects.create_user(
            email="admin@abase.local",
            password="Senha@123",
            first_name="Admin",
            last_name="ABASE",
            is_active=True,
        )
        admin.roles.add(self.admin_role)
        snapshot = capture_preserved_auth_snapshot()

        admin.set_password("NovaSenha@123")
        admin.save(update_fields=["password"])

        validation = validate_preserved_auth_snapshot(snapshot)

        self.assertFalse(validation["ok"])
        self.assertTrue(
            any("teve o hash alterado" in message for message in validation["errors"])
        )
