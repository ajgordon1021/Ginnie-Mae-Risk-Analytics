SELECT
"Property State",
ROUND(AVG("Current Interest Rate")::NUMERIC, 2) AS Average_interest_rate,
ROUND(AVG("Loan Age")::NUMERIC) As Average_loan_seasoning,
ROUND(AVG("Borrower Credit Score at Origination")::NUMERIC) AS Average_credit_Score,
SUM(CASE WHEN "Current Loan Delinquency Status" = 0 THEN 1 ELSE 0 END) AS Current_Loans,
SUM(CASE WHEN "Current Loan Delinquency Status" <> 0 THEN 1 ELSE 0 END) AS Delinquent_Loans,
SUM(CASE WHEN "Current Loan Delinquency Status" <> 0 THEN 1 ELSE 0 END)::float/SUM(CASE WHEN "Current Loan Delinquency Status" = 0 THEN 1 ELSE 0 END)::float*100 As Delinquency_PCT,
"Monthly Reporting Period"
FROM fnma_mbs_sf_loans
WHERE "Monthly Reporting Period" = 22026
GROUP BY "Property State", "Monthly Reporting Period"