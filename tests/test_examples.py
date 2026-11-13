"""The ten example requests, run end to end on the real public data.

Each example must (1) pass every verifier check and (2) agree with the independent Python recount
(tests/oracle.py) on the cells that recount can reach.
"""
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path

import pytest

import oracle
from harness import drift
from harness.db import connect
from harness.rounding import round_half_up
from harness.runner import ROOT, load_spec, run

SPECS = sorted((ROOT / "specs").glob("*.yaml"))


def _run(con, name, **params):
    return run(load_spec(ROOT / "specs" / name), con, params)


@pytest.mark.parametrize("path", SPECS, ids=lambda p: p.stem)
def test_every_example_passes_the_gate(con, path):
    result = run(load_spec(path), con)
    failed = [f"{c.table}: {c.name}: {c.detail}" for c in result.checks if not c.passed]
    assert not failed, failed
    assert len(result.checks) > 0


def test_01_placemat_matches_independent_recount(con, oracle_stays):
    r = _run(con, "01_quarterly_placemat.yaml")
    intakes, _, in_care = r.tables
    row = next(x for x in intakes.rows if x.startswith("Current FY period"))
    for region in ["City of Austin", "Outside jurisdiction", "Rest of Travis County"]:
        n = oracle.intakes(oracle_stays, datetime(2017, 4, 1), datetime(2018, 1, 1), region)
        assert abs(intakes.get(row, region) - D(n) / 9) <= 1  # shown values may move by 1 to add up
    total = oracle.intakes(oracle_stays, datetime(2017, 4, 1), datetime(2018, 1, 1))
    assert intakes.get(row, "Total") == round_half_up(total / 9)
    dec = next(x for x in in_care.rows if x.startswith("Single month"))
    assert in_care.get(dec, "Total") == oracle.in_care(oracle_stays, datetime(2018, 1, 1))


def test_01_next_quarter_is_one_parameter(con):
    r = _run(con, "01_quarterly_placemat.yaml", quarter="2017-18 Q2")
    assert any("Apr-Sep 2017" in row for row in r.tables[0].rows)
    assert r.passed


def test_02_monthly_average_in_care_matches_recount(con, oracle_stays):
    r = _run(con, "02_custody_monthly_averages.yaml")
    t = r.tables[0]
    months = [datetime(2017 + (m < 4), m, 1) for m in [5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]]
    expected = sum(oracle.in_care(oracle_stays, m) for m in months) / len(months)
    assert t.get("Total", t.columns[1]) == round_half_up(expected)


def test_03_reviewer_differences_are_explained(con):
    r = _run(con, "03_reviewer_comparison.yaml")
    verdicts = {(d.row, d.col.split(" [")[0]): d.verdict for d in r.extras["reviewer_diffs"] if d.verdict != "match"}
    assert verdicts == {
        ("Public assist", "% change"): "% from unrounded",
        ("Stray hold", "FY 2016-17 YTD (Apr-Feb 2017)"): "rounding (parts)",
        ("Owner surrender", "% change"): "% reversed",
        ("Other", "FY 2017-18 YTD (Apr-Feb 2018)"): "real difference",
        ("Other", "% change"): "real difference",
    }
    assert "2 difference(s) need a closer look" in r.extras["reply_draft"]


def test_04_extraction_list_and_ongoing_rule(con):
    t = _run(con, "04_outside_jurisdiction_extract.yaml").tables[0]
    assert {d["region_type"] for d in t.detail} == {"Outside jurisdiction"}
    assert t.get("Total", "Intakes") == len(t.detail)
    as_of_end = datetime(2018, 2, 16)
    for d in t.detail:
        open_then = d["intake_dt"] < as_of_end and (d["outcome_dt"] is None or d["outcome_dt"] >= as_of_end)
        assert d["ongoing_as_of"] == open_then
        assert (d["date_of_death"] is not None) == bool(d["deceased"])


def test_05_partial_year_is_labelled(con):
    t = _run(con, "05_chart_update.yaml").tables[0]
    assert t.rows[-1].startswith("FY 2017-18 YTD")
    assert any("partial year" in n for n in t.notes)


def test_05_strict_mode_fails_on_partial_year(con):
    spec = load_spec(ROOT / "specs" / "05_chart_update.yaml")
    spec["tables"][0]["incomplete"] = "fail"
    assert not run(spec, con).passed


def test_06_zero_months_are_shown(con):
    t = _run(con, "06_monthly_summary.yaml").tables[0]
    assert len(t.rows) == 35  # Apr 2015 to Feb 2018
    assert any(t.get(r, "Total") == 0 for r in t.rows)


def test_07_list_adds_up_to_summary(con):
    t = _run(con, "07_list_view.yaml").tables[0]
    assert len(t.detail) == sum(t.get(r, "Total") for r in t.rows)


def test_08_rerun_drift_names_the_record_and_the_field(con, tmp_path):
    spec = load_spec(ROOT / "specs" / "08_month_end_list.yaml")
    spec.pop("snapshot")
    first = run(spec, con).tables[0].detail
    victim = first[0]

    # The source changes after the first run: an adoption is back-dated into January.
    ins, outs = tmp_path / "intakes.csv", tmp_path / "outcomes.csv"
    con.execute(f"copy raw_intakes to '{ins}' (header)")
    con.execute(f"copy raw_outcomes to '{outs}' (header)")
    with outs.open("a") as f:
        f.write(f"{victim['animal_id']},2018-01-20 12:00:00,Adoption,\n")
    later = connect(ins, outs)
    second = run(spec, later).tables[0].detail
    assert len(second) == len(first) - 1

    changes = drift.diff(first, second, con, later)
    assert len(changes) == 1
    c = changes[0]
    assert (c.animal_id, c.change) == (victim["animal_id"], "removed")
    assert "outcome_dt: None -> 2018-01-20 12:00:00" in c.reason
    assert "Adoption" in c.reason


def test_09_point_in_time_agrees_with_month_end_stock(con, oracle_stays):
    spec = load_spec(ROOT / "specs" / "09_point_in_time.yaml")
    spec["tables"][0]["exclude_intake_types"] = []
    spec["tables"][0]["lookback_years"] = 10
    t = run(spec, con).tables[0]
    assert t.get("Total", "Total") == oracle.in_care(oracle_stays, datetime(2018, 1, 1))


def test_10_labels_and_same_scope(con):
    t = _run(con, "10_executive_comparison.yaml").tables[0]
    labels = {r: t.get(r, "What the number is") for r in t.rows}
    assert labels["Intakes started"] == "Total, year to date"
    assert labels["Intakes started per month"] == "Monthly average, year to date"
    assert t.columns[:2] == ["FY 2016-17 YTD (Apr-Feb 2017)", "FY 2017-18 YTD (Apr-Feb 2018)"]
