SELECT
CASE WHEN t.issuer_group = 'Mega' Then 'Mega' ELSE 'Non Mega' END AS Issuer_Group,
SUM(CASE WHEN t2.months_delinquent <> 0 THEN 1 ELSE 0 END) AS Total_Delinquencies,
SUM(CASE WHEN t3.agency = 'F' THEN 1 ELSE 0 END) AS FHA_Loans,
SUM(CASE WHEN t3.agency = 'V' THEN 1 ELSE 0 END) AS VA_Loans,
SUM(CASE WHEN t3.agency = 'R' THEN 1 ELSE 0 END) AS RD_Loans,
SUM(CASE WHEN t3.agency = 'N' THEN 1 ELSE 0 END) AS PIH_Loans,
COUNT(t3.disclosure_sequence_number) AS Total_Loans,
ROUND(SUM(CASE WHEN t3.first_time_home_buyer = 'Y' THEN 1 ELSE 0 END)::NUMERIC/COUNT(t3.disclosure_sequence_number),2)  AS Percent_FTHB,
ROUND(SUM(CASE WHEN t3.down_payment_assistance = 'Y' THEN 1 ELSE 0 END)::NUMERIC/COUNT(t3.disclosure_sequence_number),2)  AS Percent_dpa
FROM gnma_static_table t3
JOIN mbs_loans_monthly t2 ON t2.disclosure_sequence_number = t3.disclosure_sequence_number
LEFT JOIN issuer_info t ON t.issuer_number = t3.issuer_id
GROUP BY CASE WHEN t.issuer_group = 'Mega' Then 'Mega' ELSE 'Non Mega' END