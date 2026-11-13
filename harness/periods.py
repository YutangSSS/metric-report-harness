"""Fiscal periods. A fiscal year runs April to March, labelled like 2017-18.

Every period is half-open: start <= t < end. That one rule removes the "is the last day included?"
argument from every query.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

FY_START_MONTH = 4


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def month_name(d: date) -> str:
    return d.strftime("%b %Y")


@dataclass(frozen=True)
class Period:
    label: str
    start: date
    end: date  # exclusive
    kind: str  # fiscal_year | quarter | month | ytd | range

    @property
    def months(self) -> int:
        return (self.end.year - self.start.year) * 12 + self.end.month - self.start.month

    def month_starts(self) -> list[date]:
        return [add_months(self.start, i) for i in range(self.months)]

    def shift_years(self, years: int, label: str | None = None) -> "Period":
        s, e = add_months(self.start, 12 * years), add_months(self.end, 12 * years)
        return Period(label or f"{self.label} ({years:+d}y)", s, e, self.kind)

    def is_complete(self, first_incomplete_month: date) -> bool:
        return self.end <= first_incomplete_month


def fy_label(fy: int) -> str:
    return f"{fy}-{str(fy + 1)[2:]}"


def fy_of(d: date) -> int:
    return d.year if d.month >= FY_START_MONTH else d.year - 1


def parse_fy(text: str) -> int:
    m = re.fullmatch(r"(\d{4})-(\d{2})", text.strip())
    if not m or (int(m.group(1)) + 1) % 100 != int(m.group(2)):
        raise ValueError(f"fiscal year must look like 2017-18, got {text!r}")
    return int(m.group(1))


def fiscal_year(fy: int) -> Period:
    s = date(fy, FY_START_MONTH, 1)
    return Period(f"FY {fy_label(fy)}", s, add_months(s, 12), "fiscal_year")


def fiscal_quarter(fy: int, q: int) -> Period:
    if q not in (1, 2, 3, 4):
        raise ValueError("quarter must be 1-4")
    s = add_months(date(fy, FY_START_MONTH, 1), 3 * (q - 1))
    e = add_months(s, 3)
    return Period(f"FY {fy_label(fy)} Q{q} ({s:%b}-{add_months(e, -1):%b})", s, e, "quarter")


def fiscal_ytd(fy: int, through_month_end_exclusive: date) -> Period:
    s = date(fy, FY_START_MONTH, 1)
    e = min(through_month_end_exclusive, add_months(s, 12))
    if e <= s:
        raise ValueError("YTD period is empty")
    return Period(f"FY {fy_label(fy)} YTD ({s:%b}-{add_months(e, -1):%b %Y})", s, e, "ytd")


def single_month(d: date) -> Period:
    s = date(d.year, d.month, 1)
    return Period(month_name(s), s, add_months(s, 1), "month")


def parse_quarter(text: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{4}-\d{2})\s*Q([1-4])", text.strip())
    if not m:
        raise ValueError(f"quarter must look like '2017-18 Q3', got {text!r}")
    return parse_fy(m.group(1)), int(m.group(2))


def parse_period(text: str, first_incomplete_month: date) -> Period:
    """Parse the period phrases used in specs.

    '2016-17'        full fiscal year
    '2017-18 Q3'     fiscal quarter
    '2017-18 YTD'    fiscal year to date, through the last complete month of the data
                     (for an earlier year: the same months, so the two are comparable)
    '2018-02'        a single calendar month
    """
    t = text.strip()
    if re.fullmatch(r"\d{4}-\d{2}", t) and int(t[5:]) <= 12 and (int(t[:4]) + 1) % 100 != int(t[5:]):
        y, m = int(t[:4]), int(t[5:])
        return single_month(date(y, m, 1))
    if re.fullmatch(r"\d{4}-\d{2}", t):
        return fiscal_year(parse_fy(t))
    if re.fullmatch(r"\d{4}-\d{2}\s*Q[1-4]", t):
        return fiscal_quarter(*parse_quarter(t))
    m = re.fullmatch(r"(\d{4}-\d{2})\s*YTD", t)
    if m:
        fy = parse_fy(m.group(1))
        cut_fy = fy_of(first_incomplete_month)
        through = first_incomplete_month.replace(year=first_incomplete_month.year - (cut_fy - fy))
        return fiscal_ytd(fy, through)
    raise ValueError(f"cannot parse period {text!r}")


def placemat_periods(quarter: str, current: str = "ytd") -> dict[str, Period]:
    """The four rows of the quarterly placemat, all derived from one parameter.

    This replaces hand-editing five DECLARE statements in each of ~10 queries every quarter.
    current = 'ytd'     -> current-year row is fiscal year to date through the quarter (3, 6, 9 or 12 months)
    current = 'quarter' -> current-year row is the quarter alone (always 3 months)
    """
    fy, q = parse_quarter(quarter)
    cur_q = fiscal_quarter(fy, q)
    if current == "ytd":
        cur = fiscal_ytd(fy, cur_q.end)
        prev = fiscal_ytd(fy - 1, cur_q.end.replace(year=cur_q.end.year - 1))
    elif current == "quarter":
        cur = cur_q
        prev = fiscal_quarter(fy - 1, q)
    else:
        raise ValueError("current must be 'ytd' or 'quarter'")
    return {
        "previous_fy": fiscal_year(fy - 1),
        "single_month": single_month(add_months(cur_q.end, -1)),
        "previous_fy_period": prev,
        "current_fy_period": cur,
    }
