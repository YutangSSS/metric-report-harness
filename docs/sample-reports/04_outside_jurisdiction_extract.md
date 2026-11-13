# 04 · Ad hoc extraction, outside-jurisdiction intakes

**Request:** Pull all intakes from outside our jurisdiction for the last three fiscal years and 2017-18 to date. Tell me which are still ongoing as of Feb 15 2018 and how long they have been open, and flag any that died or were euthanized, with the date. QA by the reviewer. Due tomorrow.

**Parameters:** `as_of = 2018-02-15`

**Data:** Austin Animal Center intakes and outcomes (public), complete through February 2018.

## Outside-jurisdiction intakes by fiscal year

| | Intakes | Repeat intakes | Died or euthanized | Ongoing as of 2018-02-15 |
|---|---:|---:|---:|---:|
| FY 2014-15 [Annual total] | 83 | 37 | 10 | 0 |
| FY 2015-16 [Annual total] | 151 | 100 | 2 | 3 |
| FY 2016-17 [Annual total] | 221 | 123 | 2 | 1 |
| FY 2017-18 YTD (Apr 1-Feb 15 2018) [Total, year to date] | 422 | 141 | 6 | 16 |
| Total | 877 | 401 | 20 | 20 |

List view: 877 records (see CSV).

- Ongoing as of 2018-02-15: intake on or before 2018-02-15 and no outcome, or an outcome after the end of 2018-02-15. Date of death is filled only when the outcome is Died or Euthanasia.

## Definitions

- Intakes started: count of intake events with intake date in the period.

## Data quality handled by the models

- duplicate intake rows removed: 27
- stays closed at the next intake (no outcome recorded): 29
- outcomes with no matching intake (animal arrived before the data starts): 1,361
- stays open more than 180 days at the data cut: 311

## Checks: 14 of 14 passed

- All checks passed. The report can go to QA.
