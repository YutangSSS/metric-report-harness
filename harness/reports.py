"""Table builders, one per kind of request. Each builder computes numbers in SQL (metrics.py),
rounds them under the house rules (rounding.py), and writes down claims for the verifier."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable

import duckdb

from .metrics import domain, measure, stat_label
from .periods import (
    Period, add_months, fiscal_year, fiscal_ytd, fy_label, fy_of, parse_fy, parse_period, placemat_periods,
)
from .rounding import pct_change, round_half_up, round_hierarchy
from .table import Table


@dataclass
class Context:
    con: duckdb.DuckDBPyConnection
    first_incomplete_month: date
    params: dict[str, Any]


def _p(ctx: Context, text: str) -> Period:
    return parse_period(str(text).format(**ctx.params), ctx.first_incomplete_month)


# --- 1. Quarterly placemat --------------------------------------------------------------------

def placemat(ctx: Context, ts: dict) -> Table:
    periods = placemat_periods(ctx.params["quarter"], ts.get("current", "ytd"))
    metric, stat, dim = ts["metric"], ts.get("stat", "monthly_average"), ts["dimension"]
    decimals = ts.get("decimals", 0)
    names = {
        "previous_fy": "Previous fiscal year",
        "single_month": "Single month",
        "previous_fy_period": "Previous FY, same period",
        "current_fy_period": "Current FY period",
    }
    rows = {k: f"{names[k]}: {p.label} [{stat_label(stat, p)}]" for k, p in periods.items()}
    cols = domain(ctx.con, dim) + ["Total"]
    pct_row = "% change, current vs previous FY same period"
    t = Table(ts["title"], cols, list(rows.values()) + [pct_row], metrics=[metric], periods=list(periods.values()))
    for k, p in periods.items():
        raw = measure(ctx.con, metric, p, dim, ts.get("filters"), stat)
        shown = round_hierarchy(raw, None, decimals)
        for c in cols:
            t.set(rows[k], c, shown[c])
        t.claim_sum([(rows[k], c) for c in cols[:-1]], (rows[k], "Total"))
    for c in cols:
        old, new = (rows["previous_fy_period"], c), (rows["current_fy_period"], c)
        t.set(pct_row, c, pct_change(t.get(*old), t.get(*new)))
        t.claim_pct(old, new, (pct_row, c))
    return t


# --- 2. Breakdown with subtotals and % change (legal-authority style) -------------------------

def breakdown_change(ctx: Context, ts: dict) -> Table:
    prev, cur = _p(ctx, ts["previous"]), _p(ctx, ts["current"])
    metric, stat, dim = ts["metric"], ts.get("stat", "monthly_average"), ts["dimension"]
    groups: dict[str, list[str]] = ts.get("groups", {})
    decimals = ts.get("decimals", 0)
    leaves = domain(ctx.con, dim)
    rows = ts.get("row_order") or (leaves + list(groups) + ["Total"])
    cols = [f"{prev.label} [{stat_label(stat, prev)}]", f"{cur.label} [{stat_label(stat, cur)}]", "% change"]
    t = Table(ts["title"], cols, rows, metrics=[metric], periods=[prev, cur])
    for col, p in zip(cols[:2], (prev, cur)):
        raw = measure(ctx.con, metric, p, dim, ts.get("filters"), stat)
        shown = round_hierarchy(raw, groups, decimals)
        for r in rows:
            t.set(r, col, shown[r])
        for g, members in groups.items():
            t.claim_sum([(m, col) for m in members], (g, col))
        top = list(groups) + [leaf for leaf in leaves if not any(leaf in ms for ms in groups.values())]
        t.claim_sum([(r, col) for r in top], ("Total", col))
    for r in rows:
        t.set(r, "% change", pct_change(t.get(r, cols[0]), t.get(r, cols[1])))
        t.claim_pct((r, cols[0]), (r, cols[1]), (r, "% change"))
    for col, p in zip(cols[:2], (prev, cur)):
        raw = measure(ctx.con, metric, p, dim, ts.get("filters"), stat)
        for g, ms in groups.items():
            raw[g] = sum(raw[m] for m in ms)
        raw["Total"] = sum(v for k, v in raw.items() if k in leaves)
        for r in rows:
            t.raw[(r, col)] = raw[r]
    return t


# --- 4. Ad hoc extraction with as-of "ongoing" logic --------------------------------------------

def extraction(ctx: Context, ts: dict) -> Table:
    as_of = date.fromisoformat(str(ctx.params["as_of"]))
    # "On date D" means at the end of D: intake before D+1, and no outcome before D+1.
    as_of_ts = datetime(as_of.year, as_of.month, as_of.day) + timedelta(days=1)
    filters = ts.get("filters", {})
    cur_fy = fy_of(as_of)
    years = [fiscal_year(fy) for fy in range(cur_fy - ts["full_years"], cur_fy)]
    ytd_start = date(cur_fy, 4, 1)
    years.append(Period(f"FY {fy_label(cur_fy)} YTD (Apr 1-{as_of:%b %-d %Y})", ytd_start, as_of + timedelta(days=1), "ytd"))
    where = " and ".join(f"{k} = ?" for k in filters) or "true"
    detail_rows = ctx.con.execute(
        f"""select animal_id, stay_id, intake_dt, intake_type, animal_type, region_type,
                   outcome_dt, outcome_type, deceased
            from fct_stays where {where} and intake_dt >= ? and intake_dt < ? order by intake_dt, stay_id""",
        [*filters.values(), datetime.combine(years[0].start, datetime.min.time()),
         datetime.combine(years[-1].end, datetime.min.time())],
    ).fetchall()
    cols_d = ["animal_id", "stay_id", "intake_dt", "intake_type", "animal_type", "region_type",
              "outcome_dt", "outcome_type", "deceased"]
    detail = []
    for r in detail_rows:
        d = dict(zip(cols_d, r))
        d["fiscal_year"] = fy_label(fy_of(d["intake_dt"].date()))
        d["ongoing_as_of"] = d["intake_dt"] < as_of_ts and (d["outcome_dt"] is None or d["outcome_dt"] >= as_of_ts)
        d["days_open_as_of"] = (as_of_ts - d["intake_dt"]).days if d["ongoing_as_of"] else None
        d["date_of_death"] = d["outcome_dt"].date() if d["deceased"] else None
        detail.append(d)

    cols = ["Intakes", "Repeat intakes", "Died or euthanized", "Ongoing as of " + as_of.isoformat()]
    rows = [f"{p.label} [{stat_label('total', p)}]" for p in years] + ["Total"]
    t = Table(ts["title"], cols, rows, metrics=["intakes"], periods=years, detail=detail)
    repeat = {r[0] for r in ctx.con.execute("select stay_id from fct_stays where is_repeat_intake").fetchall()}
    for label, p in zip(rows, years):
        in_p = [d for d in detail if p.start <= d["intake_dt"].date() < p.end]
        t.set(label, cols[0], Decimal(len(in_p)))
        t.set(label, cols[1], Decimal(sum(d["stay_id"] in repeat for d in in_p)))
        t.set(label, cols[2], Decimal(sum(bool(d["deceased"]) for d in in_p)))
        t.set(label, cols[3], Decimal(sum(d["ongoing_as_of"] for d in in_p)))
        sql_count = measure(ctx.con, "intakes", p, None, filters)["Total"]
        t.claim_equal(f"list rows = summary count: {p.label}", Decimal(len(in_p)), round_half_up(sql_count))
    for c in cols:
        t.set("Total", c, sum(t.get(r, c) for r in rows[:-1]))
        t.claim_sum([(r, c) for r in rows[:-1]], ("Total", c))
    bad = [d for d in detail if d["ongoing_as_of"] and not (d["outcome_dt"] is None or d["outcome_dt"] >= as_of_ts)]
    t.claim_true("ongoing rule: open on or before as-of, no outcome or outcome after it", not bad, f"{len(bad)} rows break it")
    t.claim_true("one row per stay", len({d["stay_id"] for d in detail}) == len(detail), "duplicate stay rows")
    t.notes.append(
        f"Ongoing as of {as_of}: intake on or before {as_of} and no outcome, or an outcome after the end of {as_of}. "
        "Date of death is filled only when the outcome is Died or Euthanasia."
    )
    return t


# --- 5. Annual series for a chart --------------------------------------------------------------

def annual_series(ctx: Context, ts: dict) -> Table:
    first, last = parse_fy(ts["from_fy"]), parse_fy(ts["to_fy"])
    periods = []
    for fy in range(first, last + 1):
        p = fiscal_year(fy)
        if not p.is_complete(ctx.first_incomplete_month):
            if ts.get("incomplete", "ytd") == "fail":
                periods.append(p)  # verifier will reject it
                continue
            p = fiscal_ytd(fy, ctx.first_incomplete_month)
        periods.append(p)
    metric, dim = ts["metric"], ts.get("dimension")
    cols = (domain(ctx.con, dim) if dim else []) + ["Total"]
    rows = [f"{p.label} [{stat_label('total', p)}]" for p in periods]
    t = Table(ts["title"], cols, rows, metrics=[metric], periods=periods)
    for r, p in zip(rows, periods):
        raw = measure(ctx.con, metric, p, dim, ts.get("filters"))
        shown = round_hierarchy(raw, None, 0) if dim else {"Total": round_half_up(raw["Total"])}
        for c in cols:
            t.set(r, c, shown[c])
        if dim:
            t.claim_sum([(r, c) for c in cols[:-1]], (r, "Total"))
        if p.kind == "ytd":
            t.notes.append(f"{p.label} is a partial year. Do not plot it beside full years without this label.")
    fys = [fy_of(p.start) for p in periods]
    t.claim_true("one bar per fiscal year, no gaps", fys == list(range(first, last + 1)), f"years {fys}")
    return t


# --- 6/7. Monthly summary with filters, zero-filled, optional list view ----------------------

def monthly_summary(ctx: Context, ts: dict) -> Table:
    fys = [parse_fy(y) for y in ts["fiscal_years"]]
    months: list[Period] = []
    for fy in fys:
        for m in fiscal_year(fy).month_starts():
            if m < ctx.first_incomplete_month:
                months.append(Period(f"{m:%Y-%m}", m, add_months(m, 1), "month"))
    metric, dim, filters = ts["metric"], ts.get("dimension"), ts.get("filters", {})
    cols = ["Fiscal year"] + (domain(ctx.con, dim) if dim else []) + ["Total"]
    rows = [m.label for m in months]
    t = Table(ts["title"], cols, rows, metrics=[metric], periods=[])
    for m in months:
        raw = measure(ctx.con, metric, m, dim, filters)
        t.set(m.label, "Fiscal year", fy_label(fy_of(m.start)))
        for c in cols[1:-1]:
            t.set(m.label, c, round_half_up(raw[c]))
        t.set(m.label, "Total", round_half_up(sum(raw.values())))
        if dim:
            t.claim_sum([(m.label, c) for c in cols[1:-1]], (m.label, "Total"))
    expected = sum(1 for fy in fys for m in fiscal_year(fy).month_starts() if m < ctx.first_incomplete_month)
    t.claim_true("every month present, including months with zero", len(rows) == expected, f"{len(rows)} of {expected}")
    zero_months = [r for r in rows if t.get(r, "Total") == 0]
    if zero_months:
        t.notes.append(f"{len(zero_months)} month(s) have zero records and are shown as 0, not dropped.")
    if any(not fiscal_year(fy).is_complete(ctx.first_incomplete_month) for fy in fys):
        t.notes.append(f"Months from {ctx.first_incomplete_month:%b %Y} on are not shown: the data is not complete yet.")

    if ts.get("list_view"):
        where = " and ".join(f"{k} = ?" for k in filters) or "true"
        date_col = "intake_dt" if metric == "intakes" else "outcome_dt"
        recs = ctx.con.execute(
            f"""select animal_id, stay_id, intake_dt, outcome_dt, intake_type, outcome_type, animal_type, region_type
                from fct_stays where {where} and {date_col} >= ? and {date_col} < ? order by {date_col}, stay_id""",
            [*filters.values(), datetime.combine(months[0].start, datetime.min.time()),
             datetime.combine(months[-1].end, datetime.min.time())],
        ).fetchall()
        keys = ["animal_id", "stay_id", "intake_dt", "outcome_dt", "intake_type", "outcome_type", "animal_type", "region_type"]
        t.detail = [dict(zip(keys, r)) for r in recs]
        for m in months:
            n = sum(1 for d in t.detail if d[date_col] is not None and m.start <= d[date_col].date() < m.end)
            t.claim_equal(f"list adds up to summary: {m.label}", Decimal(n), t.get(m.label, "Total"))
    return t


# --- 8. Monthly list for a partner team (rerun drift is checked in drift.py) -------------------

def month_end_list(ctx: Context, ts: dict) -> Table:
    month = date.fromisoformat(str(ctx.params["month"]) + "-01")
    month_end = add_months(month, 1)
    me_ts = datetime(month_end.year, month_end.month, 1)
    min_days = int(ts.get("min_days_in_care", 30))
    filters = ts.get("filters", {})
    where = " and ".join(f"{k} = ?" for k in filters) or "true"
    recs = ctx.con.execute(
        f"""select animal_id, stay_id, intake_dt, intake_type, animal_type, region_type,
                   date_diff('day', intake_dt, ?::timestamp) as days_in_care_at_month_end
            from fct_stays
            where {where} and intake_dt < ? and (outcome_dt is null or outcome_dt >= ?)
              and date_diff('day', intake_dt, ?::timestamp) >= ?
            order by animal_id, stay_id""",
        [me_ts, *filters.values(), me_ts, me_ts, me_ts, min_days],
    ).fetchall()
    keys = ["animal_id", "stay_id", "intake_dt", "intake_type", "animal_type", "region_type", "days_in_care_at_month_end"]
    detail = [dict(zip(keys, r)) for r in recs]
    p = Period(f"{month:%b %Y}", month, month_end, "month")
    dims = domain(ctx.con, "animal_type")
    t = Table(ts["title"], ["Animals"], dims + ["Total"], metrics=["in_care"], periods=[p], detail=detail)
    for a in dims:
        t.set(a, "Animals", Decimal(sum(1 for d in detail if d["animal_type"] == a)))
    t.set("Total", "Animals", Decimal(len(detail)))
    t.claim_sum([(a, "Animals") for a in dims], ("Total", "Animals"))
    t.claim_true("one row per animal", len({d["animal_id"] for d in detail}) == len(detail), "an animal is listed twice")
    t.notes.append(f"In care at the end of {month:%B %Y} for {min_days}+ days. Data as loaded at run time; reruns are compared by drift.py.")
    return t


# --- 9. Point-in-time population cross-tab ----------------------------------------------------

def point_in_time(ctx: Context, ts: dict) -> Table:
    as_of = date.fromisoformat(str(ctx.params["as_of"]))
    as_of_ts = datetime(as_of.year, as_of.month, as_of.day) + timedelta(days=1)  # end of the as-of day
    lookback = add_months(date(as_of.year, as_of.month, 1), -12 * int(ts.get("lookback_years", 4)))
    rows_dim, cols_dim = ts["rows"], ts["columns"]
    excl = ts.get("exclude_intake_types", [])
    excl_sql = f"and intake_type not in ({', '.join('?' for _ in excl)})" if excl else ""
    recs = ctx.con.execute(
        f"""select animal_id, {rows_dim}, {cols_dim} from fct_stays
            where intake_dt < ? and (outcome_dt is null or outcome_dt >= ?) and intake_dt >= ? {excl_sql}""",
        [as_of_ts, as_of_ts, datetime(lookback.year, lookback.month, 1), *excl],
    ).fetchall()
    rvals, cvals = domain(ctx.con, rows_dim), domain(ctx.con, cols_dim)
    t = Table(ts["title"], cvals + ["Total"], rvals + ["Total"], metrics=["in_care"], periods=[])
    for r in rvals:
        for c in cvals:
            t.set(r, c, Decimal(len({a for a, rv, cv in recs if rv == r and cv == c})))
        t.set(r, "Total", Decimal(len({a for a, rv, _ in recs if rv == r})))
        t.claim_sum([(r, c) for c in cvals], (r, "Total"))
    for c in cvals + ["Total"]:
        if c != "Total":
            t.set("Total", c, Decimal(len({a for a, _, cv in recs if cv == c})))
        t.claim_sum([(r, c) for r in rvals], ("Total", c))
    t.set("Total", "Total", Decimal(len({a for a, _, _ in recs})))
    t.claim_equal("distinct animals = stays in care (nobody counted twice)", len({a for a, _, _ in recs}), len(recs))
    t.notes.append(
        f"Distinct animals in care on {as_of} (intake on or before, no outcome or outcome after), "
        f"intake within {ts.get('lookback_years', 4)} years before, excluding intake types {excl or 'none'}."
    )
    return t


# --- 10. Two-period executive comparison ------------------------------------------------------

def comparison(ctx: Context, ts: dict) -> Table:
    prev, cur = _p(ctx, ts["previous"]), _p(ctx, ts["current"])
    if prev.months != cur.months:
        raise ValueError(f"{prev.label} and {cur.label} cover different numbers of months")
    cols = [prev.label, cur.label, "Change", "% change", "What the number is"]
    rows = [m["label"] for m in ts["measures"]]
    t = Table(ts["title"], cols, rows, metrics=[m["metric"] for m in ts["measures"]], periods=[prev, cur])
    for m in ts["measures"]:
        stat = m.get("stat", "total")
        a = round_half_up(measure(ctx.con, m["metric"], prev, None, ts.get("filters"), stat)["Total"], m.get("decimals", 0))
        b = round_half_up(measure(ctx.con, m["metric"], cur, None, ts.get("filters"), stat)["Total"], m.get("decimals", 0))
        t.set(m["label"], prev.label, a)
        t.set(m["label"], cur.label, b)
        t.set(m["label"], "Change", b - a)
        t.set(m["label"], "% change", pct_change(a, b))
        t.set(m["label"], "What the number is", stat_label(stat, cur))
        t.claim_pct((m["label"], prev.label), (m["label"], cur.label), (m["label"], "% change"))
        t.claim_equal(f"change = current - previous: {m['label']}", t.get(m["label"], "Change"), b - a)
    t.claim_true("same scope both years (same filters, same months of the year)",
                 prev.start.month == cur.start.month and prev.months == cur.months, "periods differ")
    t.notes.append(f"Scope: all region types, filters {ts.get('filters') or 'none'}, same months in both years.")
    return t


BUILDERS: dict[str, Callable[[Context, dict], Table]] = {
    "placemat": placemat,
    "breakdown_change": breakdown_change,
    "extraction": extraction,
    "annual_series": annual_series,
    "monthly_summary": monthly_summary,
    "month_end_list": month_end_list,
    "point_in_time": point_in_time,
    "comparison": comparison,
}
