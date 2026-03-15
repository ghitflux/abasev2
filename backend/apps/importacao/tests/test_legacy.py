from __future__ import annotations

import tempfile
from datetime import date, datetime
from pathlib import Path
from decimal import Decimal

from django.test import SimpleTestCase

from apps.importacao.legacy import list_legacy_pagamento_snapshots_from_dump


class LegacyPagamentoSnapshotDumpTestCase(SimpleTestCase):
    def test_parser_ler_snapshots_manuais_do_dump(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dump_path = Path(temp_dir) / "legacy.sql"
            dump_path.write_text(
                """
                INSERT INTO `pagamentos_mensalidades`
                (`id`, `referencia_month`, `cpf_cnpj`, `esperado_manual`, `recebido_manual`,
                 `manual_status`, `agente_refi_solicitado`, `manual_paid_at`,
                 `manual_forma_pagamento`, `manual_comprovante_path`, `created_at`, `updated_at`)
                VALUES
                (1, '2026-01-01', '12345678900', 400.00, 400.00, 'pago', 0,
                 '2026-01-15 00:00:00', 'pix', 'comprovantes/1.jpg',
                 '2026-01-10 08:00:00', '2026-01-15 09:00:00'),
                (2, '2026-01-01', '12345678900', 400.00, 420.00, 'pago', 1,
                 '2026-01-20 00:00:00', 'manual', 'comprovantes/2.jpg',
                 '2026-01-10 08:00:00', '2026-01-20 10:00:00'),
                (3, '2026-01-01', '99999999999', NULL, NULL, NULL, 0,
                 NULL, NULL, NULL, '2026-01-10 08:00:00', '2026-01-10 08:00:00');
                """,
                encoding="utf-8",
            )

            snapshots = list_legacy_pagamento_snapshots_from_dump(
                dump_path=dump_path,
                competencia=date(2026, 1, 1),
            )

        self.assertEqual(len(snapshots), 1)
        snapshot = snapshots[("12345678900", date(2026, 1, 1))]
        self.assertEqual(snapshot.manual_status, "pago")
        self.assertEqual(snapshot.recebido_manual, Decimal("420.00"))
        self.assertTrue(snapshot.agente_refi_solicitado)
        self.assertEqual(snapshot.manual_forma_pagamento, "manual")
        self.assertEqual(snapshot.manual_comprovante_path, "comprovantes/2.jpg")
        self.assertEqual(snapshot.manual_paid_at, datetime(2026, 1, 20, 0, 0))
