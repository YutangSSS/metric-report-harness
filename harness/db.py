"""Build the DuckDB database: raw CSVs -> staging tables -> fct_stays."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"


def connect(
    intakes_csv: Path | str = DATA_DIR / "aac_intakes.csv",
    outcomes_csv: Path | str = DATA_DIR / "aac_outcomes.csv",
) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(
        "create table raw_intakes as select animal_id, datetime::timestamp as datetime, intake_type, "
        "intake_condition, animal_type, found_location from read_csv_auto(?, header=true)",
        [str(intakes_csv)],
    )
    con.execute(
        "create table raw_outcomes as select animal_id, datetime::timestamp as datetime, outcome_type, "
        "outcome_subtype from read_csv_auto(?, header=true)",
        [str(outcomes_csv)],
    )
    build_models(con)
    return con


def build_models(con: duckdb.DuckDBPyConnection) -> None:
    for sql_file in sorted(MODELS_DIR.glob("*.sql")):
        con.execute(sql_file.read_text())


def data_cut(con: duckdb.DuckDBPyConnection) -> date:
    """Last calendar day with any recorded event. Periods ending after this are incomplete."""
    (cut,) = con.execute(
        "select greatest((select max(intake_dt) from stg_intakes), (select max(outcome_dt) from stg_outcomes))::date"
    ).fetchone()
    return cut


def first_incomplete_month(con: duckdb.DuckDBPyConnection) -> date:
    """First day of the earliest month that is not fully covered by the data.

    Coverage is judged on intakes, because a month with outcomes but no intakes recorded on its last
    days is still being entered.
    """
    (last_intake,) = con.execute("select max(intake_dt)::date from stg_intakes").fetchone()
    return date(last_intake.year, last_intake.month, 1)


def data_quality(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Counts of every source problem the models handle, printed in each report."""
    q = lambda sql: con.execute(sql).fetchone()[0]
    return {
        "duplicate intake rows removed": q("select count(*) from raw_intakes") - q("select count(*) from stg_intakes"),
        "stays closed at the next intake (no outcome recorded)": q("select count(*) from fct_stays where outcome_type = 'Not recorded'"),
        "outcomes with no matching intake (animal arrived before the data starts)": q(
            "select count(*) from stg_outcomes o where not exists (select 1 from fct_stays s where s.outcome_id = o.outcome_id)"),
        "stays open more than 180 days at the data cut": q(
            "select count(*) from fct_stays where outcome_dt is null and intake_dt < (select max(intake_dt) from fct_stays) - interval 180 day"),
    }
