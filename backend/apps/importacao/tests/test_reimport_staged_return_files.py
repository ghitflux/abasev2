from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import override_settings

from apps.accounts.models import Role, User

from .base import ImportacaoBaseTestCase
from ..models import ArquivoRetorno


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class ReimportStagedReturnFilesCommandTestCase(ImportacaoBaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Garante a preferência explícita usada pelo comando em produção.
        if not Role.objects.filter(codigo="ADMIN").exists():
            Role.objects.create(codigo="ADMIN", nome="Administrador")
        if not User.objects.filter(email="admin@abase.local").exists():
            admin = User.objects.create_user(
                email="admin@abase.local",
                password="Senha@123",
                first_name="Admin",
                last_name="ABASE",
                is_active=True,
            )
            admin.roles.add(Role.objects.get(codigo="ADMIN"))

    def test_command_reimports_manifest_in_order(self):
        fixture_path = self.fixture_path("retorno_etipi_052025.txt")

        with tempfile.TemporaryDirectory() as temp_dir:
            staged_file = Path(temp_dir) / "2025-05-01__fixture__retorno_etipi_052025.txt"
            staged_file.write_bytes(fixture_path.read_bytes())
            manifest_path = Path(temp_dir) / "return_files_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "stage_dir": temp_dir,
                        "files": [
                            {
                                "competencia": "2025-05-01",
                                "source_id": 999,
                                "source_name": fixture_path.name,
                                "source_storage_path": "arquivos_retorno/original.txt",
                                "staged_path": staged_file.name,
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            call_command(
                "reimport_staged_return_files",
                "--staging-dir",
                temp_dir,
                "--execute",
            )

        arquivo = ArquivoRetorno.objects.get()
        self.assertEqual(arquivo.competencia.isoformat(), "2025-05-01")
        self.assertEqual(arquivo.status, ArquivoRetorno.Status.CONCLUIDO)
        self.assertEqual(arquivo.uploaded_by.email, "admin@abase.local")
