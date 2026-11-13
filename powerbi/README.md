# Power BI semantic model

A star schema and a Power BI semantic model (TMDL text files) over the same data the harness reports on.

```
                 dim_date (fiscal Apr-Mar, complete-month flag)
                /      |  (intake_date: active, outcome_date: inactive)
fct_in_care_monthly    fct_stays ──── dim_region, dim_animal_type, dim_custody, dim_intake_type
  (one row per stay per month end in care)
```

## Build the data

```bash
uv run python -m harness.export        # writes powerbi/data/*.csv (7 tables, about 14 MB)
```

## Open it

The model is a Power BI Project semantic model (`ShelterReporting.SemanticModel/`), stored as TMDL so every
measure and relationship can be read and reviewed in Git. Power BI Desktop runs on Windows only:

1. Copy the repo and `powerbi/data/` to the Windows machine.
2. In Power BI Desktop, turn on *Options > Preview features > Power BI Project (.pbip) save option* and *TMDL format*.
3. Create a new report, save it as a .pbip, then replace its `.SemanticModel/definition` folder with this one
   (or open this folder with Tabular Editor and deploy).
4. Set the `DataFolder` parameter to the folder holding the CSVs, and refresh.

**Not tested in Power BI Desktop.** This Mac has no Power BI Desktop. What is tested (`tests/test_export.py`,
`tests/test_powerbi_model.py`):

- The exported tables reproduce the harness numbers for intakes, stays closed, and monthly average in care.
- Every column the model reads, relates or uses in a measure exists in the CSVs.
- Every measure the model references is defined.

The first refresh in Desktop is the real test of the TMDL syntax and the Power Query steps.

## Measures

| Measure | DAX idea | Why it is written this way |
|---|---|---|
| Intakes | `COUNTROWS(fct_stays)` | Active relationship on intake date |
| Stays Closed | `USERELATIONSHIP(outcome_date, date)` | Same fact, second date role, no duplicate table |
| Intakes per Month | `DIVIDE(Intakes, Months in Context)` | Divides by complete months only, so a partial month does not deflate the average |
| In Care at Month End (avg) | `AVERAGEX(months, COALESCE(COUNTROWS(snapshot), 0))` | A stock comes from a snapshot. COALESCE keeps months with 0 in the average; AVERAGEX would otherwise skip a blank month |
| Intakes per Month % Change | `ROUND` both sides, then `DIVIDE` | House rule: % change from the numbers shown |
| Data Through | last complete month | Subtitle on every page |

## Report pages to build

1. **Placemat**: cards for Intakes per Month, Stays Closed, In Care (avg), with % change; matrix by region type; slicers for fiscal year and quarter.
2. **Monthly summary**: matrix of months × intake type with *Show items with no data* on, so empty months show 0 (example 06).
3. **List (drill-through)**: drill through from a month and category to the stay list: animal ID, intake and outcome dates, types and region (example 07). Add a card with the row count so the list visibly ties to the summary cell.
4. **Point in time**: matrix of animal type × region type from `fct_in_care_monthly` for one month end (example 09).
