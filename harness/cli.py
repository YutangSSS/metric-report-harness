"""harness run specs/01_quarterly_placemat.yaml --set quarter="2017-18 Q3"
harness run-all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .db import connect, first_incomplete_month
from .runner import ROOT, load_spec, run, write


def _params(pairs: list[str]) -> dict[str, str]:
    out = {}
    for p in pairs:
        k, _, v = p.partition("=")
        if not v:
            raise SystemExit(f"--set expects key=value, got {p!r}")
        out[k.strip()] = v.strip()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run one spec")
    r.add_argument("spec")
    r.add_argument("--set", action="append", default=[], help="override a parameter, e.g. quarter='2017-18 Q2'")
    r.add_argument("--out", default=None)
    sub.add_parser("run-all", help="run every spec in specs/")
    a = sub.add_parser("ask", help="answer a request email (model reads it, harness computes)")
    a.add_argument("email_file")
    a.add_argument("--date", required=True, help="date the email was sent, YYYY-MM-DD")
    a.add_argument("--attach", default=None)
    a.add_argument("--backend", default="cli", help="cli (local claude login) or api (ANTHROPIC_API_KEY)")
    args = ap.parse_args(argv)
    if args.cmd == "ask":
        return _ask(args)

    con = connect()
    fim = first_incomplete_month(con)
    paths = [Path(args.spec)] if args.cmd == "run" else sorted((ROOT / "specs").glob("*.yaml"))
    failed = 0
    for path in paths:
        spec = load_spec(path)
        result = run(spec, con, _params(getattr(args, "set", [])))
        out_dir = Path(getattr(args, "out", None) or ROOT / "out" / path.stem)
        md = write(result, out_dir, fim)
        n_ok = sum(c.passed for c in result.checks)
        status = "PASS" if result.passed else "FAIL"
        print(f"{status}  {spec['id']}  {spec['title']:<48} checks {n_ok}/{len(result.checks)}  -> {md.relative_to(ROOT) if md.is_relative_to(ROOT) else md}")
        failed += not result.passed
    return 1 if failed else 0


def _ask(args) -> int:
    from datetime import date

    from .agent import handle
    from .agent.backends import get_backend

    con = connect()
    ans = handle(get_backend(args.backend), con, Path(args.email_file).read_text(), date.fromisoformat(args.date), args.attach)
    if ans.spec is None:
        print("Needs clarification before any numbers are produced:")
        for q in ans.questions:
            print(f"  - {q}")
        return 2
    out_dir = ROOT / "out" / "ask"
    md = write(ans.result, out_dir, first_incomplete_month(con))
    (out_dir / "reply_draft.txt").write_text(ans.reply or "")
    print(f"{'PASS' if ans.result.passed else 'FAIL'}  report -> {md}")
    print(f"reply draft ({ans.reply_source}, NOT sent) -> {out_dir / 'reply_draft.txt'}")
    for f in ans.card.get("follow_ups") or []:
        print(f"  follow-up: {f}")
    return 0 if ans.result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
