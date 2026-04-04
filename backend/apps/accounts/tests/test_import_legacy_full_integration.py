from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TransactionTestCase

from core.legacy_dump import default_legacy_dump_path


class ImportLegacyFullIntegrationTestCase(TransactionTestCase):
    reset_sequences = False

    def _resolve_dump_path(self) -> Path:
        repo_root = Path(__file__).resolve().parents[4]
        candidates = [
            os.environ.get("ABASE_LEGACY_DUMP_FILE"),
            str(default_legacy_dump_path()),
            str(repo_root / "dumps_legado" / "abase_dump_legado_21.03.2026.sql"),
            str(repo_root / "scriptsphp" / "abase (2).sql"),
            "/legacy-dumps/abase (2).sql",
            "/tmp/abase_legacy.sql",
        ]
        for candidate in candidates:
            if not candidate:
                continue
            path = Path(candidate)
            if path.exists():
                return path
        self.skipTest(
            f"Dump legado não encontrado neste ambiente. Candidatos verificados: {candidates}"
        )

    def test_import_legacy_full_dry_run_com_dump_real_fecha_no_baseline(self):
        dump_path = self._resolve_dump_path()

        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "legacy_report.json"

            call_command(
                "import_legacy_full",
                file=str(dump_path),
                dry_run=True,
                report_file=str(report_path),
            )

            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "100% concluído")
        self.assertEqual(report["summary"]["roles"], report["sections"]["roles"]["source_rows"])
        self.assertEqual(
            report["summary"]["users_operacionais"],
            report["sections"]["users_operacionais"]["source_rows"],
        )
        self.assertEqual(
            report["summary"]["associados"],
            report["sections"]["associados"]["actual_rows"],
        )
        self.assertEqual(
            report["summary"]["contratos"],
            report["sections"]["contratos"]["actual_rows"],
        )
        self.assertEqual(
            report["summary"]["pagamentos_mensalidades"],
            report["sections"]["pagamentos_mensalidades"]["source_rows"],
        )
        self.assertEqual(report["summary"]["competencia_conflicts"], 0)
        self.assertTrue(str(dump_path).endswith(report["source_file"].split("/")[-1]))
