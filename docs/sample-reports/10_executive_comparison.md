# 10 · Executive two-year comparison

**Request:** For the briefing note: intakes, stays closed, adoptions and intakes that became 30+ day stays, 2017-18 against 2016-17, with change and % change. Make clear what each number is.

**Data:** Austin Animal Center intakes and outcomes (public), complete through February 2018.

## FY 2017-18 to date against the same months of FY 2016-17

| | FY 2016-17 YTD (Apr-Feb 2017) | FY 2017-18 YTD (Apr-Feb 2018) | Change | % change | What the number is |
|---|---:|---:|---:|---:|---:|
| Intakes started | 16,260 | 15,949 | -311 | -1.9% | Total, year to date |
| Intakes started per month | 1,478 | 1,450 | -28 | -1.9% | Monthly average, year to date |
| Stays closed | 16,405 | 15,773 | -632 | -3.9% | Total, year to date |
| Adoptions | 7,753 | 7,369 | -384 | -5.0% | Total, year to date |
| Intakes that became 30+ day stays | 2,922 | 2,837 | -85 | -2.9% | Total, year to date |
| Animals in care at month end | 1,089 | 1,066 | -23 | -2.1% | Monthly average, year to date |

- Scope: all region types, filters none, same months in both years.

## Definitions

- Intakes started: count of intake events with intake date in the period.
- Stays closed: count of stays whose outcome date is in the period.
- Adoptions: stays closed in the period with outcome type Adoption.
- Intakes that became long stays: intakes in the period that stayed 30+ days (closed or still open).
- In care at month end: stays with intake before the end of the month and no outcome before it (intake_dt < month_end and (outcome_dt is null or outcome_dt >= month_end)).

## Data quality handled by the models

- duplicate intake rows removed: 27
- duplicate outcome rows removed: 10
- stays closed at the next intake (no outcome recorded): 29
- outcomes with no matching intake (animal arrived before the data starts): 1,351
- stays open more than 180 days at the data cut: 311

## Checks: 15 of 15 passed

- All checks passed. The report can go to QA.
