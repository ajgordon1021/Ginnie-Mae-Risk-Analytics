-- Drop tables if they exist
IF OBJECT_ID('non_level_payments', 'U') IS NOT NULL DROP TABLE non_level_payments;
IF OBJECT_ID('pool_loans', 'U') IS NOT NULL DROP TABLE pool_loans;
IF OBJECT_ID('issuers', 'U') IS NOT NULL DROP TABLE issuers;
IF OBJECT_ID('economic_indicators', 'U') IS NOT NULL DROP TABLE economic_indicators;

-- Issuers
CREATE TABLE issuers (
    issuer_number INT PRIMARY KEY,
    issuer_name VARCHAR(40),
    issuer_address_1 VARCHAR(30),
    issuer_address_2 VARCHAR(30),
    issuer_city VARCHAR(30),
    issuer_state VARCHAR(2),
    issuer_zip_1 VARCHAR(5),
    issuer_zip_2 VARCHAR(4)
);

-- Combined Pool + Loan
CREATE TABLE pool_loans (
    cusip VARCHAR(9),
    pool_number VARCHAR(6),
    pool_indicator VARCHAR(1),
    pool_type VARCHAR(2),
    security_interest_rate DECIMAL(5,3),
    pool_issue_date DATE,
    pool_maturity_date DATE,
    original_aggregate_amount DECIMAL(15,2),
    issuer_number INT REFERENCES issuers(issuer_number),
    pool_upb DECIMAL(14,2),
    num_loans_in_pool INT,
    num_loans_30d_dq INT,
    upb_30d_dq DECIMAL(14,2),
    pct_upb_30d_dq DECIMAL(5,2),
    num_loans_60d_dq INT,
    upb_60d_dq DECIMAL(14,2),
    pct_upb_60d_dq DECIMAL(5,2),
    num_loans_90plus_dq INT,
    upb_90plus_dq DECIMAL(14,2),
    pct_upb_90plus_dq DECIMAL(5,2),
    security_rpb DECIMAL(14,2),
    rpb_factor DECIMAL(10,8),
    project_loan_security_rate DECIMAL(5,3),
    estimated_mortgage_amount DECIMAL(14,2),
    disclosure_seq_number BIGINT,
    case_number VARCHAR(15),
    agency_type VARCHAR(1),
    loan_type VARCHAR(3),
    loan_term INT,
    first_payment_date DATE,
    loan_maturity_date DATE,
    loan_interest_rate DECIMAL(5,3),
    modified_loan_indicator VARCHAR(1),
    non_level_payments_indicator VARCHAR(1),
    mature_loan_cert_flag VARCHAR(1),
    loan_origination_date DATE,
    initial_endorsement_date DATE,
    final_endorsement_date DATE,
    lockout_term INT,
    lockout_period_end_date DATE,
    prepayment_premium_period INT,
    prepayment_end_date DATE,
    interest_approval_date DATE,
    prepayment_penalty_flag VARCHAR(1),
    original_principal_balance DECIMAL(12,2),
    upb_at_issuance DECIMAL(12,2),
    unpaid_principal_balance DECIMAL(12,2),
    draw_number VARCHAR(2),
    approved_draw_amount DECIMAL(13,2),
    months_delinquent INT,
    current_month_liquidation VARCHAR(1),
    removal_reason INT,
    seller_issuer_id INT,
    property_name NVARCHAR(MAX),
    property_street NVARCHAR(MAX),
    property_city VARCHAR(30),
    property_state VARCHAR(2),
    property_zip VARCHAR(9),
    msa VARCHAR(5),
    number_of_units INT,
    current_pi_amount DECIMAL(12,2),
    prepayment_description NVARCHAR(MAX),
    nlp_adjustment_description NVARCHAR(MAX),
    fha_program_section_code NVARCHAR(MAX),
    insurance_type VARCHAR(1),
    as_of_date VARCHAR(6),
    green_status VARCHAR(3),
    affordable_status VARCHAR(3),
    PRIMARY KEY (cusip, as_of_date)
);

-- Non-Level Payment records
CREATE TABLE non_level_payments (
    id INT IDENTITY(1,1) PRIMARY KEY,
    cusip VARCHAR(9),
    pool_number VARCHAR(6),
    pool_indicator VARCHAR(1),
    pool_type VARCHAR(2),
    disclosure_seq_number BIGINT,
    effective_date DATE,
    security_interest_rate DECIMAL(5,3),
    mortgage_interest_rate DECIMAL(5,3),
    principal_and_interest DECIMAL(12,2)
);

-- Economic indicators
CREATE TABLE economic_indicators (
    id INT IDENTITY(1,1) PRIMARY KEY,
    report_date DATE,
    state VARCHAR(2),
    unemployment_rate DECIMAL(5,2),
    hpi_index DECIMAL(10,2),
    mortgage_rate_30yr DECIMAL(5,3)
);

-- Indexes
CREATE INDEX idx_pool_loans_issuer ON pool_loans(issuer_number);
CREATE INDEX idx_pool_loans_pool_type ON pool_loans(pool_type);
CREATE INDEX idx_pool_loans_property_state ON pool_loans(property_state);
CREATE INDEX idx_pool_loans_months_dq ON pool_loans(months_delinquent);
CREATE INDEX idx_pool_loans_as_of ON pool_loans(as_of_date);
CREATE INDEX idx_nlp_cusip ON non_level_payments(cusip);