"""Rerun drift: the same monthly list, rerun on a later day, returns a different set of records.

Instead of "the numbers changed, not sure why", the diff names every record that came or went
and the source field that changed for it.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

FIELDS = ["intake_dt", "outcome_dt", "outcome_type", "intake_type", "animal_type", "region_type"]


@dataclass
class Change:
    animal_id: str
    stay_id: int
    change: str  # added | removed
    reason: str


def save_snapshot(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0]) if rows else ["animal_id", "stay_id"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def load_snapshot(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        return list(csv.DictReader(f))


def _stay(con: duckdb.DuckDBPyConnection, stay_id: int) -> dict[str, Any] | None:
    cols = ", ".join(FIELDS)
    row = con.execute(f"select {cols} from fct_stays where stay_id = ?", [stay_id]).fetchone()
    return dict(zip(FIELDS, row)) if row else None


def diff(
    old_rows: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
    old_con: duckdb.DuckDBPyConnection | None,
    new_con: duckdb.DuckDBPyConnection,
) -> list[Change]:
    """Compare two runs of a list. old_con is the database the first run used, when still available."""
    old = {(r["animal_id"], int(r["stay_id"])): r for r in old_rows}
    new = {(r["animal_id"], int(r["stay_id"])): r for r in new_rows}
    changes: list[Change] = []
    for key in sorted(old.keys() ^ new.keys()):
        animal_id, stay_id = key
        kind = "removed" if key in old else "added"
        now = _stay(new_con, stay_id)
        before = _stay(old_con, stay_id) if old_con is not None else None
        if now is None:
            reason = "record no longer exists in the source"
        elif before is None and old_con is not None:
            reason = "record is new in the source (entered after the first run)"
        elif before is not None:
            changed = [f"{f}: {before[f]} -> {now[f]}" for f in FIELDS if before[f] != now[f]]
            reason = "; ".join(changed) if changed else "no field changed: check the list rule itself"
        else:
            reason = f"first run's data is not available; current values: outcome {now['outcome_type']} on {now['outcome_dt']}"
        changes.append(Change(animal_id, stay_id, kind, reason))
    return changes
