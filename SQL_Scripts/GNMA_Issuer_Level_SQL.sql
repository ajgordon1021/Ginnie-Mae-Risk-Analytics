SELECT t.issuer_id,
        ROUND(AVG(t.loan_age_months)) As Average_loan_seasoning,
        Round(AVG(t.unpaid_principal_balance),2) As Average_UPB,
        SUM(t.unpaid_principal_balance) AS Total_UPB,
        ROUND(AVG(t2.loan_interest_rate),2) AS Average_interest_rate,
        ROUND(AVG(CASE WHEN t2.credit_score <>'NaN'THEN CAST(t2.credit_score AS NUMERIC) ELSE NULL END)) As Average_credit_Score,
        SUM(CASE WHEN t.months_delinquent = 0 THEN 1 ELSE 0 END) AS Current_Loans,
        SUM(CASE WHEN t.months_delinquent <> 0 THEN 1 ELSE 0 END) AS Delinquent_Loans,
        SUM(CASE WHEN t.months_delinquent <> 0 THEN 1 ELSE 0 END)::float/COUNT(*)::float*100 As Delinquency_PCT,
        t.report_date AS Reporting_Date
FROM mbs_loans_monthly t
JOIN gnma_static_table t2 ON t2.disclosure_sequence_number = t.disclosure_sequence_number
GROUP BY t.issuer_id, t.report_date