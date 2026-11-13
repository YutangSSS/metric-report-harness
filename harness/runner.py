"""Spec -> Runner -> Verifier -> Report.

A spec is a YAML file: the request in words, the parameters, and the tables. The runner builds each
table, the verifier re-checks it, and the report is written only alongside its check results.
"""
from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import yaml

from . import compare as cmp
from . import drift
from .db import data_quality, first_incomplete_month
from .metrics import describe
from .reports import BUILDERS, Context
from .table import Table, fmt
from .verifier import Check, verify

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Result:
    spec: dict[str, Any]
    tables: list[Table]
    checks: list[Check]
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


def load_spec(path: Path | str) -> dict[str, Any]:
    spec = yaml.safe_load(Path(path).read_text())
    for key in ("id", "title", "request", "tables"):
        if key not in spec:
            raise ValueError(f"{path}: spec is missing {key!r}")
    for ts in spec["tables"]:
        if ts.get("kind") not in BUILDERS:
            raise ValueError(f"{path}: unknown table kind {ts.get('kind')!r}")
    spec["_path"] = str(path)
    return spec


def run(spec: dict[str, Any], con: duckdb.DuckDBPyConnection, params: dict[str, Any] | None = None) -> Result:
    merged = {**spec.get("params", {}), **(params or {})}
    fim = first_incomplete_month(con)
    ctx = Context(con, fim, merged)
    tables = [BUILDERS[ts["kind"]](ctx, ts) for ts in spec["tables"]]
    checks = verify(tables, fim)
    result = Result(spec | {"params": merged}, tables, checks)
    result.extras["data_quality"] = data_quality(con)

    if "reviewer_csv" in spec:  # example 3: compare a reviewer's numbers to ours
        theirs = cmp.load_reviewer(ROOT / spec["reviewer_csv"])
        diffs = cmp.compare(tables[0], theirs)
        result.extras["reviewer_diffs"] = diffs
        result.extras["reply_draft"] = cmp.reply_draft(diffs)

    if spec.get("snapshot"):  # example 8: keep each run's list, and explain any change on a rerun
        snap = ROOT / "out" / "snapshots" / f"{spec['id']}_{merged['month']}.csv"
        rows = tables[0].detail or []
        if snap.exists():
            changes = drift.diff(drift.load_snapshot(snap), rows, None, con)
            result.extras["drift"] = changes
        drift.save_snapshot(rows, snap)
    return result


def render_markdown(r: Result, first_incomplete) -> str:
    s = r.spec
    out = [f"# {s['id']} · {s['title']}", "", f"**Request:** {s['request'].strip()}", ""]
    if s.get("params"):
        out += ["**Parameters:** " + ", ".join(f"`{k} = {v}`" for k, v in s["params"].items()), ""]
    last_full = (first_incomplete.replace(day=1) - timedelta(days=1))
    out += [f"**Data:** Austin Animal Center intakes and outcomes (public), complete through {last_full:%B %Y}.", ""]
    for t in r.tables:
        dec = 1
        out += [f"## {t.title}", "", "| | " + " | ".join(t.columns) + " |", "|---|" + "---:|" * len(t.columns)]
        for row in t.rows:
            cells = []
            for c in t.columns:
                v = t.get(row, c)
                is_pct = "%" in c or "%" in row
                cells.append(fmt(v, dec if is_pct else 0) + ("%" if is_pct and v is not None and not isinstance(v, str) else ""))
            out.append(f"| {row} | " + " | ".join(cells) + " |")
        out.append("")
        if t.detail is not None:
            out += [f"List view: {len(t.detail):,} records (see CSV).", ""]
        for n in t.notes:
            out.append(f"- {n}")
        out.append("")
    out += ["## Definitions", ""] + [f"- {d}" for d in describe(m for t in r.tables for m in t.metrics)] + [""]
    if "reviewer_diffs" in r.extras:
        out += ["## Reviewer comparison", "", "| Cell | Ours | Reviewer | Verdict |", "|---|---:|---:|---|"]
        for d in r.extras["reviewer_diffs"]:
            out.append(f"| {d.row} / {d.col} | {d.ours} | {d.theirs} | {d.verdict} |")
        out += ["", "**Draft reply (not sent):**", "", "```", r.extras["reply_draft"], "```", ""]
    if "drift" in r.extras:
        ch = r.extras["drift"]
        out += ["## Rerun drift", "", f"{len(ch)} record(s) changed since the last saved run of this list.", ""]
        out += [f"- {c.change} · {c.animal_id} · {c.reason}" for c in ch] + [""]
    dq = r.extras.get("data_quality", {})
    if dq:
        out += ["## Data quality handled by the models", ""] + [f"- {k}: {v:,}" for k, v in dq.items()] + [""]
    failed = [c for c in r.checks if not c.passed]
    out += [f"## Checks: {len(r.checks) - len(failed)} of {len(r.checks)} passed", ""]
    for c in failed:
        out.append(f"- FAIL · {c.table} · {c.name}: {c.detail}")
    if not failed:
        out.append("- All checks passed. The report can go to QA.")
    return "\n".join(out) + "\n"


def write(r: Result, out_dir: Path, first_incomplete) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / "report.md"
    md.write_text(render_markdown(r, first_incomplete))
    for i, t in enumerate(r.tables, 1):
        with (out_dir / f"table_{i}.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["row", *t.columns])
            for row in t.rows:
                w.writerow([row, *("" if t.get(row, c) is None else t.get(row, c) for c in t.columns)])
        if t.detail:
            with (out_dir / f"table_{i}_list.csv").open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(t.detail[0]))
                w.writeheader()
                w.writerows(t.detail)
    with (out_dir / "checks.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table", "check", "passed", "detail"])
        for c in r.checks:
            w.writerow([c.table, c.name, c.passed, c.detail])
    digest = hashlib.sha256(md.read_bytes()).hexdigest()[:12]
    (out_dir / "run.txt").write_text(
        f"spec={r.spec['_path']}\nparams={r.spec.get('params')}\nran_at={datetime.now():%Y-%m-%d %I:%M %p}\n"
        f"checks_passed={r.passed}\nreport_sha256_12={digest}\n"
    )
    return md
