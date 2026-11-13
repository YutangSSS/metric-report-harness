"""The dbt port must produce exactly the same fct_stays as the harness models (run `dbt build` first)."""
from pathlib import Path

import pytest

DBT_DB = Path(__file__).resolve().parent.parent / "dbt" / "target" / "shelter.duckdb"


@pytest.mark.skipif(not DBT_DB.exists(), reason="run `cd dbt && uv run --group dbt dbt build --profiles-dir .` first")
def test_dbt_fct_stays_matches_harness(con):
    con.execute(f"attach '{DBT_DB}' as dbt (read_only)")
    try:
        cols = [r[0] for r in con.execute("select column_name from information_schema.columns where table_name = 'fct_stays' and table_catalog = 'memory' order by ordinal_position").fetchall()]
        sel = ", ".join(cols)
        only_harness = con.execute(f"select count(*) from (select {sel} from main.fct_stays except all select {sel} from dbt.main.fct_stays)").fetchone()[0]
        only_dbt = con.execute(f"select count(*) from (select {sel} from dbt.main.fct_stays except all select {sel} from main.fct_stays)").fetchone()[0]
        n = con.execute("select count(*) from dbt.main.fct_stays").fetchone()[0]
    finally:
        con.execute("detach dbt")
    assert (only_harness, only_dbt) == (0, 0)
    assert n == 80160
