from datetime import datetime

from db_config import get_connection

# Azure SQL connection
conn = get_connection()
cur = conn.cursor()

# Read the file
filepath = "/Users/katherinezeller/Downloads/mfplmon4_202606.txt"  # UPDATE THIS PATH

with open(filepath, 'r', encoding='latin-1') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

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
            issuer_num = parse_int(fields[9])
            
            if issuer_num and issuer_num not in issuers_seen:
                cur.execute("""
                    IF NOT EXISTS (SELECT 1 FROM issuers WHERE issuer_number = ?)
                    INSERT INTO issuers (
                        issuer_number, issuer_name, issuer_address_1,
                        issuer_address_2, issuer_city, issuer_state,
                        issuer_zip_1, issuer_zip_2
                    ) VALUES (?,?,?,?,?,?,?,?)
                """, (
                    issuer_num,
                    issuer_num,
                    clean_str(fields[10]),
                    clean_str(fields[11]),
                    clean_str(fields[12]),
                    clean_str(fields[13]),
                    clean_str(fields[14]),
                    clean_str(fields[15]),
                    clean_str(fields[16])
                ))
                conn.commit()
                issuers_seen.add(issuer_num)
            
            cur.execute("""
                IF NOT EXISTS (SELECT 1 FROM pool_loans WHERE cusip = ? AND as_of_date = ?)
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
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?
                )
            """, (
                clean_str(fields[1]),           # cusip (for EXISTS check)
                clean_str(fields[73]),          # as_of_date (for EXISTS check)
                clean_str(fields[1]),
                clean_str(fields[2]),
                clean_str(fields[3]),
                clean_str(fields[4]),
                parse_num(fields[5]),
                parse_date(fields[6]),
                parse_date(fields[7]),
                parse_num(fields[8]),
                parse_int(fields[9]),
                parse_num(fields[17]),
                parse_int(fields[18]),
                parse_int(fields[19]),
                parse_num(fields[20]),
                parse_num(fields[21]),
                parse_int(fields[22]),
                parse_num(fields[23]),
                parse_num(fields[24]),
                parse_int(fields[25]),
                parse_num(fields[26]),
                parse_num(fields[27]),
                parse_num(fields[28]),
                parse_num(fields[29]),
                parse_num(fields[30]),
                parse_num(fields[31]),
                parse_int(fields[32]),
                clean_str(fields[33]),
                clean_str(fields[34]),
                clean_str(fields[35]),
                parse_int(fields[36]),
                parse_date(fields[37]),
                parse_date(fields[38]),
                parse_num(fields[39]),
                clean_str(fields[40]),
                clean_str(fields[41]),
                clean_str(fields[42]),
                parse_date(fields[43]),
                parse_date(fields[44]),
                parse_date(fields[45]),
                parse_int(fields[46]),
                parse_date(fields[47]),
                parse_int(fields[48]),
                parse_date(fields[49]),
                parse_date(fields[50]),
                clean_str(fields[51]),
                parse_num(fields[52]),
                parse_num(fields[53]),
                parse_num(fields[54]),
                clean_str(fields[55]),
                parse_num(fields[56]),
                parse_int(fields[57]),
                clean_str(fields[58]),
                parse_int(fields[59]),
                parse_int(fields[60]),
                clean_str(fields[61]),
                clean_str(fields[62]),
                clean_str(fields[63]),
                clean_str(fields[64]),
                clean_str(fields[65]),
                clean_str(fields[66]),
                parse_int(fields[67]),
                parse_num(fields[68]),
                clean_str(fields[69]),
                clean_str(fields[70]),
                clean_str(fields[71]),
                clean_str(fields[72]),
                clean_str(fields[73]),
                clean_str(fields[74]),
                clean_str(fields[75]),
            ))
            conn.commit()
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
                ) VALUES (?,?,?,?,?,?,?,?,?)
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
            conn.commit()
            n_count += 1
        except Exception as e:
            conn.rollback()
            errors += 1
            if errors <= 5:
                print(f"NLP Error on line {i+1}: {e}")

    if (i + 1) % 5000 == 0:
        print(f"Processed {i+1} lines...")

cur.close()
conn.close()

print(f"\nDone!")
print(f"M records loaded: {m_count}")
print(f"N records loaded: {n_count}")
print(f"Unique issuers: {len(issuers_seen)}")
print(f"Errors: {errors}")