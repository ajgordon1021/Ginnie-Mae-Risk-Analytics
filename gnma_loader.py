"""Load Ginnie Mae single-family monthly disclosure files into the Azure database.

Handles two downloads, as .txt or .zip:
  - loan-level monthly file (llmon_YYYYMM, llmon1_YYYYMM, llmon2_YYYYMM): 'LL' records
    -> gnma_static_table (one row per loan, kept up to date)
    -> mbs_loans_monthly (one row per loan per month)
  - liquidations file (llmonliq_YYYYMM): 'LR' records -> mbs_monthly_liquidations

The report month comes from the YYYYMM in the file name. Every loaded file is
recorded in gnma_load_log, so a file is never loaded twice unless --force is given.

    python gnma_loader.py C:\\Users\\me\\Downloads\\llmon_202609.zip
    python gnma_loader.py --inbox C:\\Users\\me\\Downloads
"""
import argparse
import io
import re
import sys
import time
import zipfile
from datetime import date
from pathlib import Path

from db_config import get_connection

BATCH_SIZE = 50_000

LOAN_FIELDS = [
    'record_type', 'cusip_number', 'pool_id', 'pool_indicator', 'pool_type', 'pool_issue_date',
    'disclosure_sequence_number', 'issuer_id', 'agency', 'loan_purpose', 'refinance_type',
    'first_payment_date', 'maturity_date', 'loan_interest_rate', 'original_principal_balance',
    'upb_at_issuance', 'unpaid_principal_balance', 'original_loan_term', 'loan_age',
    'remaining_loan_term', 'months_delinquent', 'months_pre_paid', 'loan_gross_margin',
    'loan_to_value', 'combined_ltv', 'total_debt_expense_ratio', 'credit_score',
    'down_payment_assistance', 'buy_down_status', 'upfront_mip', 'annual_mip',
    'number_of_borrowers', 'first_time_home_buyer', 'property_type', 'state_code', 'msa',
    'third_party_origination_type', 'current_month_liquidation_flag', 'removal_reason',
    'as_of_date', 'loan_origination_date', 'seller_issuer_id', 'index_type', 'look_back_period',
    'interest_rate_change_date', 'initial_interest_rate_cap', 'subsequent_interest_rate_cap',
    'lifetime_interest_rate_cap', 'next_interest_rate_change_ceiling',
    'lifetime_interest_rate_ceiling', 'lifetime_interest_rate_floor', 'prospective_interest_rate',
    'arm_adjustment_effective_date', 'scheduled_unpaid_principal_balance',
    're_performing_loan_indicator',
]
LIQUIDATION_FIELDS = [
    'record_type', 'cusip_number', 'pool_id', 'pool_indicator', 'pool_type', 'pool_issue_date',
    'disclosure_sequence_number', 'issuer_id', 'report_period', 'agency_type', 'loan_purpose',
    'original_principal_balance', 'unpaid_principal_balance', 'liquidation_balance', 'removal_reason',
]

# Only the fields the analysis tables use are uploaded
STAGED_LOAN_FIELDS = [
    'disclosure_sequence_number', 'issuer_id', 'agency', 'state_code', 'msa',
    'original_principal_balance', 'loan_interest_rate', 'loan_to_value', 'credit_score',
    'loan_origination_date', 'down_payment_assistance', 'first_time_home_buyer', 'seller_issuer_id',
    'unpaid_principal_balance', 'loan_age', 'months_delinquent',
]
STAGED_LIQUIDATION_FIELDS = [
    'disclosure_sequence_number', 'issuer_id', 'cusip_number', 'pool_id', 'agency_type',
    'loan_purpose', 'original_principal_balance', 'unpaid_principal_balance', 'liquidation_balance',
    'removal_reason',
]


def _staging_ddl(table, fields):
    cols = ',\n    '.join(f'{f} VARCHAR(50)' for f in fields)
    return f"IF OBJECT_ID(N'{table}', N'U') IS NULL CREATE TABLE {table} (\n    {cols}\n)"


SCHEMA = [
    _staging_ddl('gnma_staging_loans', STAGED_LOAN_FIELDS),
    _staging_ddl('gnma_staging_liquidations', STAGED_LIQUIDATION_FIELDS),
    """IF OBJECT_ID(N'gnma_static_table', N'U') IS NULL CREATE TABLE gnma_static_table (
    disclosure_sequence_number VARCHAR(20) NOT NULL PRIMARY KEY,
    issuer_id INT,
    state_code VARCHAR(20),
    msa VARCHAR(20),
    original_principal_balance DECIMAL(14,2),
    loan_interest_rate DECIMAL(6,3),
    ltv DECIMAL(7,2),
    credit_score INT,
    loan_origination_date VARCHAR(20),
    down_payment_assistance VARCHAR(20),
    first_time_home_buyer VARCHAR(20),
    seller_issuer_id INT,
    agency VARCHAR(20),
    created_at DATETIME2,
    last_updated DATETIME2
)""",
    """IF OBJECT_ID(N'mbs_loans_monthly', N'U') IS NULL CREATE TABLE mbs_loans_monthly (
    disclosure_sequence_number VARCHAR(20) NOT NULL,
    report_date DATE NOT NULL,
    issuer_id INT,
    unpaid_principal_balance DECIMAL(14,2),
    loan_age_months INT,
    months_delinquent INT,
    delinquency_status VARCHAR(10),
    created_at DATETIME2,
    CONSTRAINT pk_mbs_loans_monthly PRIMARY KEY (report_date, disclosure_sequence_number)
)""",
    """IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_mbs_loans_monthly_dsn')
    CREATE INDEX ix_mbs_loans_monthly_dsn ON mbs_loans_monthly (disclosure_sequence_number)""",
    """IF OBJECT_ID(N'mbs_monthly_liquidations', N'U') IS NULL CREATE TABLE mbs_monthly_liquidations (
    disclosure_sequence_number VARCHAR(20) NOT NULL,
    report_date DATE NOT NULL,
    issuer_id INT,
    cusip_number VARCHAR(20),
    pool_id VARCHAR(20),
    agency_type VARCHAR(20),
    loan_purpose VARCHAR(20),
    original_principal_balance DECIMAL(14,2),
    unpaid_principal_balance DECIMAL(14,2),
    liquidation_balance DECIMAL(14,2),
    removal_reason VARCHAR(20),
    created_at DATETIME2,
    CONSTRAINT pk_mbs_monthly_liquidations PRIMARY KEY (report_date, disclosure_sequence_number)
)""",
    """IF OBJECT_ID(N'gnma_load_log', N'U') IS NULL CREATE TABLE gnma_load_log (
    file_name VARCHAR(260) NOT NULL PRIMARY KEY,
    file_type VARCHAR(20),
    report_date DATE,
    rows_loaded INT,
    loaded_at DATETIME2
)""",
]

# One row per loan from the staging table (a file should not repeat a loan, but don't fail if it does)
_DEDUPED = """(SELECT *, ROW_NUMBER() OVER (PARTITION BY disclosure_sequence_number ORDER BY (SELECT NULL)) AS rn
      FROM {table} WHERE disclosure_sequence_number IS NOT NULL) s
WHERE s.rn = 1"""

LOAN_STATEMENTS = [
    # New loans are added and existing loans refreshed with this month's values
    """MERGE gnma_static_table AS t
USING (
    SELECT s.disclosure_sequence_number,
           TRY_CAST(s.issuer_id AS INT) AS issuer_id,
           s.state_code,
           s.msa,
           TRY_CAST(s.original_principal_balance AS DECIMAL(14,2)) AS original_principal_balance,
           TRY_CAST(s.loan_interest_rate AS DECIMAL(6,3)) AS loan_interest_rate,
           TRY_CAST(s.loan_to_value AS DECIMAL(7,2)) AS ltv,
           TRY_CAST(s.credit_score AS INT) AS credit_score,
           s.loan_origination_date,
           s.down_payment_assistance,
           s.first_time_home_buyer,
           TRY_CAST(s.seller_issuer_id AS INT) AS seller_issuer_id,
           s.agency
    FROM """ + _DEDUPED.format(table='gnma_staging_loans') + """
) AS src
ON t.disclosure_sequence_number = src.disclosure_sequence_number
WHEN MATCHED THEN UPDATE SET
    issuer_id = src.issuer_id,
    state_code = src.state_code,
    msa = src.msa,
    original_principal_balance = src.original_principal_balance,
    loan_interest_rate = src.loan_interest_rate,
    ltv = src.ltv,
    credit_score = src.credit_score,
    loan_origination_date = src.loan_origination_date,
    down_payment_assistance = src.down_payment_assistance,
    first_time_home_buyer = src.first_time_home_buyer,
    seller_issuer_id = src.seller_issuer_id,
    agency = src.agency,
    last_updated = SYSDATETIME()
WHEN NOT MATCHED THEN INSERT (
    disclosure_sequence_number, issuer_id, state_code, msa, original_principal_balance,
    loan_interest_rate, ltv, credit_score, loan_origination_date, down_payment_assistance,
    first_time_home_buyer, seller_issuer_id, agency, created_at, last_updated
) VALUES (
    src.disclosure_sequence_number, src.issuer_id, src.state_code, src.msa, src.original_principal_balance,
    src.loan_interest_rate, src.ltv, src.credit_score, src.loan_origination_date, src.down_payment_assistance,
    src.first_time_home_buyer, src.seller_issuer_id, src.agency, SYSDATETIME(), SYSDATETIME()
);""",
    # Reloading a file replaces that month's rows for its loans
    """DELETE m FROM mbs_loans_monthly m
WHERE m.report_date = ?
  AND EXISTS (SELECT 1 FROM gnma_staging_loans s WHERE s.disclosure_sequence_number = m.disclosure_sequence_number)""",
    """INSERT INTO mbs_loans_monthly (
    disclosure_sequence_number, report_date, issuer_id, unpaid_principal_balance,
    loan_age_months, months_delinquent, delinquency_status, created_at
)
SELECT s.disclosure_sequence_number,
       ?,
       TRY_CAST(s.issuer_id AS INT),
       COALESCE(TRY_CAST(s.unpaid_principal_balance AS DECIMAL(14,2)), 0),
       COALESCE(TRY_CAST(s.loan_age AS INT), 0),
       COALESCE(TRY_CAST(s.months_delinquent AS INT), 0),
       CASE WHEN TRY_CAST(s.months_delinquent AS INT) = 0 THEN 'Current' ELSE 'Delinquent' END,
       SYSDATETIME()
FROM """ + _DEDUPED.format(table='gnma_staging_loans'),
]

LIQUIDATION_STATEMENTS = [
    """DELETE l FROM mbs_monthly_liquidations l
WHERE l.report_date = ?
  AND EXISTS (SELECT 1 FROM gnma_staging_liquidations s WHERE s.disclosure_sequence_number = l.disclosure_sequence_number)""",
    """INSERT INTO mbs_monthly_liquidations (
    disclosure_sequence_number, report_date, issuer_id, cusip_number, pool_id, agency_type,
    loan_purpose, original_principal_balance, unpaid_principal_balance, liquidation_balance,
    removal_reason, created_at
)
SELECT s.disclosure_sequence_number,
       ?,
       TRY_CAST(s.issuer_id AS INT),
       s.cusip_number,
       s.pool_id,
       s.agency_type,
       s.loan_purpose,
       TRY_CAST(s.original_principal_balance AS DECIMAL(14,2)),
       TRY_CAST(s.unpaid_principal_balance AS DECIMAL(14,2)),
       TRY_CAST(s.liquidation_balance AS DECIMAL(14,2)),
       s.removal_reason,
       SYSDATETIME()
FROM """ + _DEDUPED.format(table='gnma_staging_liquidations'),
]

# Same size bands as the old Postgres update_issuer_group procedure
ISSUER_GROUP_UPDATE = """UPDATE i SET issuer_group = s.issuer_group
FROM issuer_info i
JOIN (
    SELECT issuer_id,
           CASE WHEN COUNT(*) < 2500 THEN 'Very Small'
                WHEN COUNT(*) < 10000 THEN 'Small'
                WHEN COUNT(*) < 75000 THEN 'Medium'
                WHEN COUNT(*) < 400000 THEN 'Large'
                ELSE 'Mega' END AS issuer_group
    FROM mbs_loans_monthly
    WHERE report_date = ?
    GROUP BY issuer_id
) s ON i.issuer_number = s.issuer_id"""

FILE_TYPES = {
    # name pattern, record prefix, all fields in the record, fields uploaded, staging table, statements
    'loans': (re.compile(r'^llmon\d?_(\d{6})', re.I), 'LL', LOAN_FIELDS, STAGED_LOAN_FIELDS,
              'gnma_staging_loans', LOAN_STATEMENTS),
    'liquidations': (re.compile(r'^llmonliq\d?_(\d{6})', re.I), 'LR', LIQUIDATION_FIELDS,
                     STAGED_LIQUIDATION_FIELDS, 'gnma_staging_liquidations', LIQUIDATION_STATEMENTS),
}


def classify(path):
    """Return (file type, report date) for a Ginnie Mae file name, or (None, None)."""
    for file_type, (pattern, *_rest) in FILE_TYPES.items():
        m = pattern.match(Path(path).name)
        if m:
            yyyymm = m.group(1)
            return file_type, date(int(yyyymm[:4]), int(yyyymm[4:]), 1)
    return None, None


def open_text(path):
    path = Path(path)
    if path.suffix.lower() != '.zip':
        return open(path, encoding='latin-1')
    z = zipfile.ZipFile(path)
    members = [m for m in z.infolist() if not m.is_dir()]
    if not members:
        raise ValueError(f'{path.name} is an empty zip file')
    biggest = max(members, key=lambda m: m.file_size)
    return io.TextIOWrapper(z.open(biggest), encoding='latin-1')


def read_records(path, prefix, fields, keep):
    """Yield the kept fields of every record starting with prefix; blanks become None."""
    idx = [fields.index(f) for f in keep]
    with open_text(path) as f:
        for line_no, line in enumerate(f, start=1):
            if not line.startswith(prefix):
                continue
            parts = line.rstrip('\r\n').split('|')
            if len(parts) != len(fields):
                raise ValueError(f'Line {line_no} has {len(parts)} fields, expected {len(fields)}. '
                                 'The Ginnie Mae file layout may have changed.')
            yield tuple(parts[i].strip() or None for i in idx)


def stage(conn, table, fields, records):
    cur = conn.cursor()
    cur.execute(f'TRUNCATE TABLE {table}')
    conn.commit()
    cur.fast_executemany = True
    sql = f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({', '.join('?' * len(fields))})"

    total, batch, start = 0, [], time.time()
    for rec in records:
        batch.append(rec)
        if len(batch) >= BATCH_SIZE:
            cur.executemany(sql, batch)
            conn.commit()
            total += len(batch)
            batch = []
            print(f'  uploaded {total:,} rows ({total / (time.time() - start):,.0f}/sec)', flush=True)
    if batch:
        cur.executemany(sql, batch)
        conn.commit()
        total += len(batch)
    cur.close()
    return total


def ensure_schema(conn):
    cur = conn.cursor()
    for stmt in SCHEMA:
        cur.execute(stmt)
    conn.commit()
    cur.close()


def already_loaded(conn, file_name):
    cur = conn.cursor()
    row = cur.execute('SELECT loaded_at FROM gnma_load_log WHERE file_name = ?', file_name).fetchone()
    cur.close()
    return row[0] if row else None


def load_file(conn, path, report_date=None, force=False):
    path = Path(path)
    file_type, file_date = classify(path)
    if file_type is None:
        raise ValueError(f'{path.name} is not a recognised Ginnie Mae file (expected llmon*_YYYYMM or llmonliq*_YYYYMM)')
    report_date = report_date or file_date
    _pattern, prefix, fields, staged, staging_table, statements = FILE_TYPES[file_type]

    loaded_at = already_loaded(conn, path.name)
    if loaded_at and not force:
        print(f'Skipping {path.name}: already loaded on {loaded_at:%Y-%m-%d %H:%M} (use --force to reload)')
        return False

    print(f'Loading {path.name} as {file_type} for {report_date:%Y-%m-%d}')
    rows = stage(conn, staging_table, staged, read_records(path, prefix, fields, staged))
    if rows == 0:
        raise ValueError(f'No {prefix} records found in {path.name}')
    print(f'  staged {rows:,} rows, updating tables...')

    cur = conn.cursor()
    try:
        for stmt in statements:
            if '?' in stmt:
                cur.execute(stmt, report_date)
            else:
                cur.execute(stmt)
        if file_type == 'loans' and cur.execute("SELECT OBJECT_ID(N'issuer_info', N'U')").fetchone()[0]:
            cur.execute(ISSUER_GROUP_UPDATE, report_date)
        cur.execute('DELETE FROM gnma_load_log WHERE file_name = ?', path.name)
        cur.execute('INSERT INTO gnma_load_log (file_name, file_type, report_date, rows_loaded, loaded_at) '
                    'VALUES (?, ?, ?, ?, SYSDATETIME())', path.name, file_type, report_date, rows)
        cur.execute(f'TRUNCATE TABLE {staging_table}')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
    print(f'Done: {path.name} ({rows:,} rows)')
    return True


def inbox_files(folder):
    return sorted(p for p in Path(folder).iterdir()
                  if p.is_file() and p.suffix.lower() in ('.txt', '.zip') and classify(p)[0])


def main(argv=None):
    parser = argparse.ArgumentParser(description='Load Ginnie Mae monthly disclosure files into Azure SQL.')
    parser.add_argument('files', nargs='*', help='llmon / llmonliq files (.txt or .zip) to load')
    parser.add_argument('--inbox', help='folder to scan for Ginnie Mae files that have not been loaded yet')
    parser.add_argument('--report-date', type=date.fromisoformat,
                        help='override the report month taken from the file name (YYYY-MM-01)')
    parser.add_argument('--force', action='store_true', help='reload files that were already loaded')
    args = parser.parse_args(argv)

    files = [Path(f) for f in args.files]
    if args.inbox:
        files += inbox_files(args.inbox)
    if not files:
        parser.error('give one or more files, or --inbox FOLDER')

    conn = get_connection()
    ensure_schema(conn)
    failures = 0
    for f in files:
        try:
            load_file(conn, f, args.report_date, args.force)
        except Exception as e:
            failures += 1
            print(f'FAILED {f.name}: {e}', file=sys.stderr)
    conn.close()
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
