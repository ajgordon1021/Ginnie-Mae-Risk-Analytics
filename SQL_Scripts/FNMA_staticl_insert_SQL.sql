INSERT INTO fnma_static_table (loan_identifier, reference_pool_id,seller_name,loan_purpose,origination_date,original_upb,borrower_credit_score_at_origination,
original_ltv,property_state,msa,property_type,number_of_units,occupancy_status,number_of_borrowers,first_time_home_buyer_indicator,dti)
SELECT DISTINCT ON (t.loan_identifier) t.loan_identifier, t.reference_pool_id,t.seller_name,t.loan_purpose,t.origination_date,t.original_upb,t.borrower_credit_score_at_origination,
t.original_ltv,t.property_state,t.msa,t.property_type,t.number_of_units,t.occupancy_status,t.number_of_borrowers,t.first_time_home_buyer_indicator,t.dti FROM fnma_sf_loan_performance t
WHERE NOT EXISTS (SELECT 1 from fnma_static_table t2 WHERE t2.loan_identifier = t.loan_identifier)
ORDER BY t.loan_identifier, to_date(lpad(trim(t.monthly_reporting_period), 6, '0'), 'MMYYYY')
ON CONFLICT (loan_identifier) DO NOTHING;