SELECT
t.state_code AS State,
COUNT(t.*) AS State_Loans,
SUM(CASE WHEN t.agency = 'F' THEN 1 ELSE 0 END) AS FHA_Loans,
SUM(CASE WHEN t.agency = 'F' THEN t2.unpaid_principal_balance ELSE 0 END) AS Total_FHA_UPB,
ROUND(SUM(CASE WHEN t.agency = 'F' THEN 1 ELSE 0 END)::NUMERIC/COUNT(*)::NUMERIC * 100, 2) AS Percent_State_FHA,
ROUND(SUM(CASE WHEN t.agency = 'F' THEN t2.unpaid_principal_balance ELSE 0 END)::NUMERIC/SUM(t2.unpaid_principal_balance)::NUMERIC * 100, 2) AS Percent_State_UPB_FHA,
SUM(CASE WHEN t.agency = 'F' AND t2.months_delinquent <> 0 THEN 1 ELSE 0 END) AS Total_FHA_Delinquencies
FROM
gnma_static_table t
LEFT JOIN mbs_loans_monthly t2 ON t2.disclosure_sequence_number = t.disclosure_sequence_number
GROUP BY t.state_code
