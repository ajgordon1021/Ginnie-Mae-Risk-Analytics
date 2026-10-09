INSERT INTO sf_state_month (reporting_date, property_state, orig_year, loan_count, dlq30, dlq90)
SELECT TO_Date(lpad(trim(s.monthly_reporting_period), 6, '0'), 'MMYYYY')
       ,s.property_state
       ,CAST(RIGHT(TRIM(s.origination_date), 4) AS INTEGER)
       ,COUNT(*)
       ,SUM(CASE WHEN NULLIF(s.current_loan_delinquency_status,'XX')::smallint >= 1 THEN 1 ELSE 0 END)
       ,SUM(CASE WHEN NULLIF(s.current_loan_delinquency_status,'XX')::smallint >= 3 THEN 1 ELSE 0 END)
FROM fnma_sf_loan_performance s
WHERE s.current_actual_upb::NUMERIC > 0
  AND s.current_loan_delinquency_status IS NOT NULL
  AND s.loan_age::NUMERIC >= 24
GROUP BY 1, 2, 3
ON CONFLICT (reporting_date, property_state, orig_year)
DO UPDATE SET loan_count = sf_state_month.loan_count + EXCLUDED.loan_count,
              dlq30 = sf_state_month.dlq30 + EXCLUDED.dlq30,
              dlq90 = sf_state_month.dlq90 + EXCLUDED.dlq90;
