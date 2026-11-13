"""Email -> request card -> spec.

The model's only job is reading: it fills a request card (JSON, fixed schema) from the email.
Code then checks the card, asks for anything missing, and builds a spec from fixed templates.
The model never writes SQL and never produces a number.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from ..metrics import DEFINITIONS, DIMENSIONS
from ..periods import parse_fy, parse_period

REQUEST_TYPES = {
    "placemat": "Quarterly placemat: monthly averages by region type for previous FY, last month of quarter, FY to date vs same months last year. Needs: quarter.",
    "breakdown_change": "One measure split by a category, two periods side by side, with subtotals and % change. Needs: previous, current, dimension.",
    "reviewer_check": "Compare a QA reviewer's numbers (attached CSV) to ours for the custody table and draft a reply. Needs: attachment.",
    "extraction": "Record-level list of intakes for a filter, last N full fiscal years plus year to date, ongoing as of a date, deceased flag. Needs: as_of, filter.",
    "annual_series": "One number per fiscal year (for a chart), optionally split by a category. Needs: from and to fiscal years.",
    "monthly_summary": "Counts by month across fiscal years, with filters, zero months shown, optional list view. Needs: fiscal_years.",
    "month_end_list": "List of animals in care N+ days at a month end, for a partner team. Needs: month.",
    "point_in_time": "Distinct animals in care on a date, cross-tab of two categories. Needs: as_of, two dimensions.",
    "comparison": "Executive comparison of several measures, previous vs current period, change and % change. Needs: previous, current.",
    "unsupported": "Anything the tools above cannot answer.",
}
FILTER_VALUES = {
    "region_type": ["City of Austin", "Rest of Travis County", "Outside jurisdiction"],
    "animal_type": ["Dog", "Cat", "Bird", "Other", "Livestock"],
    "intake_type": ["Stray", "Owner Surrender", "Public Assist", "Wildlife", "Euthanasia Request"],
}

CARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["request_type", "metrics", "dimension", "second_dimension", "quarter", "previous", "current",
                 "from_fy", "to_fy", "fiscal_years", "as_of", "month", "filters", "exclude_intake_types",
                 "full_years", "min_days", "list_view", "per_month_metrics", "reviewer", "due", "questions", "follow_ups"],
    "properties": {
        "request_type": {"type": "string", "enum": list(REQUEST_TYPES)},
        "metrics": {"type": "array", "items": {"type": "string", "enum": list(DEFINITIONS)}},
        "dimension": {"type": "string", "enum": sorted(DIMENSIONS) + [""]},
        "second_dimension": {"type": "string", "enum": sorted(DIMENSIONS) + [""]},
        "quarter": {"type": "string", "description": "like '2017-18 Q3', or '' if not stated"},
        "previous": {"type": "string", "description": "period like '2016-17', '2016-17 YTD', '2016-17 Q3', or ''"},
        "current": {"type": "string", "description": "period like '2017-18 YTD', or ''"},
        "from_fy": {"type": "string", "description": "like '2014-15', or ''"},
        "to_fy": {"type": "string", "description": "like '2017-18', or ''"},
        "fiscal_years": {"type": "array", "items": {"type": "string"}},
        "as_of": {"type": "string", "description": "YYYY-MM-DD, or ''"},
        "month": {"type": "string", "description": "YYYY-MM, or ''"},
        "filters": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False, "required": ["column", "value"],
                "properties": {"column": {"type": "string", "enum": list(FILTER_VALUES)}, "value": {"type": "string"}},
            },
        },
        "exclude_intake_types": {"type": "array", "items": {"type": "string"}},
        "full_years": {"type": "integer", "description": "number of full fiscal years before the current one, 0 if not stated"},
        "min_days": {"type": "integer", "description": "minimum days in care for a month-end list, 0 if not stated"},
        "list_view": {"type": "boolean"},
        "per_month_metrics": {"type": "array", "items": {"type": "string", "enum": list(DEFINITIONS)},
                              "description": "comparison only: metrics also wanted as a monthly average beside the total"},
        "reviewer": {"type": "string"},
        "due": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "string"},
                      "description": "blocking questions only: missing or ambiguous information whose answer would change a number"},
        "follow_ups": {"type": "array", "items": {"type": "string"},
                       "description": "non-blocking points to confirm later (reviewer, deadline, format); they never change a number"},
    },
}

SYSTEM = f"""You read reporting requests from a manager and fill in a request card. You do not answer the request.

The reporting system can run these request types:
{chr(10).join(f'- {k}: {v}' for k, v in REQUEST_TYPES.items())}

Metrics: {'; '.join(f'{k} = {v}' for k, v in DEFINITIONS.items())}
Dimensions: region_type (City of Austin / Rest of Travis County / Outside jurisdiction), custody_group (Public assist / Stray hold / Owner surrender / Other), animal_type, intake_type, outcome_type.
Filter values: {FILTER_VALUES}

House rules that are already decided (never ask about these; the system applies them):
- "To date" / YTD runs through the last complete month of data, and the earlier year uses the same months.
- The in-custody subtotal is Stray hold + Owner surrender; the total is all custody groups.
- "Ongoing as of D" means intake on or before D and no outcome before the end of D. "As of today" means the email date.
- Rounding, % change and labels follow fixed rules; region types are always all three unless a filter is named.
- Point-in-time counts use a four-year look-back; month-end lists default to 30+ days in care.

Rules:
- Fiscal years run April to March and are written like 2017-18. "This year" means the fiscal year containing the email date; "to date" means YTD.
- Fill a field only from what the email says or clearly implies. Leave strings empty, lists empty and numbers 0 when not stated.
- If the email leaves out something the request type needs, or a term could mean two different things that give different numbers, add a short question to questions instead of guessing.
- Anything whose answer would not change a number (who reviews it, when it is due, file format) goes in follow_ups, never in questions.
- If nothing in the list can answer it, use request_type unsupported and say why in questions."""


def read_email(backend, email: str, email_date: date) -> dict[str, Any]:
    prompt = f"Email date: {email_date.isoformat()}\n\n<email>\n{email.strip()}\n</email>\n\nFill in the request card."
    return backend.json(SYSTEM, prompt, CARD_SCHEMA)


def _valid_period(text: str, cut: date) -> bool:
    try:
        parse_period(text, cut)
        return True
    except ValueError:
        return False


def card_to_spec(card: dict[str, Any], first_incomplete_month: date, attachment: str | None = None
                 ) -> tuple[dict[str, Any] | None, list[str]]:
    """Return (spec, []) when the card is complete, or (None, questions) when something is missing.

    Every check here is code. The model's own questions are passed through; code adds its own.
    """
    t = card["request_type"]
    questions = list(card.get("questions") or [])
    filters = {f["column"]: f["value"] for f in card.get("filters") or []}
    for col, val in filters.items():
        if val not in FILTER_VALUES.get(col, []):
            questions.append(f"'{val}' is not a known {col}. Which of {FILTER_VALUES[col]} did you mean?")
    metrics = card.get("metrics") or []
    cut = first_incomplete_month

    def need(cond: bool, q: str):
        if not cond:
            questions.append(q)

    tables: list[dict[str, Any]] = []
    params: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    if t == "unsupported":
        questions = questions or ["This request is outside what the reporting tools can answer."]
    elif t == "placemat":
        need(bool(re.fullmatch(r"\d{4}-\d{2}\s*Q[1-4]", card["quarter"])), "Which quarter is this placemat for (for example 2017-18 Q3)?")
        need(bool(metrics), "Which measures should the placemat show?")
        params["quarter"] = card["quarter"]
        titles = {"intakes": "Average number of intakes started each month", "outcomes": "Average number of stays closed each month",
                  "in_care": "Average number of animals in care at month end", "adoptions": "Average number of adoptions each month",
                  "long_stays": "Average number of intakes that became 30+ day stays"}
        for m in metrics:
            tables.append({"kind": "placemat", "title": titles[m], "metric": m, "stat": "monthly_average",
                           "dimension": card["dimension"] or "region_type", "current": "ytd"})
    elif t in ("breakdown_change", "reviewer_check"):
        if t == "reviewer_check":
            need(attachment is not None, "Please attach the reviewer's numbers as a CSV.")
            extra["reviewer_csv"] = attachment
        prev, cur = card["previous"] or "2016-17 YTD", card["current"] or "2017-18 YTD"
        if t == "breakdown_change":
            need(bool(card["previous"] and card["current"]), "Which two periods should be compared?")
            need(_valid_period(prev, cut) and _valid_period(cur, cut), f"I could not read the periods '{prev}' and '{cur}'.")
        dim = card["dimension"] or "custody_group"
        table = {"kind": "breakdown_change", "title": "Average animals in care at month end, by custody type",
                 "metric": (metrics or ["in_care"])[0], "stat": "monthly_average", "dimension": dim,
                 "previous": prev, "current": cur}
        if dim == "custody_group":
            table["groups"] = {"In shelter custody": ["Stray hold", "Owner surrender"]}
            table["row_order"] = ["Public assist", "Stray hold", "Owner surrender", "In shelter custody", "Other", "Total"]
        tables.append(table)
    elif t == "extraction":
        need(bool(card["as_of"]), "As of which date should files count as ongoing?")
        need(bool(filters), "Which records should the extraction include (for example outside-jurisdiction intakes)?")
        need(card["full_years"] > 0, "How many full fiscal years before this one should the extraction cover?")
        params["as_of"] = card["as_of"]
        tables.append({"kind": "extraction", "title": "Intakes by fiscal year", "filters": filters,
                       "full_years": card["full_years"]})
    elif t == "annual_series":
        need(bool(card["from_fy"] and card["to_fy"]), "Which fiscal years should the chart cover?")
        tables.append({"kind": "annual_series", "title": "Intakes started by fiscal year", "metric": (metrics or ["intakes"])[0],
                       "dimension": card["dimension"] or None, "from_fy": card["from_fy"], "to_fy": card["to_fy"], "incomplete": "ytd"})
    elif t == "monthly_summary":
        need(bool(card["fiscal_years"]), "Which fiscal years should the summary cover?")
        tables.append({"kind": "monthly_summary", "title": "Monthly summary", "metric": (metrics or ["intakes"])[0],
                       "dimension": card["dimension"] or None, "fiscal_years": card["fiscal_years"], "filters": filters,
                       "list_view": bool(card["list_view"])})
    elif t == "month_end_list":
        need(bool(re.fullmatch(r"\d{4}-\d{2}", card["month"])), "Which month end is the list for?")
        params["month"] = card["month"]
        tables.append({"kind": "month_end_list", "title": "Animals in care at month end",
                       "min_days_in_care": card["min_days"] or 30, "filters": filters})
    elif t == "point_in_time":
        need(bool(card["as_of"]), "On which date should the population be counted?")
        need(bool(card["dimension"] and card["second_dimension"]), "Which two categories should the table cross?")
        params["as_of"] = card["as_of"]
        tables.append({"kind": "point_in_time", "title": "Distinct animals in care", "rows": card["dimension"],
                       "columns": card["second_dimension"], "lookback_years": 4,
                       "exclude_intake_types": card["exclude_intake_types"]})
    elif t == "comparison":
        need(bool(card["previous"] and card["current"]), "Which two periods should be compared?")
        need(bool(metrics), "Which measures should the comparison include?")
        labels = {"intakes": "Intakes started", "outcomes": "Stays closed", "adoptions": "Adoptions",
                  "long_stays": "Intakes that became 30+ day stays", "in_care": "Animals in care at month end"}
        measures = []
        for m in metrics:
            measures.append({"label": labels[m], "metric": m, "stat": "monthly_average" if m == "in_care" else "total"})
            if m != "in_care" and m in (card.get("per_month_metrics") or []):
                measures.append({"label": f"{labels[m]} per month", "metric": m, "stat": "monthly_average"})
        tables.append({"kind": "comparison", "title": f"{card['current']} against {card['previous']}",
                       "previous": card["previous"], "current": card["current"], "measures": measures})
    else:
        questions.append(f"Unknown request type {t!r}.")

    for fy in [card.get("from_fy"), card.get("to_fy"), *(card.get("fiscal_years") or [])]:
        if fy:
            try:
                parse_fy(fy)
            except ValueError:
                questions.append(f"'{fy}' is not a fiscal year like 2017-18.")
    if questions:
        return None, questions
    spec = {"id": "agent", "title": f"Request: {t}", "request": "(from email)", "params": params, "tables": tables, **extra}
    return spec, []
