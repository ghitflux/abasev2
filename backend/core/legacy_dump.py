from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.utils import timezone


def default_legacy_dump_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        os.environ.get("ABASE_LEGACY_DUMP_FILE"),
        repo_root / "dumps_legado" / "abase_dump_legado_21.03.2026.sql",
        repo_root / "scriptsphp" / "abase (2).sql",
        "dumps_legado/abase_dump_legado_21.03.2026.sql",
        "scriptsphp/abase (2).sql",
        "/legacy-dumps/abase (2).sql",
        "/tmp/abase_legacy.sql",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.exists():
            return path
    return Path("dumps_legado/abase_dump_legado_21.03.2026.sql")


def parse_timestamp(value: str | None) -> datetime | None:
    if not value or value == "NULL":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value.strip("'"), fmt)
            return timezone.make_aware(parsed)
        except ValueError:
            continue
    return None


def parse_date(value: str | None) -> date | None:
    if not value or value == "NULL":
        return None
    try:
        return datetime.strptime(value.strip("'"), "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_decimal(value: str | None) -> Decimal | None:
    if not value or value == "NULL":
        return None
    try:
        return Decimal(value.strip("'"))
    except InvalidOperation:
        return None


def parse_int(value: str | None) -> int | None:
    if not value or value == "NULL":
        return None
    try:
        return int(value.strip("'"))
    except ValueError:
        return None


def parse_str(value: str | None) -> str:
    if not value or value == "NULL":
        return ""
    return value.strip("'").replace("\\'", "'").replace("\\\\", "\\")


def parse_str_or_none(value: str | None) -> str | None:
    if not value or value == "NULL":
        return None
    return value.strip("'").replace("\\'", "'").replace("\\\\", "\\")


def parse_bool(value: str | None) -> bool:
    if not value or value == "NULL":
        return False
    return value.strip("'") in ("1", "true", "True")


def parse_json(value: str | None) -> Any:
    if not value or value == "NULL":
        return None

    raw = value.strip("'")
    candidates = [
        raw,
        raw.replace("\\'", "'").replace("\\\\", "\\"),
        raw.replace("\\'", "'")
        .replace('\\"', '"')
        .replace("\\/", "/")
        .replace("\\\\", "\\"),
    ]

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue

    try:
        return json.loads(bytes(raw, "utf-8").decode("unicode_escape"))
    except Exception:
        return None


def split_row_tuples(values_str: str) -> list[str]:
    rows: list[str] = []
    current = ""
    depth = 0
    in_quote = False
    previous = ""

    for char in values_str:
        if char == "'" and previous != "\\":
            in_quote = not in_quote

        if not in_quote and char == "(":
            depth += 1
            if depth == 1:
                previous = char
                continue

        if not in_quote and char == ")":
            depth -= 1
            if depth == 0:
                rows.append(current)
                current = ""
                previous = char
                continue

        if depth >= 1:
            current += char

        previous = char

    return rows


def split_values(values_str: str) -> list[str]:
    result: list[str] = []
    current = ""
    in_quote = False

    for index, char in enumerate(values_str):
        if char == "'" and not in_quote:
            in_quote = True
            current += char
            continue
        if char == "'" and in_quote:
            if index > 0 and values_str[index - 1] == "\\":
                current += char
            else:
                in_quote = False
                current += char
            continue
        if char == "," and not in_quote:
            result.append(current.strip())
            current = ""
            continue
        current += char

    if current.strip():
        result.append(current.strip())
    return result


def extract_table_data(sql_text: str, table_name: str) -> list[dict[str, str]]:
    pattern = re.compile(
        r"INSERT INTO `" + re.escape(table_name) + r"`\s*"
        r"\(([^)]+)\)\s*VALUES\s*([\s\S]+?);",
        re.IGNORECASE,
    )
    rows: list[dict[str, str]] = []
    for match in pattern.finditer(sql_text):
        columns = [column.strip().strip("`") for column in match.group(1).split(",")]
        for row_raw in split_row_tuples(match.group(2)):
            raw_values = split_values(row_raw)
            if len(raw_values) == len(columns):
                rows.append(dict(zip(columns, raw_values)))
    return rows


class LegacyDump:
    def __init__(self, sql_text: str):
        self.sql_text = sql_text
        self._cache: dict[str, list[dict[str, str]]] = {}

    @classmethod
    def from_file(cls, file_path: str | Path) -> "LegacyDump":
        path = Path(file_path).expanduser()
        sql_text = path.read_text(encoding="utf-8", errors="replace")
        return cls(sql_text)

    def table_rows(self, table_name: str) -> list[dict[str, str]]:
        if table_name not in self._cache:
            self._cache[table_name] = extract_table_data(self.sql_text, table_name)
        return self._cache[table_name]
