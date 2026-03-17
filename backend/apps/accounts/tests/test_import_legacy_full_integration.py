from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TransactionTestCase


class ImportLegacyFullIntegrationTestCase(TransactionTestCase):
    reset_sequences = False

    def _resolve_dump_path(self) -> Path:
        candidates = [
            os.environ.get("ABASE_LEGACY_DUMP_FILE"),
            str(Path(__file__).resolve().parents[4] / "scriptsphp" / "abase (2).sql"),
            "/legacy-dumps/abase (2).sql",
            "/tmp/abase_legacy.sql",
        ]
        for candidate in candidates:
            if not candidate:
                continue
            path = Path(candidate)
            if path.exists():
                return path
        self.fail(f"Dump legado não encontrado. Candidatos verificados: {candidates}")

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
        self.assertEqual(
            report["summary"],
            {
                "roles": 8,
                "users_operacionais": 36,
                "agente_cadastros": 648,
                "associados": 647,
                "cpf_duplicado_consolidado": 1,
                "associado_users": 647,
                "contratos": 648,
                "ciclos": 648,
                "parcelas": 1944,
                "documentos": 4405,
                "agente_cadastro_assumptions": 111,
                "agente_doc_issues": 437,
                "agente_doc_reuploads": 616,
                "agente_margens": 11,
                "agente_margem_historicos": 11,
                "agente_margem_snapshots": 671,
                "despesas": 82,
                "pagamentos_mensalidades": 2081,
                "tesouraria_confirmacoes": 198,
                "tesouraria_pagamentos": 648,
                "refinanciamentos": 347,
                "refinanciamento_assumptions": 251,
                "refinanciamento_ajustes_valor": 0,
                "refinanciamento_comprovantes": 690,
                "refinanciamento_itens": 51,
                "refinanciamento_solicitacoes": 330,
                "competencia_conflicts": 0,
            },
        )
