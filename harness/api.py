"""Read-only HTTP API over the harness.

GET  /health                      data cut and model build status
GET  /specs                       the example requests this service can run
POST /reports/{spec_id}           run one spec (optional parameter overrides); returns tables and checks
POST /ask                         request email -> questions, or a verified report plus a reply draft

Nothing here writes to the data or sends anything anywhere. Numbers come only from the harness.
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .db import connect, data_quality, first_incomplete_month
from .runner import ROOT, Result, load_spec, run

app = FastAPI(title="metric-report-harness", version="0.2.0")
_con = connect()
_SPECS = {p.stem.split("_", 1)[0]: p for p in sorted((ROOT / "specs").glob("*.yaml"))}


def _cell(v):
    return float(v) if isinstance(v, Decimal) else v


def _result_json(r: Result) -> dict[str, Any]:
    return {
        "passed": r.passed,
        "params": r.spec.get("params", {}),
        "tables": [
            {"title": t.title, "columns": t.columns,
             "rows": [{"row": row, **{c: _cell(t.get(row, c)) for c in t.columns}} for row in t.rows],
             "notes": t.notes, "list_rows": len(t.detail) if t.detail is not None else None}
            for t in r.tables
        ],
        "checks": {"passed": sum(c.passed for c in r.checks), "total": len(r.checks),
                   "failed": [{"table": c.table, "check": c.name, "detail": c.detail} for c in r.checks if not c.passed]},
        "data_quality": r.extras.get("data_quality"),
    }


@app.get("/health")
def health():
    cur = _con.cursor()
    return {"status": "ok", "first_incomplete_month": first_incomplete_month(cur).isoformat(), "data_quality": data_quality(cur)}


@app.get("/specs")
def specs():
    out = []
    for sid, path in _SPECS.items():
        s = load_spec(path)
        out.append({"id": sid, "title": s["title"], "params": s.get("params", {})})
    return out


class RunBody(BaseModel):
    params: dict[str, str] = {}


@app.post("/reports/{spec_id}")
def report(spec_id: str, body: RunBody | None = None):
    if spec_id not in _SPECS:
        raise HTTPException(404, f"unknown spec {spec_id}")
    spec = load_spec(_SPECS[spec_id])
    spec.pop("snapshot", None)  # the API never writes snapshots
    try:
        r = run(spec, _con.cursor(), (body.params if body else {}))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return _result_json(r)


class AskBody(BaseModel):
    email: str
    email_date: date


@app.post("/ask")
def ask(body: AskBody):
    from .agent import handle
    from .agent.backends import get_backend

    backend_name = os.environ.get("HARNESS_BACKEND")
    if not backend_name:
        raise HTTPException(503, "no model backend configured (set HARNESS_BACKEND=api or cli)")
    ans = handle(get_backend(backend_name), _con.cursor(), body.email, body.email_date)
    if ans.spec is None:
        return {"status": "needs_clarification", "questions": ans.questions, "card": ans.card}
    return {"status": "answered", "card": ans.card, "report": _result_json(ans.result),
            "reply_draft": ans.reply, "reply_source": ans.reply_source}
