-- Overall Concentration Risk

SELECT 
    i.issuer_name,
    COUNT(*) as pool_count,
    SUM(p.unpaid_principal_balance) as total_upb,
    ROUND(SUM(p.unpaid_principal_balance) / 
        (SELECT SUM(unpaid_principal_balance) FROM pool_loans) * 100, 2) as pct_of_total_upb
FROM pool_loans p
JOIN issuers i ON p.issuer_number = i.issuer_number
GROUP BY i.issuer_name
ORDER BY total_upb DESC
LIMIT 15;


-- Geographic Concentration Risk

SELECT 
    property_state,
    COUNT(*) as loan_count,
    SUM(unpaid_principal_balance) as total_upb,
    ROUND(SUM(unpaid_principal_balance) / 
        (SELECT SUM(unpaid_principal_balance) FROM pool_loans) * 100, 2) as pct_of_total_upb,
    SUM(CASE WHEN months_delinquent > 0 THEN 1 ELSE 0 END) as delinquent_loans,
    ROUND(SUM(CASE WHEN months_delinquent > 0 THEN 1 ELSE 0 END)::DECIMAL / 
        COUNT(*) * 100, 2) as delinquency_rate
FROM pool_loans
GROUP BY property_state
ORDER BY total_upb DESC
LIMIT 15;


-- Overall Delinquency Risk

SELECT
    CASE 
        WHEN months_delinquent = 0 THEN 'Current'
        WHEN months_delinquent = 1 THEN '30 Days'
        WHEN months_delinquent = 2 THEN '60 Days'
        WHEN months_delinquent = 3 THEN '90 Days'
        WHEN months_delinquent >= 4 THEN '120+ Days'
        ELSE 'Unknown'
    END as delinquency_bucket,
    COUNT(*) as loan_count,
    SUM(unpaid_principal_balance) as total_upb,
    ROUND(SUM(unpaid_principal_balance) / 
        (SELECT SUM(unpaid_principal_balance) FROM pool_loans) * 100, 2) as pct_of_upb
FROM pool_loans
GROUP BY 
    CASE 
        WHEN months_delinquent = 0 THEN 'Current'
        WHEN months_delinquent = 1 THEN '30 Days'
        WHEN months_delinquent = 2 THEN '60 Days'
        WHEN months_delinquent = 3 THEN '90 Days'
        WHEN months_delinquent >= 4 THEN '120+ Days'
        ELSE 'Unknown'
    END
ORDER BY MIN(months_delinquent);
    END;


-- Issuer Level Delinquency Risk

SELECT 
    i.issuer_name,
    COUNT(*) as pool_count,
    SUM(p.unpaid_principal_balance) as total_upb,
    SUM(CASE WHEN p.months_delinquent > 0 THEN 1 ELSE 0 END) as delinquent_loans,
    ROUND(SUM(CASE WHEN p.months_delinquent > 0 THEN 1 ELSE 0 END)::DECIMAL / 
        COUNT(*) * 100, 2) as delinquency_rate,
    SUM(CASE WHEN p.months_delinquent >= 3 THEN p.unpaid_principal_balance ELSE 0 END) as serious_dq_upb
FROM pool_loans p
JOIN issuers i ON p.issuer_number = i.issuer_number
GROUP BY i.issuer_name
HAVING COUNT(*) >= 10
ORDER BY delinquency_rate DESC
LIMIT 15;


-- Issuer Geographic Risk

SELECT 
    i.issuer_name,
    p.property_state as top_state,
    COUNT(*) as loans_in_state,
    SUM(p.unpaid_principal_balance) as state_upb,
    ROUND(COUNT(*)::DECIMAL / 
        (SELECT COUNT(*) FROM pool_loans p2 WHERE p2.issuer_number = p.issuer_number) * 100, 2) 
        as pct_of_issuer_portfolio
FROM pool_loans p
JOIN issuers i ON p.issuer_number = i.issuer_number
GROUP BY i.issuer_name, p.property_state, p.issuer_number
HAVING COUNT(*) >= 5
ORDER BY pct_of_issuer_portfolio DESC
LIMIT 20;


-- Pool Type Concentration

SELECT 
    pool_type,
    COUNT(*) as pool_count,
    SUM(unpaid_principal_balance) as total_upb,
    ROUND(AVG(loan_interest_rate), 3) as avg_interest_rate,
    ROUND(AVG(EXTRACT(YEAR FROM AGE(loan_maturity_date, first_payment_date))), 1) as avg_term_years,
    SUM(CASE WHEN months_delinquent > 0 THEN 1 ELSE 0 END) as delinquent_count
FROM pool_loans
GROUP BY pool_type
ORDER BY total_upb DESC;


-- Upcoming Maturities

SELECT 
    i.issuer_name,
    p.pool_number,
    p.property_name,
    p.property_state,
    p.loan_maturity_date,
    p.unpaid_principal_balance,
    p.months_delinquent
FROM pool_loans p
JOIN issuers i ON p.issuer_number = i.issuer_number
WHERE p.loan_maturity_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '24 months'
ORDER BY p.loan_maturity_date
LIMIT 20;


-- Florida Exposure Example

SELECT 
    'Florida Exposure' as scenario,
    COUNT(*) as total_fl_loans,
    SUM(unpaid_principal_balance) as total_fl_upb,
    ROUND(SUM(unpaid_principal_balance) / 
        (SELECT SUM(unpaid_principal_balance) FROM pool_loans) * 100, 2) as pct_of_portfolio,
    SUM(CASE WHEN months_delinquent > 0 THEN 1 ELSE 0 END) as currently_delinquent,
    ROUND(SUM(unpaid_principal_balance) * 0.15, 2) as projected_loss_15pct_severity,
    ROUND(SUM(unpaid_principal_balance) * 0.25, 2) as projected_loss_25pct_severity
FROM pool_loans
WHERE property_state = 'FL';