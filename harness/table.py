"""A report table: displayed cells, plus the claims the verifier must re-check from those cells."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .periods import Period

Cell = Decimal | str | None


@dataclass
class Table:
    title: str
    columns: list[str]
    rows: list[str]
    cells: dict[tuple[str, str], Cell] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    # Claims are written by the builder and checked by the verifier against the displayed cells only.
    claims: list[tuple[Any, ...]] = field(default_factory=list)
    periods: list[Period] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    detail: list[dict[str, Any]] | None = None  # record-level list, when the request asks for one
    raw: dict[tuple[str, str], float] = field(default_factory=dict)  # unrounded values, when kept

    def set(self, row: str, col: str, value: Cell) -> None:
        if row not in self.rows or col not in self.columns:
            raise KeyError((row, col))
        self.cells[(row, col)] = value

    def get(self, row: str, col: str) -> Cell:
        return self.cells.get((row, col))

    def claim_sum(self, parts: list[tuple[str, str]], total: tuple[str, str]) -> None:
        self.claims.append(("sum", parts, total))

    def claim_pct(self, old: tuple[str, str], new: tuple[str, str], pct: tuple[str, str]) -> None:
        self.claims.append(("pct", old, new, pct))

    def claim_equal(self, name: str, a: Any, b: Any) -> None:
        self.claims.append(("equal", name, a, b))

    def claim_true(self, name: str, ok: bool, detail: str = "") -> None:
        self.claims.append(("true", name, ok, detail))


def fmt(value: Cell, decimals: int = 0) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    if decimals == 0:
        return f"{value:,.0f}"
    return f"{value:,.{decimals}f}"
