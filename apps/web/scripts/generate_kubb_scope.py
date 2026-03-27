#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera artefatos Kubb por escopo sem sobrescrever domínios não relacionados."
    )
    parser.add_argument("--scope", required=True, help="Nome do escopo em src/gen/<scope>.")
    parser.add_argument(
        "--prefix",
        action="append",
        required=True,
        help="Prefixo de rota a manter no schema temporário. Pode ser repetido.",
    )
    parser.add_argument(
        "--source",
        default="../../backend/schema.yaml",
        help="Schema OpenAPI de origem.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    source = (root / args.source).resolve()
    if not source.exists():
        raise SystemExit(f"Schema não encontrado: {source}")

    with source.open("r", encoding="utf-8") as handle:
        schema = yaml.safe_load(handle)

    original_paths = schema.get("paths", {})
    filtered_paths = {
        path: payload
        for path, payload in original_paths.items()
        if any(path.startswith(prefix) for prefix in args.prefix)
    }
    if not filtered_paths:
        raise SystemExit(
            "Nenhuma rota correspondeu ao escopo informado. "
            f"Prefixes: {', '.join(args.prefix)}"
        )

    temp_dir = root / ".tmp" / "kubb"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_schema = temp_dir / f"{args.scope}.yaml"
    scoped_output = root / "src" / "gen" / args.scope

    scoped_schema = dict(schema)
    scoped_schema["paths"] = filtered_paths
    with temp_schema.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(scoped_schema, handle, sort_keys=False, allow_unicode=True)

    tracked_before = set()
    if shutil.which("git"):
        result = subprocess.run(
            ["git", "status", "--short", "--", "src/gen"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        tracked_before = {
            line.split(maxsplit=1)[-1].strip()
            for line in result.stdout.splitlines()
            if line.strip()
        }

    env = os.environ.copy()
    env["KUBB_INPUT_PATH"] = str(temp_schema)
    env["KUBB_OUTPUT_PATH"] = str(scoped_output)
    env["KUBB_CLEAN"] = "false"

    subprocess.run(
        ["pnpm", "exec", "kubb", "--config", "kubb.config.js"],
        cwd=root,
        env=env,
        check=True,
    )

    if shutil.which("git"):
        result = subprocess.run(
            ["git", "status", "--short", "--", "src/gen"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        tracked_after = {
            line.split(maxsplit=1)[-1].strip()
            for line in result.stdout.splitlines()
            if line.strip()
        }
        touched = tracked_after | tracked_before
        allowed_prefix = f"src/gen/{args.scope}/"
        unexpected = sorted(
            path
            for path in touched
            if path.startswith("src/gen/") and not path.startswith(allowed_prefix)
        )
        if unexpected:
            raise SystemExit(
                "Geração por escopo tocou arquivos fora do domínio permitido:\n"
                + "\n".join(unexpected)
            )

    print(
        "Kubb por escopo concluído.",
        f"scope={args.scope}",
        f"prefixes={','.join(args.prefix)}",
        sep=" ",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
