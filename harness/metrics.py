"""Metric definitions. Code owns every number: the SQL lives here, not in a prompt or a spreadsheet.

Each metric has one written definition (DEFINITIONS) that is printed in every report that uses it.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Mapping

import duckdb

from .periods import Period

DIMENSIONS = {"region_type", "custody_group", "animal_type", "intake_type", "outcome_type"}
FILTER_COLUMNS = DIMENSIONS | {"is_repeat_intake", "deceased"}

DEFINITIONS = {
    "intakes": "Intakes started: count of intake events with intake date in the period.",
    "outcomes": "Stays closed: count of stays whose outcome date is in the period.",
    "adoptions": "Adoptions: stays closed in the period with outcome type Adoption.",
    "in_care": (
        "In care at month end: stays with intake before the end of the month and no outcome before it "
        "(intake_dt < month_end and (outcome_dt is null or outcome_dt >= month_end))."
    ),
    "long_stays": "Intakes that became long stays: intakes in the period that stayed 30+ days (closed or still open).",
}

# For a monthly average, flow metrics divide the period total by the number of months;
# in_care is a stock, so it averages the month-end counts instead.
STOCK_METRICS = {"in_care"}


def _filter_sql(filters: Mapping[str, object] | None) -> tuple[str, list]:
    if not filters:
        return "", []
    clauses, params = [], []
    for col, value in filters.items():
        if col not in FILTER_COLUMNS:
            raise ValueError(f"unknown filter column {col!r}")
        values = list(value) if isinstance(value, (list, tuple, set)) else [value]
        clauses.append(f"{col} in ({', '.join('?' for _ in values)})")
        params.extend(values)
    return " and " + " and ".join(clauses), params


def _ts(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def domain(con: duckdb.DuckDBPyConnection, dimension: str) -> list[str]:
    """Every value a dimension can take, from the whole dataset, so empty cells show 0, not a missing row."""
    if dimension not in DIMENSIONS:
        raise ValueError(f"unknown dimension {dimension!r}")
    return [r[0] for r in con.execute(f"select distinct {dimension} from fct_stays where {dimension} is not null order by 1").fetchall()]


def measure(
    con: duckdb.DuckDBPyConnection,
    metric: str,
    period: Period,
    dimension: str | None = None,
    filters: Mapping[str, object] | None = None,
    stat: str = "total",
    long_stay_days: int = 30,
) -> dict[str, float]:
    """Return {dimension value: number} (or {'Total': number} with no dimension), zero-filled."""
    if dimension is not None and dimension not in DIMENSIONS:
        raise ValueError(f"unknown dimension {dimension!r}")
    dim_sql = dimension or "'Total'"
    where, params = _filter_sql(filters)
    s, e = _ts(period.start), _ts(period.end)

    if metric == "in_care":
        sql = f"""
            with m as (select unnest(?::timestamp[]) as month_end)
            select {dim_sql} as k, count(*)::double as n
            from m join fct_stays s
              on s.intake_dt < m.month_end and (s.outcome_dt is null or s.outcome_dt >= m.month_end)
            where true {where}
            group by 1"""
        month_ends = [_ts(m) for m in period.month_starts()[1:]] + [e]
        rows = con.execute(sql, [month_ends, *params]).fetchall()
        divisor = len(month_ends) if stat == "monthly_average" else 1
        if stat == "total":
            if period.months != 1:
                raise ValueError("in_care is a stock: use stat monthly_average for multi-month periods")
    else:
        if metric == "intakes":
            cond = "intake_dt >= ? and intake_dt < ?"
        elif metric in ("outcomes", "adoptions"):
            cond = "outcome_dt >= ? and outcome_dt < ?"
            if metric == "adoptions":
                cond += " and outcome_type = 'Adoption'"
        elif metric == "long_stays":
            cond = (
                "intake_dt >= ? and intake_dt < ? and "
                f"coalesce(days_in_care, date_diff('day', intake_dt, (select max(intake_dt) from fct_stays))) >= {int(long_stay_days)}"
            )
        else:
            raise ValueError(f"unknown metric {metric!r}")
        sql = f"select {dim_sql} as k, count(*)::double as n from fct_stays where {cond} {where} group by 1"
        rows = con.execute(sql, [s, e, *params]).fetchall()
        divisor = period.months if stat == "monthly_average" else 1

    if stat not in ("total", "monthly_average"):
        raise ValueError(f"unknown stat {stat!r}")
    out = {k: 0.0 for k in (domain(con, dimension) if dimension else ["Total"])}
    for k, n in rows:
        out[k] = n / divisor
    return out


def stat_label(stat: str, period: Period) -> str:
    """The label an executive needs to read a number correctly."""
    base = {"total": "Total", "monthly_average": "Monthly average"}[stat]
    if period.kind == "ytd":
        return f"{base}, year to date"
    if period.kind == "fiscal_year" and stat == "total":
        return "Annual total"
    if period.kind == "month":
        return "Month-end count" if stat == "monthly_average" else "Month total"
    return base


def describe(metrics: Iterable[str]) -> list[str]:
    return [DEFINITIONS[m] for m in dict.fromkeys(metrics)]
