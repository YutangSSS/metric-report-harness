-- One row per intake event (an animal can come in more than once).
-- Duplicates removed here are counted in data_quality() so they never disappear silently.
-- region_type plays the role of the "region type" split in a quarterly statistics placemat:
--   City of Austin / Rest of Travis County / Outside jurisdiction.
-- custody_group plays the role of legal authority: who holds responsibility for the animal.
create or replace table stg_intakes as
select
    row_number() over (order by animal_id, datetime, found_location, intake_type) as intake_id,
    animal_id,
    datetime                                   as intake_dt,
    intake_type,
    intake_condition,
    animal_type,
    found_location,
    case
        when found_location = 'Outside Jurisdiction'         then 'Outside jurisdiction'
        when found_location like '%Austin (TX)'
         and found_location not like '%Travis (TX)'          then 'City of Austin'
        else 'Rest of Travis County'
    end                                        as region_type,
    case intake_type
        when 'Stray'              then 'Stray hold'
        when 'Owner Surrender'    then 'Owner surrender'
        when 'Public Assist'      then 'Public assist'
        else 'Other'
    end                                        as custody_group
from raw_intakes
-- Exact duplicate intake events (same animal, same timestamp) are entered twice in the source; count them once.
qualify row_number() over (partition by animal_id, datetime order by found_location, intake_type) = 1;
