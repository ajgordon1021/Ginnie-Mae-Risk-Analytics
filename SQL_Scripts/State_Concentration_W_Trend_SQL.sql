WITH monthly AS (
    SELECT t.state_code,
           t2.report_date AS reporting_date,
           ROUND(AVG(t2.loan_age_months)) AS average_loan_seasoning,
           ROUND(AVG(CASE WHEN t2.unpaid_principal_balance <> 'NaN' THEN CAST(t2.unpaid_principal_balance AS NUMERIC) END), 2) AS average_upb,
           SUM(CASE WHEN t2.unpaid_principal_balance <> 'NaN' THEN CAST(t2.unpaid_principal_balance AS NUMERIC) END) AS total_upb,
           ROUND(AVG(t.loan_interest_rate), 2) AS average_interest_rate,
           ROUND(AVG(CASE WHEN t.credit_score <> 'NaN' THEN CAST(t.credit_score AS NUMERIC) END)) AS average_credit_score,
           SUM(CASE WHEN t2.months_delinquent = 0 THEN 1 ELSE 0 END) AS current_loans,
           SUM(CASE WHEN t2.months_delinquent <> 0 THEN 1 ELSE 0 END) AS delinquent_loans,
           ROUND(SUM(CASE WHEN t2.months_delinquent <> 0 THEN 1 ELSE 0 END)::NUMERIC
                 / COUNT(t2.*)::NUMERIC * 100, 2) AS delinquency_pct,
           COUNT(t4.*) AS total_liquidations,
           ROUND(SUM(CASE WHEN t2.months_delinquent <> 0 AND t3.issuer_group = 'Mega' THEN 1 ELSE 0 END)::NUMERIC / SUM(CASE WHEN t2.months_delinquent <> 0 THEN 1 ELSE 0 END)::NUMERIC,4) AS mega_dq_pct
    FROM gnma_static_table t
    JOIN mbs_loans_monthly t2 ON t2.disclosure_sequence_number = t.disclosure_sequence_number
    JOIN issuer_info t3 ON t3.issuer_number = t.issuer_id
    LEFT JOIN mbs_monthly_liquidations t4 ON t4.disclosure_sequence_number = t.disclosure_sequence_number
                                         AND t4.report_date = '8/1/2026'::DATE
    WHERE t2.report_date IN (DATE '2026-07-01', DATE '2026-08-01')
    GROUP BY t.state_code, t2.report_date
),
trended AS (
    SELECT *,
           LAG(delinquency_pct) OVER (PARTITION BY state_code ORDER BY reporting_date) AS prior_delinquency_pct
    FROM monthly
)
SELECT *,
       delinquency_pct - prior_delinquency_pct AS delinquency_change_pp,
       CASE
           WHEN prior_delinquency_pct IS NULL         THEN 'New'
           WHEN delinquency_pct > prior_delinquency_pct THEN 'Up'
           WHEN delinquency_pct < prior_delinquency_pct THEN 'Down'
           ELSE 'Flat'
       END AS delinquency_trend
FROM trended
WHERE reporting_date = DATE '2026-08-01'
ORDER BY state_code;
