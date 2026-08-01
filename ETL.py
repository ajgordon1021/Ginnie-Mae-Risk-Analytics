import pandas as pd
import psycopg2
from datetime import datetime


conn = psycopg2.connect(
    host="localhost",
    database="Ginnie_Mae_Concentration_Risk",
    user="katherinezeller"
)
cur = conn.cursor()

# Read the file
filepath = "/Users/katherinezeller/Documents/MF_Data.txt"  # UPDATE THIS PATH

with open(filepath, 'r', encoding='latin-1') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Helper function to parse dates in CCYYMMDD format
def parse_date(val):
    if not val or val.strip() == '':
        return None
    val = val.strip()
    try:
        if len(val) == 8:
            return datetime.strptime(val, '%Y%m%d').date()
        elif len(val) == 6:
            return datetime.strptime(val, '%Y%m').date()
    except:
        return None
    return None

# Helper to parse numeric values
def parse_num(val):
    if not val or val.strip() == '':
        return None
    try:
        return float(val.strip())
    except:
        return None

def parse_int(val):
    if not val or val.strip() == '':
        return None
    try:
        return int(float(val.strip()))
    except:
        return None

def clean_str(val):
    if not val:
        return None
    val = val.strip()
    return val if val else None

# Track unique issuers
issuers_seen = set()
m_count = 0
n_count = 0
errors = 0

for i, line in enumerate(lines):
    line = line.strip()
    fields = line.split('|')
    
    record_type = fields[0]
    
    if record_type == 'M':
        try:
            # Extract issuer info (P9-P16)
            issuer_num = parse_int(fields[9])
            
            if issuer_num and issuer_num not in issuers_seen:
                cur.execute("""
                    INSERT INTO issuers (
                        issuer_number, issuer_name, issuer_address_1,
                        issuer_address_2, issuer_city, issuer_state,
                        issuer_zip_1, issuer_zip_2
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (issuer_number) DO NOTHING
                """, (
                    issuer_num,
                    clean_str(fields[10]),
                    clean_str(fields[11]),
                    clean_str(fields[12]),
                    clean_str(fields[13]),
                    clean_str(fields[14]),
                    clean_str(fields[15]),
                    clean_str(fields[16])
                ))
                issuers_seen.add(issuer_num)
            
            # Insert pool_loan record
            cur.execute("""
                INSERT INTO pool_loans (
                    cusip, pool_number, pool_indicator, pool_type,
                    security_interest_rate, pool_issue_date, pool_maturity_date,
                    original_aggregate_amount, issuer_number, pool_upb,
                    num_loans_in_pool, num_loans_30d_dq, upb_30d_dq,
                    pct_upb_30d_dq, num_loans_60d_dq, upb_60d_dq,
                    pct_upb_60d_dq, num_loans_90plus_dq, upb_90plus_dq,
                    pct_upb_90plus_dq, security_rpb, rpb_factor,
                    project_loan_security_rate, estimated_mortgage_amount,
                    disclosure_seq_number, case_number, agency_type,
                    loan_type, loan_term, first_payment_date,
                    loan_maturity_date, loan_interest_rate,
                    modified_loan_indicator, non_level_payments_indicator,
                    mature_loan_cert_flag, loan_origination_date,
                    initial_endorsement_date, final_endorsement_date,
                    lockout_term, lockout_period_end_date,
                    prepayment_premium_period, prepayment_end_date,
                    interest_approval_date, prepayment_penalty_flag,
                    original_principal_balance, upb_at_issuance,
                    unpaid_principal_balance, draw_number,
                    approved_draw_amount, months_delinquent,
                    current_month_liquidation, removal_reason,
                    seller_issuer_id, property_name, property_street,
                    property_city, property_state, property_zip,
                    msa, number_of_units, current_pi_amount,
                    prepayment_description, nlp_adjustment_description,
                    fha_program_section_code, insurance_type,
                    as_of_date, green_status, affordable_status
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s
                )
                ON CONFLICT (cusip, as_of_date) DO NOTHING
            """, (
                clean_str(fields[1]),          # cusip
                clean_str(fields[2]),          # pool_number
                clean_str(fields[3]),          # pool_indicator
                clean_str(fields[4]),          # pool_type
                parse_num(fields[5]),          # security_interest_rate
                parse_date(fields[6]),         # pool_issue_date
                parse_date(fields[7]),         # pool_maturity_date
                parse_num(fields[8]),          # original_aggregate_amount
                parse_int(fields[9]),          # issuer_number
                parse_num(fields[17]),         # pool_upb
                parse_int(fields[18]),         # num_loans_in_pool
                parse_int(fields[19]),         # num_loans_30d_dq
                parse_num(fields[20]),         # upb_30d_dq
                parse_num(fields[21]),         # pct_upb_30d_dq
                parse_int(fields[22]),         # num_loans_60d_dq
                parse_num(fields[23]),         # upb_60d_dq
                parse_num(fields[24]),         # pct_upb_60d_dq
                parse_int(fields[25]),         # num_loans_90plus_dq
                parse_num(fields[26]),         # upb_90plus_dq
                parse_num(fields[27]),         # pct_upb_90plus_dq
                parse_num(fields[28]),         # security_rpb
                parse_num(fields[29]),         # rpb_factor
                parse_num(fields[30]),         # project_loan_security_rate
                parse_num(fields[31]),         # estimated_mortgage_amount
                parse_int(fields[32]),         # disclosure_seq_number
                clean_str(fields[33]),         # case_number
                clean_str(fields[34]),         # agency_type
                clean_str(fields[35]),         # loan_type
                parse_int(fields[36]),         # loan_term
                parse_date(fields[37]),        # first_payment_date
                parse_date(fields[38]),        # loan_maturity_date
                parse_num(fields[39]),         # loan_interest_rate
                clean_str(fields[40]),         # modified_loan_indicator
                clean_str(fields[41]),         # non_level_payments_indicator
                clean_str(fields[42]),         # mature_loan_cert_flag
                parse_date(fields[43]),        # loan_origination_date
                parse_date(fields[44]),        # initial_endorsement_date
                parse_date(fields[45]),        # final_endorsement_date
                parse_int(fields[46]),         # lockout_term
                parse_date(fields[47]),        # lockout_period_end_date
                parse_int(fields[48]),         # prepayment_premium_period
                parse_date(fields[49]),        # prepayment_end_date
                parse_date(fields[50]),        # interest_approval_date
                clean_str(fields[51]),         # prepayment_penalty_flag
                parse_num(fields[52]),         # original_principal_balance
                parse_num(fields[53]),         # upb_at_issuance
                parse_num(fields[54]),         # unpaid_principal_balance
                clean_str(fields[55]),         # draw_number
                parse_num(fields[56]),         # approved_draw_amount
                parse_int(fields[57]),         # months_delinquent
                clean_str(fields[58]),         # current_month_liquidation
                parse_int(fields[59]),         # removal_reason
                parse_int(fields[60]),         # seller_issuer_id
                clean_str(fields[61]),         # property_name
                clean_str(fields[62]),         # property_street
                clean_str(fields[63]),         # property_city
                clean_str(fields[64]),         # property_state
                clean_str(fields[65]),         # property_zip
                clean_str(fields[66]),         # msa
                parse_int(fields[67]),         # number_of_units
                parse_num(fields[68]),         # current_pi_amount
                clean_str(fields[69]),         # prepayment_description
                clean_str(fields[70]),         # nlp_adjustment_description
                clean_str(fields[71]),         # fha_program_section_code
                clean_str(fields[72]),         # insurance_type
                clean_str(fields[73]),         # as_of_date
                clean_str(fields[74]),         # green_status
                clean_str(fields[75]),         # affordable_status
            ))
            m_count += 1
            
        except Exception as e:
            conn.rollback()
            errors += 1
            if errors <= 5:
                print(f"Error on line {i+1}: {e}")
                print(f"  Fields count: {len(fields)}")
    
    elif record_type == 'N':
        try:
            cur.execute("""
                INSERT INTO non_level_payments (
                    cusip, pool_number, pool_indicator, pool_type,
                    disclosure_seq_number, effective_date,
                    security_interest_rate, mortgage_interest_rate,
                    principal_and_interest
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                clean_str(fields[1]),
                clean_str(fields[2]),
                clean_str(fields[3]),
                clean_str(fields[4]),
                parse_int(fields[5]),
                parse_date(fields[6]),
                parse_num(fields[7]),
                parse_num(fields[8]),
                parse_num(fields[9])
            ))
            n_count += 1
        except Exception as e:
            conn.rollback()
            errors += 1
            if errors <= 5:
                print(f"Error on line {i+1}: {e}")
                print(f"  Fields count: {len(fields)}")

    
    if (i + 1) % 5000 == 0:
        print(f"Processed {i+1} lines...")

conn.commit()
cur.close()
conn.close()

print(f"\nDone!")
print(f"M records loaded: {m_count}")
print(f"N records loaded: {n_count}")
print(f"Unique issuers: {len(issuers_seen)}")
print(f"Errors: {errors}")