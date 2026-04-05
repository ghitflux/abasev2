from __future__ import annotations


MANUAL_PAYMENT_KIND_MARISTELA_IN_CYCLE = "conciliacao_maristela_em_ciclo"
MANUAL_PAYMENT_KIND_MARISTELA_OUTSIDE_CYCLE = "conciliacao_maristela_fora_ciclo"


def normalize_manual_payment_kind(value: str | None) -> str:
    return (value or "").strip().casefold()


def is_manual_payment_in_cycle(value: str | None) -> bool:
    return normalize_manual_payment_kind(value) == MANUAL_PAYMENT_KIND_MARISTELA_IN_CYCLE


def is_manual_payment_outside_cycle(value: str | None) -> bool:
    return (
        normalize_manual_payment_kind(value)
        == MANUAL_PAYMENT_KIND_MARISTELA_OUTSIDE_CYCLE
    )
