from __future__ import annotations

from datetime import date


NOVEMBER_2025_REFERENCE = date(2025, 11, 1)

# Novembro/2025 deixou de ser tratado como competência obrigatoriamente fora do ciclo.
# A constante permanece para rotinas históricas de auditoria/reparo.
FORCED_OUTSIDE_CYCLE_REFERENCES = frozenset()


def month_floor(value: date | None) -> date | None:
    if value is None:
        return None
    return value.replace(day=1)


def is_forced_outside_cycle_reference(value: date | None) -> bool:
    reference = month_floor(value)
    return reference in FORCED_OUTSIDE_CYCLE_REFERENCES
