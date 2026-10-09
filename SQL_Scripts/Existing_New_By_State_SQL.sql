SELECT CASE WHEN EXISTS (SELECT 1 FROM sf_new_issuance_loan_level t WHERE t.disclosure_sequence_number = t2.disclosure_sequence_number) THEN 'New Issuances' ELSE 'Existing Loans'
END AS loan_type,
COUNT(*) AS Total_Loans,
ROUND(AVG(CASE WHEN t2.loan_interest_rate <>'NaN'THEN CAST(t2.loan_interest_rate AS NUMERIC) ELSE NULL END), 2)AS Average_interest_rate,
ROUND(SUM(CASE WHEN t2.first_time_home_buyer = 'Y' THEN 1 ELSE 0 END)::NUMERIC/COUNT(*),2)  AS Percent_FTHB,
ROUND(SUM(CASE WHEN t2.down_payment_assistance = 'Y' THEN 1 ELSE 0 END)::NUMERIC/COUNT(*),2)  AS Percent_dpa,
t2.state_code
FROM gnma_static_table t2
GROUP BY CASE WHEN EXISTS (SELECT 1 FROM sf_new_issuance_loan_level t WHERE t.disclosure_sequence_number = t2.disclosure_sequence_number) THEN 'New Issuances' ELSE 'Existing Loans'
END, t2.state_code
ORDER BY state_code