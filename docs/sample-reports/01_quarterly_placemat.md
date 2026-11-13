# 01 · Quarterly placemat

**Request:** Please prepare the Q3 placemat: average intakes started each month, average stays closed each month and average animals in care at month end, by region type, for the previous fiscal year, the last month of the quarter, and the fiscal year to date against the same months last year.

**Parameters:** `quarter = 2017-18 Q3`

**Data:** Austin Animal Center intakes and outcomes (public), complete through February 2018.

## Average number of intakes started each month

| | City of Austin | Outside jurisdiction | Rest of Travis County | Total |
|---|---:|---:|---:|---:|
| Previous fiscal year: FY 2016-17 [Monthly average] | 1,228 | 18 | 222 | 1,468 |
| Single month: Dec 2017 [Month-end count] | 993 | 20 | 142 | 1,155 |
| Previous FY, same period: FY 2016-17 YTD (Apr-Dec 2016) [Monthly average, year to date] | 1,297 | 17 | 224 | 1,538 |
| Current FY period: FY 2017-18 YTD (Apr-Dec 2017) [Monthly average, year to date] | 1,268 | 45 | 218 | 1,531 |
| % change, current vs previous FY same period | -2.2% | 164.7% | -2.7% | -0.5% |


## Average number of stays closed each month

| | City of Austin | Outside jurisdiction | Rest of Travis County | Total |
|---|---:|---:|---:|---:|
| Previous fiscal year: FY 2016-17 [Monthly average] | 1,237 | 18 | 223 | 1,478 |
| Single month: Dec 2017 [Month-end count] | 1,044 | 27 | 162 | 1,233 |
| Previous FY, same period: FY 2016-17 YTD (Apr-Dec 2016) [Monthly average, year to date] | 1,291 | 17 | 221 | 1,529 |
| Current FY period: FY 2017-18 YTD (Apr-Dec 2017) [Monthly average, year to date] | 1,244 | 45 | 219 | 1,508 |
| % change, current vs previous FY same period | -3.6% | 164.7% | -0.9% | -1.4% |


## Average number of animals in care at month end

| | City of Austin | Outside jurisdiction | Rest of Travis County | Total |
|---|---:|---:|---:|---:|
| Previous fiscal year: FY 2016-17 [Monthly average] | 889 | 18 | 152 | 1,059 |
| Single month: Dec 2017 [Month-end count] | 819 | 19 | 106 | 944 |
| Previous FY, same period: FY 2016-17 YTD (Apr-Dec 2016) [Monthly average, year to date] | 988 | 19 | 160 | 1,167 |
| Current FY period: FY 2017-18 YTD (Apr-Dec 2017) [Monthly average, year to date] | 928 | 31 | 143 | 1,102 |
| % change, current vs previous FY same period | -6.1% | 63.2% | -10.6% | -5.6% |


## Definitions

- Intakes started: count of intake events with intake date in the period.
- Stays closed: count of stays whose outcome date is in the period.
- In care at month end: stays with intake before the end of the month and no outcome before it (intake_dt < month_end and (outcome_dt is null or outcome_dt >= month_end)).

## Data quality handled by the models

- duplicate intake rows removed: 27
- stays closed at the next intake (no outcome recorded): 29
- outcomes with no matching intake (animal arrived before the data starts): 1,361
- stays open more than 180 days at the data cut: 311

## Checks: 36 of 36 passed

- All checks passed. The report can go to QA.
