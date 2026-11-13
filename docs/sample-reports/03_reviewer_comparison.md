# 03 · QA reviewer comparison

**Request:** The reviewer's numbers for the custody table don't match yours in a few cells. Can you check each one and reply with what's going on?

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

## Reviewer comparison

| Cell | Ours | Reviewer | Verdict |
|---|---:|---:|---|
| Public assist / FY 2016-17 YTD (Apr-Feb 2017) [Monthly average, year to date] | 53 | 53 | match |
| Public assist / FY 2017-18 YTD (Apr-Feb 2018) [Monthly average, year to date] | 63 | 63 | match |
| Public assist / % change | 18.9 | 20.2 | % from unrounded |
| Stray hold / FY 2016-17 YTD (Apr-Feb 2017) [Monthly average, year to date] | 739 | 738 | rounding (parts) |
| Stray hold / FY 2017-18 YTD (Apr-Feb 2018) [Monthly average, year to date] | 706 | 706 | match |
| Stray hold / % change | -4.5 | -4.5 | match |
| Owner surrender / FY 2016-17 YTD (Apr-Feb 2017) [Monthly average, year to date] | 285 | 285 | match |
| Owner surrender / FY 2017-18 YTD (Apr-Feb 2018) [Monthly average, year to date] | 281 | 281 | match |
| Owner surrender / % change | -1.4 | 1.4 | % reversed |
| In shelter custody / FY 2016-17 YTD (Apr-Feb 2017) [Monthly average, year to date] | 1024 | 1024 | match |
| In shelter custody / FY 2017-18 YTD (Apr-Feb 2018) [Monthly average, year to date] | 987 | 987 | match |
| In shelter custody / % change | -3.6 | -3.6 | match |
| Other / FY 2016-17 YTD (Apr-Feb 2017) [Monthly average, year to date] | 12 | 12 | match |
| Other / FY 2017-18 YTD (Apr-Feb 2018) [Monthly average, year to date] | 16 | 17 | real difference |
| Other / % change | 33.3 | 41.7 | real difference |
| Total / FY 2016-17 YTD (Apr-Feb 2017) [Monthly average, year to date] | 1089 | 1089 | match |
| Total / FY 2017-18 YTD (Apr-Feb 2018) [Monthly average, year to date] | 1066 | 1066 | match |
| Total / % change | -2.1 | -2.1 | match |

**Draft reply (not sent):**

```
Thanks for the review. 5 of 18 cells differ; here is why:
- Public assist / % change: yours 20.2, mine 18.9. Your % uses the unrounded averages; mine uses the numbers shown in the table.
- Stray hold / FY 2016-17 YTD (Apr-Feb 2017) [Monthly average, year to date]: yours 738, mine 739. You rounded this part on its own; I adjusted the parts so they add up to the rounded total.
- Owner surrender / % change: yours 1.4, mine -1.4. Your % divides by the current year; it should divide by the previous year.
- Other / FY 2017-18 YTD (Apr-Feb 2018) [Monthly average, year to date]: yours 17, mine 16. This is not a rounding effect. Let's compare definitions and filters.
- Other / % change: yours 41.7, mine 33.3. This is not a rounding effect. Let's compare definitions and filters.
2 difference(s) need a closer look; the rest come from the rounding rules.
```

## Data quality handled by the models

- duplicate intake rows removed: 27
- stays closed at the next intake (no outcome recorded): 29
- outcomes with no matching intake (animal arrived before the data starts): 1,361
- stays open more than 180 days at the data cut: 311

## Checks: 12 of 12 passed

- All checks passed. The report can go to QA.
