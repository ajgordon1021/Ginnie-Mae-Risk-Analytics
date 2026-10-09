SELECT state_code,
        ROUND(AVG(t2.loan_age_months)) As Average_loan_seasoning,
        Round(AVG(t2.unpaid_principal_balance),2) As Average_UPB,
        SUM(t2.unpaid_principal_balance) AS Total_UPB,
        ROUND(AVG(t.loan_interest_rate),2) AS Average_interest_rate,
        ROUND(AVG(CASE WHEN t.credit_score <>'NaN'THEN CAST(t.credit_score AS NUMERIC) ELSE NULL END)) AS Average_credit_Score,
        SUM(CASE WHEN t2.months_delinquent = 0 THEN 1 ELSE 0 END) AS Current_Loans,
        SUM(CASE WHEN t2.months_delinquent <> 0 THEN 1 ELSE 0 END) AS Delinquent_Loans,
        ROUND(SUM(CASE WHEN t2.months_delinquent <> 0 THEN 1 ELSE 0 END)::NUMERIC/COUNT(t2.*)::NUMERIC*100,2) As Delinquency_PCT,
        t2.report_date AS Reporting_Date
FROM gnma_static_table t
LEFT JOIN mbs_loans_monthly t2 ON t2.disclosure_sequence_number = t.disclosure_sequence_number
GROUP BY t.state_code, t2.report_date