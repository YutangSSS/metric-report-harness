# 02 · Monthly averages by custody type, with % change

**Request:** For the placemat, show the average number of animals in care at month end by custody type for FY 2016-17 and FY 2017-18 to date (same months last year), with an "In shelter custody" subtotal (stray hold + owner surrender), the overall total, and % change.

**Data:** Austin Animal Center intakes and outcomes (public), complete through February 2018.

## Average animals in care at month end, by custody type

| | FY 2016-17 YTD (Apr-Feb 2017) [Monthly average, year to date] | FY 2017-18 YTD (Apr-Feb 2018) [Monthly average, year to date] | % change |
|---|---:|---:|---:|
| Public assist | 53 | 63 | 18.9% |
| Stray hold | 739 | 706 | -4.5% |
| Owner surrender | 285 | 281 | -1.4% |
| In shelter custody | 1,024 | 987 | -3.6% |
| Other | 12 | 16 | 33.3% |
| Total | 1,089 | 1,066 | -2.1% |


## Definitions

- In care at month end: stays with intake before the end of the month and no outcome before it (intake_dt < month_end and (outcome_dt is null or outcome_dt >= month_end)).

## Data quality handled by the models

- duplicate intake rows removed: 27
- stays closed at the next intake (no outcome recorded): 29
- outcomes with no matching intake (animal arrived before the data starts): 1,361
- stays open more than 180 days at the data cut: 311

## Checks: 12 of 12 passed

- All checks passed. The report can go to QA.
