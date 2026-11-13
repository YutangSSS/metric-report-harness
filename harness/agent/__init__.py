"""The agent layer: request email -> request card (model) -> spec (code) -> verified report (harness)
-> reply draft (model, grounding-checked by code). Nothing is sent anywhere."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ..db import first_incomplete_month
from ..runner import Result, run
from .card import card_to_spec, read_email
from .summary import Grounding, write_reply


@dataclass
class Answer:
    card: dict[str, Any]
    questions: list[str] = field(default_factory=list)
    spec: dict[str, Any] | None = None
    result: Result | None = None
    reply: str | None = None
    grounding: Grounding | None = None
    reply_source: str | None = None


def handle(backend, con, email: str, email_date: date, attachment: str | None = None, reply: bool = True) -> Answer:
    card = read_email(backend, email, email_date)
    spec, questions = card_to_spec(card, first_incomplete_month(con), attachment)
    if spec is None:
        return Answer(card, questions)
    spec["request"] = email.strip().splitlines()[0] if email.strip() else "(empty)"
    spec["_path"] = "agent"
    result = run(spec, con)
    ans = Answer(card, [], spec, result)
    if reply and result.passed:
        ans.reply, ans.grounding, ans.reply_source = write_reply(backend, result)
    return ans
