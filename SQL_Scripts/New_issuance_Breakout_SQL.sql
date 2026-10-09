SELECT  t.issuer_id || ' - ' || t2.issuer_name AS Issuer_Title,
        COUNT(t.*) AS total_new_issuances,
        ROUND(AVG(CASE WHEN t.original_principal_balance <>'NaN'THEN CAST(t.original_principal_balance AS NUMERIC) ELSE NULL END), 2) As Average_OPB,
        SUM(CASE WHEN t.original_principal_balance <>'NaN'THEN CAST(t.original_principal_balance AS NUMERIC) ELSE NULL END) AS Total_OPB,
        ROUND(AVG(CASE WHEN t.loan_interest_rate <>'NaN'THEN CAST(t.loan_interest_rate AS NUMERIC) ELSE NULL END), 2)AS Average_interest_rate,
        ROUND(AVG(CASE WHEN t.credit_score <>'NaN'THEN CAST(t.credit_score AS NUMERIC) ELSE NULL END)) As Average_credit_Score,
        SUM(CASE WHEN t.agency = 'F' THEN 1 ELSE 0 END) AS New_FHA_Issuances,
        SUM(CASE WHEN t.agency = 'V' THEN 1 ELSE 0 END) AS New_VA_Issuances,
        SUM(CASE WHEN t.agency = 'R' THEN 1 ELSE 0 END) AS New_RD_Issuances,
        SUM(CASE WHEN t.agency = 'N' THEN 1 ELSE 0 END) AS New_PIH_Issuances
FROM sf_new_issuance_loan_level t
JOIN issuer_info t2 ON t.issuer_id = t2.issuer_number
WHERE t.as_of_date = '8/1/2026'
GROUP BY t.issuer_id || ' - ' || t2.issuer_name