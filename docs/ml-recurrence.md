# Recurrence model: return within 180 days of leaving care

Rows: closed stays ending in adoption or return to owner, with the full 180-day window before the data cut (2018-03-29). Train on FY 2014-15 and 2015-16 (21,514 stays, 10.2% returned); test on FY 2016-17 (11,524 stays, 11.3% returned).

| Model | AUC | Brier score | Return rate in top 10% |
|---|---:|---:|---:|
| base rate (train) | 0.500 | 0.1001 | 11.1% |
| logistic regression | 0.653 | 0.0975 | 22.2% |
| gradient boosting | 0.662 | 0.0967 | 21.0% |

Calibration of gradient boosting on the test year (5 equal-size bins):

| Mean predicted | Observed | Stays |
|---:|---:|---:|
| 4.3% | 4.3% | 2,305 |
| 7.3% | 6.6% | 2,305 |
| 9.5% | 11.4% | 2,305 |
| 11.6% | 13.8% | 2,305 |
| 19.3% | 20.1% | 2,304 |

Lower Brier is better; the base rate row is the bar to beat. AUC says how well the model ranks; calibration says whether a predicted 20% really means 20%.
Features: animal type, intake type and condition, outcome type, region type, log days in care, prior intakes, outcome month. No feature uses information from after the outcome date.
