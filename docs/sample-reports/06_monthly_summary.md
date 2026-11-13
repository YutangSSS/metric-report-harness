# 06 · Monthly summary with filters

**Request:** Build a monthly summary of bird intakes by intake type for FY 2015-16 to FY 2017-18 to date. Months with none should still show.

**Data:** Austin Animal Center intakes and outcomes (public), complete through February 2018.

## Bird intakes by month and intake type

| | Fiscal year | Euthanasia Request | Owner Surrender | Public Assist | Stray | Wildlife | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2015-04 | 2015-16 | 0 | 0 | 0 | 3 | 2 | 5 |
| 2015-05 | 2015-16 | 0 | 0 | 2 | 7 | 2 | 11 |
| 2015-06 | 2015-16 | 0 | 0 | 2 | 1 | 0 | 3 |
| 2015-07 | 2015-16 | 0 | 0 | 0 | 0 | 1 | 1 |
| 2015-08 | 2015-16 | 0 | 0 | 0 | 1 | 1 | 2 |
| 2015-09 | 2015-16 | 0 | 0 | 0 | 1 | 1 | 2 |
| 2015-10 | 2015-16 | 0 | 0 | 0 | 6 | 3 | 9 |
| 2015-11 | 2015-16 | 1 | 0 | 0 | 1 | 1 | 3 |
| 2015-12 | 2015-16 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2016-01 | 2015-16 | 0 | 0 | 0 | 2 | 4 | 6 |
| 2016-02 | 2015-16 | 0 | 0 | 45 | 2 | 1 | 48 |
| 2016-03 | 2015-16 | 0 | 3 | 6 | 2 | 2 | 13 |
| 2016-04 | 2016-17 | 0 | 0 | 0 | 7 | 4 | 11 |
| 2016-05 | 2016-17 | 0 | 0 | 0 | 4 | 7 | 11 |
| 2016-06 | 2016-17 | 0 | 0 | 0 | 3 | 2 | 5 |
| 2016-07 | 2016-17 | 0 | 2 | 0 | 2 | 3 | 7 |
| 2016-08 | 2016-17 | 0 | 2 | 0 | 2 | 2 | 6 |
| 2016-09 | 2016-17 | 0 | 1 | 1 | 3 | 2 | 7 |
| 2016-10 | 2016-17 | 0 | 1 | 0 | 6 | 1 | 8 |
| 2016-11 | 2016-17 | 0 | 0 | 1 | 4 | 2 | 7 |
| 2016-12 | 2016-17 | 0 | 0 | 2 | 4 | 3 | 9 |
| 2017-01 | 2016-17 | 0 | 0 | 0 | 1 | 0 | 1 |
| 2017-02 | 2016-17 | 0 | 0 | 0 | 3 | 2 | 5 |
| 2017-03 | 2016-17 | 0 | 0 | 0 | 3 | 1 | 4 |
| 2017-04 | 2017-18 | 0 | 2 | 0 | 7 | 3 | 12 |
| 2017-05 | 2017-18 | 0 | 0 | 0 | 11 | 2 | 13 |
| 2017-06 | 2017-18 | 0 | 2 | 0 | 6 | 0 | 8 |
| 2017-07 | 2017-18 | 0 | 1 | 0 | 6 | 5 | 12 |
| 2017-08 | 2017-18 | 0 | 1 | 0 | 3 | 4 | 8 |
| 2017-09 | 2017-18 | 0 | 3 | 0 | 4 | 0 | 7 |
| 2017-10 | 2017-18 | 0 | 5 | 0 | 4 | 1 | 10 |
| 2017-11 | 2017-18 | 0 | 0 | 0 | 4 | 1 | 5 |
| 2017-12 | 2017-18 | 0 | 0 | 0 | 1 | 1 | 2 |
| 2018-01 | 2017-18 | 0 | 1 | 0 | 6 | 0 | 7 |
| 2018-02 | 2017-18 | 0 | 1 | 0 | 1 | 0 | 2 |

- 1 month(s) have zero records and are shown as 0, not dropped.
- Months from Mar 2018 on are not shown: the data is not complete yet.

## Definitions

- Intakes started: count of intake events with intake date in the period.

## Data quality handled by the models

- duplicate intake rows removed: 27
- stays closed at the next intake (no outcome recorded): 29
- outcomes with no matching intake (animal arrived before the data starts): 1,361
- stays open more than 180 days at the data cut: 311

## Checks: 36 of 36 passed

- All checks passed. The report can go to QA.
