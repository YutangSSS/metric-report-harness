"""House rules, on tiny inputs where the right answer can be worked out by hand."""
from datetime import date, datetime
from decimal import Decimal as D

import pytest

from harness.db import data_quality, first_incomplete_month
from harness.metrics import measure
from harness.periods import parse_period, placemat_periods
from harness.rounding import allocate, pct_change, round_half_up, round_hierarchy
from harness.table import Table
from harness.verifier import verify_table


# --- rounding ---------------------------------------------------------------------------------

def test_half_up_not_bankers():
    assert round(2.5) == 2  # Python's default, which Excel users will not expect
    assert round_half_up(2.5) == D(3)
    assert round_half_up(0.125, 2) == D("0.13")


def test_parts_add_up_to_rounded_total():
    raw = {"a": 1.4, "b": 1.4, "c": 1.4}  # independent rounding gives 1+1+1 = 3, but the total 4.2 rounds to 4
    shown = round_hierarchy(raw)
    assert shown["Total"] == D(4)
    assert sum(shown[k] for k in raw) == D(4)


def test_subtotal_and_total_both_tie():
    raw = {"stray": 738.364, "owner": 285.364, "assist": 52.727, "other": 12.273}
    shown = round_hierarchy(raw, {"custody": ["stray", "owner"]})
    assert shown["stray"] + shown["owner"] == shown["custody"]
    assert shown["custody"] + shown["assist"] + shown["other"] == shown["Total"] == D(1089)


def test_allocate_is_deterministic_on_ties():
    assert allocate({"x": 0.5, "y": 0.5}, D(1)) == {"x": D(1), "y": D(0)}


def test_pct_change_uses_shown_numbers_and_handles_zero():
    assert pct_change(D(53), D(63)) == D("18.9")  # unrounded 52.727 -> 63.364 would give 20.2
    assert pct_change(D(0), D(5)) is None


# --- periods ----------------------------------------------------------------------------------

def test_one_parameter_drives_the_placemat():
    p = placemat_periods("2017-18 Q3")
    assert (p["previous_fy"].start, p["previous_fy"].end) == (date(2016, 4, 1), date(2017, 4, 1))
    assert (p["single_month"].start, p["single_month"].months) == (date(2017, 12, 1), 1)
    assert (p["current_fy_period"].start, p["current_fy_period"].end) == (date(2017, 4, 1), date(2018, 1, 1))
    assert (p["previous_fy_period"].start, p["previous_fy_period"].end) == (date(2016, 4, 1), date(2017, 1, 1))
    assert placemat_periods("2017-18 Q2")["current_fy_period"].months == 6
    assert placemat_periods("2017-18 Q2", current="quarter")["current_fy_period"].months == 3


def test_ytd_compares_the_same_months():
    cut = date(2018, 3, 1)
    cur, prev = parse_period("2017-18 YTD", cut), parse_period("2016-17 YTD", cut)
    assert (cur.start, cur.end, prev.start, prev.end) == (date(2017, 4, 1), date(2018, 3, 1), date(2016, 4, 1), date(2017, 3, 1))


def test_bad_period_text_is_rejected():
    with pytest.raises(ValueError):
        parse_period("2017-19", date(2018, 3, 1))


# --- models on a hand-checked tiny dataset ----------------------------------------------------

def test_tiny_boundaries(tiny):
    jan, feb = parse_period("2017-01", date(2017, 3, 1)), parse_period("2017-02", date(2017, 3, 1))
    # A1 arrives Jan 31 23:59 and leaves Feb 1 00:00: still in care at the end of January.
    # A3 is entered twice at the same minute: counted once.
    # A4 has no outcome before its second intake: its first stay closes at that intake.
    assert measure(tiny, "intakes", jan)["Total"] == 3
    assert measure(tiny, "intakes", feb)["Total"] == 2
    assert measure(tiny, "in_care", jan, stat="monthly_average")["Total"] == 3
    assert measure(tiny, "in_care", feb, stat="monthly_average")["Total"] == 2
    by_region = measure(tiny, "intakes", feb, "region_type")
    assert by_region == {"City of Austin": 0, "Outside jurisdiction": 0, "Rest of Travis County": 2}
    assert first_incomplete_month(tiny) == date(2017, 3, 1)
    dq = data_quality(tiny)
    assert dq["duplicate intake rows removed"] == 1
    assert dq["stays closed at the next intake (no outcome recorded)"] == 1
    assert dq["outcomes with no matching intake (animal arrived before the data starts)"] == 1


def test_filters_are_whitelisted(tiny):
    with pytest.raises(ValueError):
        measure(tiny, "intakes", parse_period("2017-01", date(2017, 3, 1)), filters={"1=1; drop table x": 1})


# --- the verifier must catch bad tables -------------------------------------------------------

def _table():
    t = Table("t", ["a", "b", "Total", "% change"], ["2016", "2017"])
    return t


def test_verifier_catches_parts_that_do_not_add_up():
    t = _table()
    for col, v in {"a": D(1), "b": D(1), "Total": D(3)}.items():
        t.set("2016", col, v)
    t.claim_sum([("2016", "a"), ("2016", "b")], ("2016", "Total"))
    assert not verify_table(t, date(2018, 3, 1))[0].passed


def test_verifier_catches_a_reversed_pct():
    t = _table()
    t.set("2016", "Total", D(285))
    t.set("2017", "Total", D(281))
    t.set("2017", "% change", D("1.4"))  # (285 - 281) / 281: divided by the wrong year
    t.claim_pct(("2016", "Total"), ("2017", "Total"), ("2017", "% change"))
    assert not verify_table(t, date(2018, 3, 1))[0].passed


def test_verifier_rejects_an_incomplete_year_not_labelled_ytd():
    t = _table()
    t.periods = [parse_period("2017-18", date(2018, 3, 1))]
    checks = verify_table(t, date(2018, 3, 1))
    assert [c.passed for c in checks if "period complete" in c.name] == [False]
