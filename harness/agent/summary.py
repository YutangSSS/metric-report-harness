"""LLM-written reply, checked by code before anyone sees it.

The model gets a facts sheet built from the verified tables and writes a short reply. Then
`grounding_check` fails the reply if it contains any number that is not in the facts sheet, or if it
leaves out a reviewer difference. A reply that fails is replaced by the plain template reply.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from ..runner import Result
from ..table import fmt

SYSTEM = """You write short replies from a data analyst to their manager or a QA reviewer.
Use only the facts given. Every number you write must appear in the facts exactly as written there.
Do not round, add, subtract or compute anything, and do not invent dates or counts.
Plain English, no headers, under 180 words. Do not add a signature."""

NUM = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?%?")


def facts_sheet(r: Result) -> str:
    lines = [f"Request: {r.spec['request'].strip()}"]
    for t in r.tables:
        lines.append(f"\nTable: {t.title}")
        for row in t.rows:
            cells = []
            for c in t.columns:
                v = t.get(row, c)
                pct = "%" in c or "%" in row
                s = fmt(v, 1 if pct else 0)
                cells.append(f"{c} = {s}{'%' if pct and isinstance(v, Decimal) else ''}")
            lines.append(f"- {row}: " + "; ".join(cells))
        for n in t.notes:
            lines.append(f"Note: {n}")
    passed = sum(c.passed for c in r.checks)
    lines.append(f"\nChecks passed: {passed} of {len(r.checks)}")
    for d in r.extras.get("reviewer_diffs", []):
        if d.verdict != "match":
            lines.append(f"Reviewer difference: {d.row} / {d.col}: reviewer {d.theirs}, ours {d.ours}, cause: {d.verdict}")
    return "\n".join(lines)


def _numbers(text: str) -> set[str]:
    return {m.group(0).replace(",", "").rstrip("%") for m in NUM.finditer(text)}


@dataclass
class Grounding:
    passed: bool
    invented: list[str]
    missing: list[str]


def grounding_check(reply: str, facts: str, r: Result) -> Grounding:
    allowed = _numbers(facts)
    allowed |= {n.lstrip("-") for n in allowed}  # "down 2.1%" for a -2.1% fact is fine
    invented = sorted(n for n in _numbers(reply) if n not in allowed and n.lstrip("-") not in allowed)
    missing = []
    for d in r.extras.get("reviewer_diffs", []):
        if d.verdict != "match" and d.row.lower() not in reply.lower():
            missing.append(f"{d.row} / {d.col}")
    return Grounding(not invented and not missing, invented, missing)


def write_reply(backend, r: Result) -> tuple[str, Grounding, str]:
    """Returns (reply, grounding, source) where source is 'model' or 'template'."""
    facts = facts_sheet(r)
    reply = backend.text(SYSTEM, f"<facts>\n{facts}\n</facts>\n\nWrite the reply.")
    g = grounding_check(reply, facts, r)
    if g.passed:
        return reply, g, "model"
    fallback = r.extras.get("reply_draft") or ("The report is attached. All checks passed." if r.passed else "The report did not pass its checks.")
    return fallback, g, "template"
