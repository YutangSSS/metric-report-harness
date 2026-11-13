# metric-report-harness

Ten recurring reporting requests from public-sector analytics work, rebuilt on public data as one small
system: **Spec → Runner → Verifier → Report**. Code computes every number, a verifier re-checks every table
from the numbers it actually shows, and a report ships only when every check passes.

```
specs/*.yaml ──► runner ──► metrics.py (SQL, DuckDB) ──► rounding rules ──► Table + claims
   (the request,                                                             │
    parameters,                                                              ▼
    tables)                                                          verifier (the gate)
                                                                             │ all checks pass?
                                                                             ▼
                                                     out/<spec>/report.md, table_N.csv, list CSVs, checks.csv
```

All 10 reports run in about 0.5 seconds on a laptop (`harness run-all`, 3 runs, 0.52 s each, M-series Mac).

## Why it exists

The work these requests come from was done by hand: about ten SQL queries per quarter, each with five date
parameters edited manually, then a QA reviewer re-adding the tables with a calculator. Most review rounds were
about rounding, mislabelled periods and lists that didn't add up to their summaries, not about the SQL.
This repo turns each of those failure modes into a rule that code enforces.

The original data is confidential, so everything here runs on the **Austin Animal Center intakes and outcomes**
dataset (80,187 intakes, Oct 2013 to Mar 2018), mirrored on Hugging Face
([jason1966/aaronschlegel_austin-animal-center-shelter-intakes-and-outcomes](https://huggingface.co/datasets/jason1966/aaronschlegel_austin-animal-center-shelter-intakes-and-outcomes),
originally City of Austin open data via Kaggle). It has the same shape as caseload data: intakes, closures,
stays that are open on a date, repeat intakes, region types and a status at intake.

| Casework concept | Stand-in here |
|---|---|
| Intake / file opened | Intake event |
| File closed, closure reason | Outcome, outcome type |
| Open on an as-of date | In care at the end of a day or month |
| Region types | City of Austin / Rest of Travis County / Outside jurisdiction |
| Legal authority | Custody group: public assist / stray hold / owner surrender / other |
| Service delivery type | Animal type |
| Recurrence | Repeat intake of the same animal |

## The ten examples

Each spec in `specs/` carries the request as it would arrive, and the general pattern it stands for.

| # | Request pattern | What the gate enforces |
|---|---|---|
| 01 | Quarterly placemat: ~10 tables, five hand-edited date parameters each | One parameter (`quarter`) drives all periods; parts add up to totals; % change from shown numbers |
| 02 | Monthly averages by legal-authority-style category, subtotal, % change | Subtotal and total both tie after rounding; stock metric averaged over month ends |
| 03 | QA reviewer sends back mismatches | Each mismatched cell gets a cause: parts rounded alone, % from unrounded, % reversed, or real difference; reply drafted from the table |
| 04 | Ad hoc extraction, 3 years + YTD, ongoing as of a date, deceased flag | List rows equal summary counts; every "ongoing" row satisfies the as-of rule |
| 05 | "Update this chart through the latest year" | A partial last year is shown as YTD and noted, or the run fails in strict mode |
| 06 | Monthly summary with filters | Months with zero records appear as 0, not dropped |
| 07 | Add a list view to the summary | The list adds up to the summary, month by month |
| 08 | Monthly list for a partner team; a rerun returns one fewer record | Each run is saved; a rerun names every record that came or went and the field that changed |
| 09 | Point-in-time tables of distinct individuals | Nobody counted twice; rows and columns both add up |
| 10 | Executive two-year comparison | Same months and scope both years; every figure labelled total, monthly average or YTD |

Sample output for every example is in [`docs/sample-reports/`](docs/sample-reports/).

## House rules (decided once, applied everywhere)

- **Half-open periods.** `start <= t < end`. "In care on date D" means intake before the end of D and no outcome before the end of D.
- **Fiscal year April to March**, labelled `2017-18`. A period that runs past the last complete month is only allowed when labelled YTD, and YTD is compared with the same months of the earlier year.
- **Round half up** (2.5 → 3), like Excel. Python's `round()` rounds 2.5 to 2.
- **Shown numbers add up.** Totals are rounded honestly; parts are adjusted by largest remainder so they sum to the shown total.
- **% change from shown numbers**, divided by the earlier period; `n/a` when the earlier value is 0.
- **Zero-fill.** Every category and month is listed, including zeros.
- **Every source problem is counted, never dropped silently.** Each report lists them:

  - 27 duplicate intake rows (same animal, same minute) are counted once.
  - 29 stays have no outcome before the next intake; they are closed at that intake as "Not recorded".
  - 1,361 outcomes have no intake, because those animals arrived before the data starts.
  - 311 stays have been open more than 180 days at the data cut.

  The verifier found the duplicate-intake problem on the first run: one animal was counted twice in the point-in-time table.

## Tests

`uv run pytest` runs 35 tests in about 1.5 seconds:

- **Rules** on hand-checked inputs, including a 7-row dataset built around boundary cases: an animal arriving at 23:59 on the last day of a month, an outcome at exactly midnight, a duplicate row and a missing outcome.
- **Gate tests** prove the verifier rejects bad tables: parts that don't add up, a reversed % change, an unlabelled partial year.
- **All ten examples** pass every check on the real data.
- **An independent recount** (`tests/oracle.py`) recomputes intakes and in-care counts in plain Python from the raw CSVs, with no SQL. It must agree with the harness.
- **Drift**: one test back-dates an adoption after the first run and checks that the rerun names that animal and the changed field.

Deliberately breaking the in-care rule (`>=` to `>`) fails 3 tests, and removing the deduplication fails 2.

## Run it

```bash
uv sync
uv run python scripts/fetch_data.py                          # pinned revision, SHA-256 checked
uv run pytest -q
uv run harness run-all                                       # all 10 -> out/
uv run harness run specs/01_quarterly_placemat.yaml --set quarter="2017-18 Q2"
```

CI (GitHub Actions) does the same on every push and uploads the reports.

## Reading order (to know it line by line)

1. `harness/periods.py`: fiscal periods and the one-parameter placemat
2. `harness/rounding.py`: half-up, largest remainder, % change from shown numbers
3. `models/*.sql`: raw → staging → `fct_stays` (the pairing rule)
4. `harness/metrics.py`: every metric's SQL and its one-sentence definition
5. `harness/reports.py`: one builder per request type, each writing claims
6. `harness/verifier.py`: the gate
7. `harness/compare.py` and `harness/drift.py`: reviewer replies and rerun drift
8. `tests/oracle.py`, then `tests/test_examples.py`

## Next

- An agent layer: turn a request email into a spec, ask for any missing rule, and answer only through these tools.
- A dbt port of `models/` with schema tests.
- A Power BI model on `fct_stays`, with drill-through to the list views.
