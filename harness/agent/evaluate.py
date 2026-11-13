"""Agent eval: run every case in evals/agent_cases.yaml through a backend and score it.

A normal case passes only if the agent's spec reproduces the golden spec's numbers exactly.
An ambiguous case passes only if the agent asks instead of running.
Replies are scored separately: every number grounded, every reviewer difference mentioned.
"""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ..runner import ROOT, Result, load_spec, run
from . import handle

CASES = ROOT / "evals" / "agent_cases.yaml"


def table_signature(r: Result) -> list[tuple]:
    sig = []
    for t in r.tables:
        cells = tuple(sorted((k, str(v)) for k, v in t.cells.items()))
        sig.append((t.metrics[0] if t.metrics else "", cells, len(t.detail or [])))
    return sorted(sig)


def load_cases() -> list[dict[str, Any]]:
    return yaml.safe_load(CASES.read_text())


def run_case(backend, con, case: dict[str, Any]) -> dict[str, Any]:
    t0 = time.time()
    att = str(ROOT / case["attachment"]) if case.get("attachment") else None
    email_date = case["date"] if isinstance(case["date"], date) else date.fromisoformat(str(case["date"]))
    out: dict[str, Any] = {"id": case["id"]}
    try:
        ans = handle(backend, con, case["email"], email_date, att, reply=True)
    except Exception as e:  # a model or parse failure is a failed case, not a crashed eval
        return out | {"passed": False, "why": f"error: {e}", "seconds": round(time.time() - t0, 1)}
    out["card_type"] = ans.card.get("request_type")
    if case.get("expect") == "questions":
        out["passed"] = ans.spec is None and bool(ans.questions)
        out["why"] = "asked: " + " | ".join(ans.questions) if out["passed"] else "ran without asking"
    elif ans.spec is None:
        out["passed"], out["why"] = False, "asked instead of running: " + " | ".join(ans.questions)
    else:
        golden = run(load_spec(ROOT / "specs" / case["golden"]), con)
        same = table_signature(golden) == table_signature(ans.result)
        out["passed"] = same and ans.result.passed
        out["why"] = "numbers identical to golden spec" if same else "numbers differ from golden spec"
        if ans.grounding is not None:
            out["reply_grounded"] = ans.grounding.passed
            out["reply_source"] = ans.reply_source
            if not ans.grounding.passed:
                out["reply_problem"] = f"invented {ans.grounding.invented}, missing {ans.grounding.missing}"
    out["seconds"] = round(time.time() - t0, 1)
    return out


def main(argv=None) -> int:
    import argparse
    from ..db import connect
    from .backends import get_backend

    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="cli")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args(argv)
    backend, con = get_backend(args.backend), connect()
    rows = []
    for case in load_cases():
        if args.only and case["id"] not in args.only:
            continue
        r = run_case(backend, con, case)
        rows.append(r)
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['id']}  {r.get('card_type', ''):<16} {r['seconds']:>5}s  {r['why'][:110]}"
              + (f"  reply={'grounded' if r.get('reply_grounded') else 'REJECTED'}" if 'reply_grounded' in r else ""), flush=True)
    n = sum(r["passed"] for r in rows)
    replies = [r for r in rows if "reply_grounded" in r]
    print(f"\ncases passed {n}/{len(rows)}; replies grounded {sum(r['reply_grounded'] for r in replies)}/{len(replies)}")
    out = ROOT / "evals" / "results"
    out.mkdir(exist_ok=True)
    (out / f"{backend.name}_{time.strftime('%Y%m%d_%H%M')}.yaml").write_text(yaml.safe_dump(rows, sort_keys=False))
    return 0 if n == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
