"""Rounding rules that a QA reviewer will check.

1. Round half up (2.5 -> 3), like Excel. Python's round() rounds half to even (2.5 -> 2).
2. Displayed parts must add up to the displayed subtotal and total. Each total is rounded
   honestly, then the parts are adjusted by the largest-remainder method so they add up.
3. Percent change is computed from the displayed (rounded) numbers, so a reader with a
   calculator gets the same answer from the table.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Mapping, Sequence


def round_half_up(x: float | Decimal, decimals: int = 0) -> Decimal:
    q = Decimal(1).scaleb(-decimals)
    return Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP)


def allocate(raw: Mapping[str, float], target: Decimal, decimals: int = 0) -> dict[str, Decimal]:
    """Round each value so the rounded values sum exactly to target (largest remainder).

    Ties on remainder go to the larger raw value, then to key order, so the result is deterministic.
    """
    unit = Decimal(1).scaleb(-decimals)
    floors = {k: (Decimal(str(v)) / unit).to_integral_value(rounding="ROUND_FLOOR") for k, v in raw.items()}
    remainders = {k: Decimal(str(v)) / unit - floors[k] for k, v in raw.items()}
    short = int(target / unit) - int(sum(floors.values()))
    if short < 0 or short > len(raw):
        raise ValueError(f"cannot allocate {target} across {dict(raw)}")
    order = sorted(raw, key=lambda k: (-remainders[k], -raw[k], list(raw).index(k)))
    bump = set(order[:short])
    return {k: (floors[k] + (1 if k in bump else 0)) * unit for k in raw}


def round_hierarchy(
    leaves: Mapping[str, float],
    groups: Mapping[str, Sequence[str]] | None = None,
    decimals: int = 0,
) -> dict[str, Decimal]:
    """Round leaves, subtotals (groups) and the overall 'Total' so every sum ties on screen.

    groups maps a subtotal name to the leaves it contains; leaves outside any group sit at top level.
    """
    groups = dict(groups or {})
    grouped = {leaf for members in groups.values() for leaf in members}
    top_raw: dict[str, float] = {g: sum(leaves[m] for m in ms) for g, ms in groups.items()}
    top_raw.update({k: v for k, v in leaves.items() if k not in grouped})
    total = round_half_up(sum(leaves.values()), decimals)
    out = allocate(top_raw, total, decimals)
    for g, members in groups.items():
        out.update(allocate({m: leaves[m] for m in members}, out[g], decimals))
    out["Total"] = total
    return out


def pct_change(old: Decimal | float | None, new: Decimal | float | None, decimals: int = 1) -> Decimal | None:
    """(new - old) / old, from displayed numbers. None when old is 0 or missing (shown as n/a)."""
    if old is None or new is None or Decimal(str(old)) == 0:
        return None
    old_d, new_d = Decimal(str(old)), Decimal(str(new))
    return round_half_up((new_d - old_d) / old_d * 100, decimals)
