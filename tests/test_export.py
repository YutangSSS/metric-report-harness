"""The Power BI star schema must reproduce the harness numbers. Each check here mirrors one DAX measure
in powerbi/ShelterReporting.SemanticModel, computed from the exported CSVs only."""
from datetime import date

import duckdb
import pytest

from harness.export import export
from harness.metrics import measure
from harness.periods import parse_period


@pytest.fixture(scope="module")
def star(con, tmp_path_factory):
    out = tmp_path_factory.mktemp("star")
    counts = export(con, out)
    bi = duckdb.connect()
    for name in counts:
        bi.execute(f"create table {name} as select * from read_csv_auto('{out / (name + '.csv')}', header=true)")
    return bi, counts


CUT = date(2018, 3, 1)


def test_row_counts_tie_to_the_model(con, star):
    _, counts = star
    assert counts["fct_stays"] == con.execute("select count(*) from fct_stays").fetchone()[0]
    assert counts["dim_region"] == 3


def test_intakes_measure(con, star):
    bi, _ = star
    # DAX: Intakes = COUNTROWS(fct_stays), filtered through the active intake_date -> dim_date relationship
    got = dict(bi.execute("""select s.region_type, count(*) from fct_stays s join dim_date d on d.date = s.intake_date
                             where d.fiscal_year = '2016-17' group by 1""").fetchall())
    want = measure(con, "intakes", parse_period("2016-17", CUT), "region_type")
    assert got == {k: int(v) for k, v in want.items()}


def test_stays_closed_measure_uses_outcome_date(con, star):
    bi, _ = star
    # DAX: Stays Closed = CALCULATE(COUNTROWS(fct_stays), USERELATIONSHIP(fct_stays[outcome_date], dim_date[date]))
    (got,) = bi.execute("""select count(*) from fct_stays s join dim_date d on d.date = s.outcome_date
                           where d.fiscal_year = '2016-17'""").fetchone()
    assert got == measure(con, "outcomes", parse_period("2016-17", CUT))["Total"]


def test_in_care_monthly_average_measure(con, star):
    bi, _ = star
    # DAX: In Care Avg = AVERAGEX(VALUES(dim_date[month_start]), COALESCE(CALCULATE(COUNTROWS(fct_in_care_monthly)), 0))
    got = dict(bi.execute("""
        with months as (select distinct month_start from dim_date where fiscal_year = '2017-18' and is_complete_month),
             per as (select m.month_start, c.custody_group, count(c.stay_id) n
                     from months m left join fct_in_care_monthly c on c.month_start = m.month_start group by all)
        select custody_group, sum(n)::double / (select count(*) from months) from per where custody_group is not null group by 1
    """).fetchall())
    want = measure(con, "in_care", parse_period("2017-18 YTD", CUT), "custody_group", stat="monthly_average")
    assert got.keys() == want.keys()
    for k in want:
        assert got[k] == pytest.approx(want[k])


def test_fiscal_calendar(star):
    bi, _ = star
    rows = dict(bi.execute("select date::varchar, fiscal_quarter || ' ' || fiscal_year from dim_date "
                           "where date in ('2017-04-01', '2017-12-31', '2018-03-31')").fetchall())
    assert rows == {"2017-04-01": "Q1 2017-18", "2017-12-31": "Q3 2017-18", "2018-03-31": "Q4 2017-18"}
