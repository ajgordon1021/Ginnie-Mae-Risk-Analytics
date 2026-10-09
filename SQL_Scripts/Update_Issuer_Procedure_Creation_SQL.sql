CREATE OR REPLACE PROCEDURE update_issuer_group(p_report_date DATE)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE issuer_info
    SET issuer_group = subquery.calculated_category
    FROM(
        SELECT
        issuer_id,
        COUNT(*) AS loan_count,
        CASE
            WHEN COUNT(*) < 2500 THEN 'Very Small'
            WHEN COUNT(*) < 10000 THEN 'Small'
            WHEN COUNT(*) < 75000 THEN 'Medium'
            WHEN COUNT(*) < 400000 THEN 'Large'
            ELSE 'Mega' END As calculated_category
            FROM mbs_loans_monthly
            WHERE report_date = p_report_date
            GROUP BY issuer_id
    ) subquery
    WHERE issuer_info.issuer_number = subquery.issuer_id;

    RAISE NOTICE 'Issuer categories update for date %', p_report_date;
    END;
    $$;