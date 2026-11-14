"""fct_stays fingerprint: an MD5 over every column of every row, in stay_id order.

The sibling repos (shelter-dbt, shelter-powerbi, shelter-recurrence-ml) each rebuild fct_stays on their own
and assert this same fingerprint, so a rule change here that is not made there (or the reverse) fails a test.
If you change a model on purpose, update the value here and in all three repos.
"""
FCT_STAYS_ROWS = 80160
FCT_STAYS_MD5 = "d11c6b0d4adcce4aa79c0bcdeadddbac"


def test_fct_stays_fingerprint(con):
    got = con.execute("""
        select count(*), md5(string_agg(concat_ws('|', stay_id, animal_id, intake_seq, is_repeat_intake, intake_dt,
               intake_type, intake_condition, animal_type, region_type, custody_group, outcome_id, outcome_dt,
               outcome_type, outcome_subtype, deceased, days_in_care), chr(10) order by stay_id))
        from fct_stays""").fetchone()
    assert got == (FCT_STAYS_ROWS, FCT_STAYS_MD5)
