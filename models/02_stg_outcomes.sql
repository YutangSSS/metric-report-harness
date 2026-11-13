-- One row per outcome event. Rows with no outcome_type are kept and labelled, never dropped silently.
create or replace table stg_outcomes as
select
    row_number() over (order by animal_id, datetime, outcome_type) as outcome_id,
    animal_id,
    datetime                                      as outcome_dt,
    coalesce(outcome_type, 'Unknown')             as outcome_type,
    outcome_subtype,
    outcome_type in ('Died', 'Euthanasia')        as deceased
from raw_outcomes;
