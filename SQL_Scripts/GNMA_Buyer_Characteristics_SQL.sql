SELECT 
CASE WHEN first_time_home_buyer = 'NaN' Then 'Repeat Buyer' WHEN first_time_home_buyer = 'N' Then 'Repeat Buyer' WHEN first_time_home_buyer = 'Y' Then 'First Time Buyer' END AS New_Buyer,
CASE WHEN down_payment_assistance = 'NaN' Then 'No Assistance' When down_payment_assistance = 'N' Then 'No Assistance' WHEN down_payment_assistance = 'Y' Then 'Received Assistance' END AS Assistance,
CASE WHEN agency = 'F' Then 'FHA' WHEN agency = 'V' Then 'VA' WHEN agency = 'R' Then 'RD' ELSE agency END AS Insurer,
COUNT(*) AS Total_Loans,
ROUND(AVG(loan_interest_rate::NUMERIC),2) AS Average_Interest_Rate,
ROUND(AVG(CASE WHEN credit_score <>'NaN'THEN CAST(credit_score AS NUMERIC) ELSE NULL END)) AS Average_credit_Score 
FROM gnma_static_table
GROUP BY CASE WHEN first_time_home_buyer = 'NaN' Then 'Repeat Buyer' WHEN first_time_home_buyer = 'N' Then 'Repeat Buyer' WHEN first_time_home_buyer = 'Y' Then 'First Time Buyer' END, CASE WHEN down_payment_assistance = 'NaN' Then 'No Assistance' When down_payment_assistance = 'N' Then 'No Assistance' WHEN down_payment_assistance = 'Y' Then 'Received Assistance' END, CASE WHEN agency = 'F' Then 'FHA' WHEN agency = 'V' Then 'VA' WHEN agency = 'R' Then 'RD' ELSE agency END