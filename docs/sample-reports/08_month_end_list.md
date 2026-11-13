# 08 · Month-end list for a partner team

**Request:** Send the partner team the list of dogs in care 30+ days at the end of January 2018.

**Parameters:** `month = 2018-01`

**Data:** Austin Animal Center intakes and outcomes (public), complete through February 2018.

## Dogs in care 30+ days at month end

| | Animals |
|---|---:|
| Bird | 0 |
| Cat | 0 |
| Dog | 316 |
| Livestock | 0 |
| Other | 0 |
| Total | 316 |

List view: 316 records (see CSV).

- In care at the end of January 2018 for 30+ days. Data as loaded at run time; reruns are compared by drift.py.

## Definitions

- In care at month end: stays with intake before the end of the month and no outcome before it (intake_dt < month_end and (outcome_dt is null or outcome_dt >= month_end)).

## Data quality handled by the models

- duplicate intake rows removed: 27
- duplicate outcome rows removed: 10
- stays closed at the next intake (no outcome recorded): 29
- outcomes with no matching intake (animal arrived before the data starts): 1,351
- stays open more than 180 days at the data cut: 311

## Checks: 3 of 3 passed

- All checks passed. The report can go to QA.
