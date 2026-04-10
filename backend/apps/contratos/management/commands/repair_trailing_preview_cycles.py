from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.contratos.trailing_preview_cycle_repair import repair_trailing_preview_cycles


class Command(BaseCommand):
    help = (
        "Corrige contratos com ciclo final indevido contendo apenas competências em previsão "
        "de abril/2026, recolocando abril no ciclo anterior e restaurando a fila operacional."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Executa a correção no banco. Sem esta flag roda em dry-run.",
        )
        parser.add_argument(
            "--report-json",
            default="",
            help="Caminho opcional para salvar o relatório em JSON.",
        )

    def handle(self, *args, **options):
        payload = repair_trailing_preview_cycles(apply=bool(options["apply"]))
        report_json = str(options.get("report_json") or "").strip()
        if report_json:
            path = Path(report_json)
        else:
            suffix = "apply" if options["apply"] else "dry_run"
            path = (
                Path(settings.BASE_DIR)
                / "media"
                / "relatorios"
                / f"repair_trailing_preview_cycles_{suffix}.json"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(json.dumps(payload, ensure_ascii=False)))
        self.stdout.write(f"Relatório salvo em {path}")
