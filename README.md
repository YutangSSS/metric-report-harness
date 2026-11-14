# metric-report-harness

Ten recurring reporting requests from public-sector analytics work, rebuilt on public data as one system.
Code computes every number. A verifier re-checks every table from the numbers it actually shows. A model only
reads request emails and writes reply drafts, and code checks both before anything is used.

```
request email ──► agent: model fills a request card ──► code checks it, asks if anything is missing
                                                          │
specs/*.yaml ─────────────────────────────────────────────┤
                                                          ▼
         runner ──► metrics.py (SQL, DuckDB) ──► rounding rules ──► Table + claims ──► verifier (the gate)
                                                                                         │ all checks pass?
                                                                                         ▼
                        report.md, CSVs, checks.csv ──► reply draft (model) ──► grounding check (code)
```

| Part | What it shows | Where |
|---|---|---|
| Reporting harness: Spec → Runner → Verifier → Report | SQL modelling, tested metric definitions, data quality gates | `harness/`, `models/`, `specs/` |
| Request-to-report agent | LLM reads, code computes, eval on 13 emails | `harness/agent/`, `evals/` |
| LLM reply with grounding check | No invented numbers reach a reader | `harness/agent/summary.py` |
| API + Docker | Read-only FastAPI service, container smoke-tested in CI | `harness/api.py`, `Dockerfile` |

All 10 reports run in 0.51 s (`harness run-all`, 3 runs, M-series Mac). `pytest`: 58 tests in about 3 s.

**Start here:** `uv run harness run specs/01_quarterly_placemat.yaml --set quarter="2017-18 Q2"`, then read
`out/01_quarterly_placemat/report.md`. It shows a table computed by code, with the checks proving it adds up.

**Related repos**, each standalone and built on the same data:

| Repo | What it shows |
|---|---|
| [shelter-dbt](https://github.com/YutangSSS/shelter-dbt) | The same models in dbt, with data tests |
| [shelter-powerbi](https://github.com/YutangSSS/shelter-powerbi) | Star schema and Power BI semantic model, with measures checked against these reports |
| [shelter-recurrence-ml](https://github.com/YutangSSS/shelter-recurrence-ml) | Time-split ML with censoring and calibration |

All four repos build the same `fct_stays` and check the same fingerprint, an MD5 over every row and column
(`tests/test_fingerprint.py`).

## Why it exists

The work these requests come from was done by hand: about ten SQL queries per quarter, each with five date
parameters edited manually, then a QA reviewer re-adding the tables with a calculator. Most review rounds were
about rounding, mislabelled periods and lists that didn't add up to their summaries, not about the SQL.
This repo turns each of those failure modes into a rule that code enforces.

The original data is confidential, so everything here runs on the **Austin Animal Center intakes and outcomes**
dataset (80,187 intakes, Oct 2013 to Mar 2018), mirrored on Hugging Face
([jason1966/aaronschlegel_austin-animal-center-shelter-intakes-and-outcomes](https://huggingface.co/datasets/jason1966/aaronschlegel_austin-animal-center-shelter-intakes-and-outcomes),
originally City of Austin open data via Kaggle). It has the same shape as caseload data.

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

| # | Request pattern | What the gate enforces |
|---|---|---|
| 01 | Quarterly placemat: ~10 tables, five hand-edited date parameters each | One parameter (`quarter`) drives all periods; parts add up to totals; % change from shown numbers |
| 02 | Monthly averages by legal-authority-style category, subtotal, % change | Subtotal and total both tie after rounding; stock metric averaged over month ends |
| 03 | QA reviewer sends back mismatches | Each mismatched cell gets a cause; reply drafted from the table |
| 04 | Ad hoc extraction, 3 years + YTD, ongoing as of a date, deceased flag | List rows equal summary counts; every "ongoing" row satisfies the as-of rule |
| 05 | "Update this chart through the latest year" | A partial last year is shown as YTD and noted, or the run fails in strict mode |
| 06 | Monthly summary with filters | Months with zero records appear as 0, not dropped |
| 07 | Add a list view to the summary | The list adds up to the summary, month by month |
| 08 | Monthly list for a partner team; a rerun returns one fewer record | A rerun names every record that came or went and the field that changed |
| 09 | Point-in-time tables of distinct individuals | Nobody counted twice; rows and columns both add up |
| 10 | Executive two-year comparison | Same months and scope both years; every figure labelled total, monthly average or YTD |

Sample output for every example: [`docs/sample-reports/`](docs/sample-reports/).

## House rules (decided once, applied everywhere)

- **Half-open periods.** `start <= t < end`. "In care on date D" means intake before the end of D and no outcome before the end of D.
- **Fiscal year April to March**, labelled `2017-18`. A period running past the last complete month is allowed only when labelled YTD, and YTD is compared with the same months of the earlier year.
- **Round half up** (2.5 → 3), like Excel. Python's `round()` gives 2.
- **Shown numbers add up.** Totals are rounded honestly; parts are adjusted by largest remainder.
- **% change from shown numbers**, divided by the earlier period; `n/a` when the earlier value is 0.
- **Zero-fill.** Every category and month is listed, including zeros.
- **Every source problem is counted, never dropped silently** (listed in every report):

  - 27 duplicate intake rows and 10 duplicate outcome rows are counted once.
  - 29 stays with no outcome before the next intake are closed there as "Not recorded".
  - 1,351 outcomes have no intake, because those animals arrived before the data starts.
  - 311 stays have been open more than 180 days at the data cut.

  The verifier found the duplicate intakes on its first run: one animal was counted twice in a point-in-time table.
  Comparing the dbt port row for row found the duplicate outcomes: row ids depended on which copy survived.

## The agent

`harness ask email.txt --date 2018-01-15` turns a request email into a verified report and a reply draft.
The model has three limits:

- It fills a **request card** (JSON with a fixed schema: request type, metrics, periods, filters and questions). It never writes SQL or produces a number.
- **Code** checks the card. If something the request needs is missing, it returns questions instead of numbers. It then builds a spec from fixed templates and runs the harness.
- The model writes a **reply draft** from a facts sheet. Code rejects the draft if it contains any number not in the facts, or skips a reviewer difference, and falls back to the template reply. Nothing is sent.

Backends: `cli` uses the local `claude` login (no API key); `api` uses the Anthropic SDK with `claude-opus-5-5`
and server-side refusal fallback. Tests use a scripted backend and never call a model.

**Eval** (`uv run python -m harness.agent.evaluate --backend cli`) has 13 synthetic emails: one per example, plus three that must not run:
- a placemat request with no quarter
- an "ongoing list" with no filter or date
- a forecasting question

An email passes only if the spec the agent builds gives exactly the same numbers as the hand-written spec.

| Run | Change | Emails passed | Replies grounded |
|---|---|---:|---:|
| 1 | first version | 12/13 | 9/9 |
| 2 | split blocking questions from follow-ups (reviewer, due date) | 11/13 | 8/8 |
| 3 | tell the model the house rules so it stops asking about them | 13/13 | 10/10 |
| 4 | same as 3, repeat run | 13/13 | 10/10 |

- **Run 1 failure:** the agent refused to start an urgent extraction because the email didn't name the reviewer.
- **Run 2 failures:** it asked what the in-custody subtotal contains and where "to date" ends. The harness already fixes both.

Results per email are in `evals/results/`. Each run took about 4.5 minutes at about 20 seconds per email.

## API and Docker

`uv run --group api uvicorn harness.api:app` serves these endpoints:
- `GET /health`
- `GET /specs`
- `POST /reports/{id}`, which takes parameter overrides
- `POST /ask`, which needs `HARNESS_BACKEND`

The API is read-only and never writes snapshots. CI builds the Docker image, starts it, and checks `/health` and a Q2 placemat run.

## Tests

`uv sync --all-groups && uv run pytest` runs 58 tests:

- **Rules** on hand-checked inputs, including a 7-row dataset of boundary cases.
- **Gate tests** prove the verifier rejects bad tables.
- **All ten examples** pass on the real data. An **independent recount** in plain Python (`tests/oracle.py`) agrees with the harness.
- **Drift:** a back-dated adoption is caught, and the record and field are named.
- **Agent, offline:** a correct card reproduces each golden spec, and a misread quarter fails the eval. An invented number in a reply is rejected.
- **Fingerprint:** `fct_stays` matches the MD5 that the three related repos also check.
- **API** endpoints.

Deliberately breaking the in-care rule (`>=` to `>`) fails 3 tests. Removing the intake deduplication fails 2.

## Run it

```bash
uv sync --all-groups
uv run python scripts/fetch_data.py                          # pinned revision, SHA-256 checked
uv run pytest -q
uv run harness run-all                                       # all 10 -> out/
uv run harness run specs/01_quarterly_placemat.yaml --set quarter="2017-18 Q2"
uv run harness ask my_email.txt --date 2018-01-15            # needs a claude login
```

## Reading order (to know it line by line)

1. `harness/periods.py` and `harness/rounding.py`: the house rules
2. `models/*.sql`: raw → staging → `fct_stays`
3. `harness/metrics.py`: every metric's SQL and definition
4. `harness/reports.py` and `harness/verifier.py`: builders write claims, the gate re-checks them
5. `harness/compare.py` and `harness/drift.py`
6. `harness/agent/card.py` and `harness/agent/summary.py`: where the model is allowed to act, and how it is checked
7. `tests/oracle.py`, `tests/test_examples.py`, `evals/agent_cases.yaml`
