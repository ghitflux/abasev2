from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.legacy_media_assets import ALL_FAMILIES, LegacyMediaAssetsService


def _default_report_path(prefix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return (
        Path(settings.BASE_DIR)
        / "media"
        / "relatorios"
        / "legacy_import"
        / f"{prefix}_{timestamp}.json"
    )


class Command(BaseCommand):
    help = "Audita o estado dos anexos legados frente ao storage oficial."

    def add_arguments(self, parser):
        parser.add_argument(
            "--legacy-root",
            default="anexos_legado",
            help="Diretório raiz do acervo legado.",
        )
        parser.add_argument(
            "--families",
            default=",".join(ALL_FAMILIES),
            help="Famílias separadas por vírgula: cadastro,renovacao,tesouraria,manual,esteira",
        )
        parser.add_argument("--cpf", help="Filtra um associado específico por CPF.")
        parser.add_argument("--report-json", help="Caminho opcional do relatório JSON.")

    def handle(self, *args, **options):
        legacy_root = Path(options["legacy_root"]).expanduser()
        if not legacy_root.exists():
            raise CommandError(f"Acervo legado não encontrado: {legacy_root}")

        families = [
            family.strip().lower()
            for family in str(options["families"] or "").split(",")
            if family.strip()
        ]
        invalid = [family for family in families if family not in ALL_FAMILIES]
        if invalid:
            raise CommandError(f"Famílias inválidas: {', '.join(invalid)}")

        service = LegacyMediaAssetsService(legacy_root=legacy_root)
        payload = service.run(
            families=families,
            cpf=options.get("cpf"),
            execute=False,
        )
        result = {
            "generated_at": datetime.now().isoformat(),
            "legacy_root": str(legacy_root.resolve()),
            "mode": "audit",
            **payload,
        }
        target = (
            Path(options["report_json"])
            if options.get("report_json")
            else _default_report_path("audit_legacy_media_assets")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        summary = result["summary"]
        self.stdout.write(
            self.style.SUCCESS(
                "Auditoria concluída: "
                f"{summary['records']} registro(s), "
                f"{summary['already_canonical']} já canônico(s), "
                f"{summary['reference_only']} pendência(s) de acervo."
            )
        )
        self.stdout.write(f"Relatório: {target}")
