# 09 · Point-in-time population tables

**Request:** How many distinct animals were in care on Dec 31 2017, by animal type and region type? Leave out wildlife intakes, and only count intakes from the last four years.

**Parameters:** `as_of = 2017-12-31`

**Data:** Austin Animal Center intakes and outcomes (public), complete through February 2018.

## Distinct animals in care by animal type and region type

| | City of Austin | Outside jurisdiction | Rest of Travis County | Total |
|---|---:|---:|---:|---:|
| Bird | 5 | 0 | 0 | 5 |
| Cat | 354 | 2 | 23 | 379 |
| Dog | 428 | 17 | 81 | 526 |
| Livestock | 0 | 0 | 0 | 0 |
| Other | 13 | 0 | 1 | 14 |
| Total | 800 | 19 | 105 | 924 |

- Distinct animals in care on 2017-12-31 (intake on or before, no outcome or outcome after), intake within 4 years before, excluding intake types ['Wildlife'].

## Definitions

- In care at month end: stays with intake before the end of the month and no outcome before it (intake_dt < month_end and (outcome_dt is null or outcome_dt >= month_end)).

## Data quality handled by the models

- duplicate intake rows removed: 27
- stays closed at the next intake (no outcome recorded): 29
- outcomes with no matching intake (animal arrived before the data starts): 1,361
- stays open more than 180 days at the data cut: 311

## Checks: 10 of 10 passed

- All checks passed. The report can go to QA.
