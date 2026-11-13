"""The gate. Re-checks every claim from the displayed cells, so a report cannot pass on the builder's word.

A report ships only if every check passes. Checks never change a number; they only pass or fail.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .rounding import pct_change
from .table import Table


@dataclass
class Check:
    table: str
    name: str
    passed: bool
    detail: str = ""


def _num(cell) -> Decimal | None:
    return cell if isinstance(cell, Decimal) else None


def verify_table(t: Table, first_incomplete_month: date) -> list[Check]:
    out: list[Check] = []
    for claim in t.claims:
        kind = claim[0]
        if kind == "sum":
            _, parts, total = claim
            vals = [_num(t.get(*p)) for p in parts]
            tot = _num(t.get(*total))
            ok = tot is not None and all(v is not None for v in vals) and sum(vals) == tot
            out.append(Check(t.title, f"adds up: {total[0]} / {total[1]}", ok,
                             "" if ok else f"parts {[str(v) for v in vals]} sum to {sum(v or 0 for v in vals)}, shown {tot}"))
        elif kind == "pct":
            _, old, new, pct = claim
            expected = pct_change(_num(t.get(*old)), _num(t.get(*new)))
            shown = t.get(*pct)
            ok = shown == expected
            out.append(Check(t.title, f"% change from shown numbers: {pct[0]} / {pct[1]}", ok,
                             "" if ok else f"shown {shown}, recomputed {expected}"))
        elif kind == "equal":
            _, name, a, b = claim
            out.append(Check(t.title, name, a == b, "" if a == b else f"{a} != {b}"))
        elif kind == "true":
            _, name, ok, detail = claim
            out.append(Check(t.title, name, bool(ok), "" if ok else detail))
        else:
            raise ValueError(f"unknown claim {kind!r}")

    for p in t.periods:
        complete = p.is_complete(first_incomplete_month)
        ok = complete or p.kind == "ytd"
        out.append(Check(t.title, f"period complete or labelled YTD: {p.label}", ok,
                         "" if ok else f"{p.label} runs past the last complete month ({first_incomplete_month:%b %Y} is incomplete)"))

    for (row, col), cell in t.cells.items():
        if isinstance(cell, Decimal) and cell < 0 and "change" not in (row + col).lower():
            out.append(Check(t.title, f"no negative counts: {row} / {col}", False, str(cell)))
    return out


def verify(tables: list[Table], first_incomplete_month: date) -> list[Check]:
    return [c for t in tables for c in verify_table(t, first_incomplete_month)]
