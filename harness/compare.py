"""Compare a QA reviewer's numbers with ours and say, cell by cell, why they differ.

Verdicts:
  match                 same number
  rounding (parts)      reviewer rounded each part on its own, so parts no longer add up; ours tie
  % from unrounded      reviewer's % change matches the unrounded numbers, ours uses the shown numbers
  % reversed            reviewer divided by the wrong year: (old - new) / new
  real difference       none of the above: the definitions or the data differ, look at it
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .rounding import round_half_up
from .table import Table


@dataclass
class CellDiff:
    row: str
    col: str
    ours: Decimal | None
    theirs: Decimal | None
    verdict: str


def load_reviewer(path: Path) -> dict[tuple[str, str], Decimal | None]:
    """CSV with a 'row' column and one column per table column, matching our labels."""
    out = {}
    with path.open() as f:
        for rec in csv.DictReader(f):
            row = rec.pop("row")
            for col, v in rec.items():
                out[(row, col)] = None if v in ("", "n/a") else Decimal(v)
    return out


def compare(t: Table, theirs: dict[tuple[str, str], Decimal | None]) -> list[CellDiff]:
    value_cols = [c for c in t.columns if c != "% change"]
    diffs = []
    for (row, col), their in theirs.items():
        ours = t.get(row, col)
        if ours == their:
            verdict = "match"
        elif col == "% change":
            old_s, new_s = t.get(row, value_cols[0]), t.get(row, value_cols[1])
            old_r, new_r = t.raw.get((row, value_cols[0])), t.raw.get((row, value_cols[1]))
            if old_r and their == round_half_up((Decimal(str(new_r)) - Decimal(str(old_r))) / Decimal(str(old_r)) * 100, 1):
                verdict = "% from unrounded"
            elif new_s and their == round_half_up((old_s - new_s) / new_s * 100, 1):
                verdict = "% reversed"
            else:
                verdict = "real difference"
        else:
            raw = t.raw.get((row, col))
            if raw is not None and their == round_half_up(raw) and abs(their - ours) <= 1:
                verdict = "rounding (parts)"
            else:
                verdict = "real difference"
        diffs.append(CellDiff(row, col, ours, their, verdict))
    return diffs


def reply_draft(diffs: list[CellDiff]) -> str:
    """A plain draft back to the reviewer. Every number in it comes from the table, not from a model."""
    issues = [d for d in diffs if d.verdict != "match"]
    if not issues:
        return "All cells match. No changes needed."
    lines = [f"Thanks for the review. {len(issues)} of {len(diffs)} cells differ; here is why:"]
    for d in issues:
        lines.append(f"- {d.row} / {d.col}: yours {d.theirs}, mine {d.ours}. {EXPLAIN[d.verdict]}")
    real = sum(d.verdict == "real difference" for d in issues)
    lines.append(
        f"{real} difference(s) need a closer look; the rest come from the rounding rules." if real
        else "All differences come from the rounding rules; the underlying counts agree."
    )
    return "\n".join(lines)


EXPLAIN = {
    "rounding (parts)": "You rounded this part on its own; I adjusted the parts so they add up to the rounded total.",
    "% from unrounded": "Your % uses the unrounded averages; mine uses the numbers shown in the table.",
    "% reversed": "Your % divides by the current year; it should divide by the previous year.",
    "real difference": "This is not a rounding effect. Let's compare definitions and filters.",
}
