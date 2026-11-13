"""Agent layer, offline. A scripted backend stands in for the model, so these tests check the code
around the model: card validation, spec templates, the eval's scoring, and the reply grounding gate."""
import pytest

from harness.agent.backends import ScriptedBackend
from harness.agent.card import CARD_SCHEMA, card_to_spec
from harness.agent.evaluate import load_cases, run_case
from harness.agent.summary import facts_sheet, grounding_check, write_reply
from harness.runner import ROOT, load_spec, run
from datetime import date


def card(**kw):
    base = {k: "" for k in CARD_SCHEMA["properties"]}
    base.update({"metrics": [], "fiscal_years": [], "filters": [], "exclude_intake_types": [], "questions": [], "follow_ups": [],
                 "per_month_metrics": [], "full_years": 0, "min_days": 0, "list_view": False})
    base.update(kw)
    assert set(base) == set(CARD_SCHEMA["required"])
    return base


# What a correct reading of each eval email looks like.
CARDS = {
    "e01": card(request_type="placemat", quarter="2017-18 Q3", metrics=["intakes", "outcomes", "in_care"], dimension="region_type"),
    "e02": card(request_type="breakdown_change", metrics=["in_care"], dimension="custody_group", previous="2016-17 YTD", current="2017-18 YTD"),
    "e03": card(request_type="reviewer_check", metrics=["in_care"], dimension="custody_group", previous="2016-17 YTD", current="2017-18 YTD"),
    "e04": card(request_type="extraction", as_of="2018-02-15", full_years=3,
                filters=[{"column": "region_type", "value": "Outside jurisdiction"}]),
    "e05": card(request_type="annual_series", metrics=["intakes"], dimension="intake_type", from_fy="2014-15", to_fy="2017-18"),
    "e06": card(request_type="monthly_summary", metrics=["intakes"], dimension="intake_type",
                fiscal_years=["2015-16", "2016-17", "2017-18"], filters=[{"column": "animal_type", "value": "Bird"}]),
    "e07": card(request_type="monthly_summary", metrics=["intakes"], dimension="intake_type", list_view=True,
                fiscal_years=["2015-16", "2016-17", "2017-18"], filters=[{"column": "animal_type", "value": "Bird"}]),
    "e08": card(request_type="month_end_list", month="2018-01", min_days=30, filters=[{"column": "animal_type", "value": "Dog"}]),
    "e09": card(request_type="point_in_time", as_of="2017-12-31", dimension="animal_type", second_dimension="region_type",
                exclude_intake_types=["Wildlife"]),
    "e10": card(request_type="comparison", previous="2016-17 YTD", current="2017-18 YTD",
                metrics=["intakes", "outcomes", "adoptions", "long_stays", "in_care"], per_month_metrics=["intakes"]),
    "a01": card(request_type="placemat", metrics=["intakes"]),  # no quarter given
    "a02": card(request_type="extraction"),                     # no date, no filter, no years
    "a03": card(request_type="unsupported", questions=["Forecasting is outside these tools."]),
}


def scripted_for(case_id, reply="All checks passed."):
    return ScriptedBackend(json_answer=lambda _p: CARDS[case_id], text_answer=lambda _p: reply)


@pytest.mark.parametrize("case", load_cases(), ids=lambda c: c["id"])
def test_correct_card_reproduces_golden_numbers(con, case):
    r = run_case(scripted_for(case["id"]), con, case)
    assert r["passed"], r["why"]


def test_wrong_card_fails_the_eval(con):
    case = next(c for c in load_cases() if c["id"] == "e01")
    wrong = dict(CARDS["e01"], quarter="2017-18 Q2")  # misread quarter
    r = run_case(ScriptedBackend(json_answer=lambda _p: wrong, text_answer=lambda _p: "ok"), con, case)
    assert not r["passed"] and "differ" in r["why"]


def test_unknown_filter_value_becomes_a_question():
    spec, qs = card_to_spec(card(request_type="month_end_list", month="2018-01",
                                 filters=[{"column": "animal_type", "value": "Horse"}]), date(2018, 3, 1))
    assert spec is None and any("Horse" in q for q in qs)


# --- reply grounding ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def reviewer_result(con):
    return run(load_spec(ROOT / "specs" / "03_reviewer_comparison.yaml"), con)


def test_grounded_reply_passes(reviewer_result):
    reply = ("Thanks. Public assist % change: you used unrounded averages (20.2 vs my 18.9). Stray hold: you rounded "
             "the part alone (738 vs 739). Owner surrender: % divided by the wrong year (1.4 vs -1.4). Other differs "
             "for real (17 vs 16, and 41.7 vs 33.3), so let's compare definitions.")
    g = grounding_check(reply, facts_sheet(reviewer_result), reviewer_result)
    assert g.passed, g


def test_invented_number_is_caught_and_template_used(reviewer_result):
    bad = ("Public assist, Stray hold, Owner surrender and Other differ. Overall the total fell 3.5%.")  # 3.5 is not a fact
    reply, g, source = write_reply(ScriptedBackend(text_answer=lambda _p: bad), reviewer_result)
    assert not g.passed and "3.5" in g.invented
    assert source == "template" and reply == reviewer_result.extras["reply_draft"]


def test_missing_reviewer_difference_is_caught(reviewer_result):
    reply = "Public assist and Stray hold differ because of rounding."
    g = grounding_check(reply, facts_sheet(reviewer_result), reviewer_result)
    assert not g.passed and any(m.startswith("Other") for m in g.missing)
