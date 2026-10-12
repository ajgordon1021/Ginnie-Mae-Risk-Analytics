import os
import time
from getpass import getpass
from urllib.parse import quote_plus

import pandas as pd
import pyodbc
from sqlalchemy import create_engine

# Azure SQL connection settings (override any of these with environment variables)
SERVER = os.getenv('GINNIE_DB_SERVER', 'ginnie-mae-risk-db.database.windows.net')
DATABASE = os.getenv('GINNIE_DB_NAME', 'Ginnie_Mae_Risk')
USERNAME = os.getenv('GINNIE_DB_USER', 'andrewgordon')

_password = None
_engine = None


def _get_password():
    # Password comes from GINNIE_DB_PASSWORD, or is prompted for once per session
    global _password
    if _password is None:
        _password = os.getenv('GINNIE_DB_PASSWORD') or getpass('Azure SQL password: ')
    return _password


def _connection_string():
    return (
        'Driver={ODBC Driver 18 for SQL Server};'
        f'Server=tcp:{SERVER},1433;'
        f'Database={DATABASE};'
        f'Uid={USERNAME};'
        f'Pwd={{{_get_password()}}};'
        'Encrypt=yes;'
        'TrustServerCertificate=no;'
    )


# Azure errors that mean "waking up / busy, try again" (40613 = paused serverless database resuming)
_TRANSIENT_ERRORS = ('40613', '40197', '40501', '49918', '49919', '49920')


def get_connection(retries=10, wait_seconds=30):
    # A paused serverless database refuses connections for a minute or two while it resumes
    for attempt in range(1, retries + 1):
        try:
            # Login timeout in seconds; long enough for a paused serverless database to wake up
            return pyodbc.connect(_connection_string(), timeout=60)
        except pyodbc.Error as e:
            if attempt == retries or not any(code in str(e) for code in _TRANSIENT_ERRORS):
                raise
            print(f'Database is waking up, retrying in {wait_seconds} seconds ({attempt}/{retries})...', flush=True)
            time.sleep(wait_seconds)


def get_engine():
    # SQLAlchemy engine for pandas; reused for the whole session
    global _engine
    if _engine is None:
        _engine = create_engine(
            'mssql+pyodbc:///?odbc_connect=' + quote_plus(_connection_string()),
            connect_args={'timeout': 60},
            fast_executemany=True,
        )
    return _engine


def read_sql(query, **kwargs):
    # SQL Server keeps the case of column aliases; lowercase them to match the
    # names Postgres used to return
    df = pd.read_sql(query, get_engine(), **kwargs)
    df.columns = df.columns.str.lower()
    return df


def df_rows(df):
    # DataFrame -> list of tuples pyodbc can insert (NaN/NaT -> None, numpy -> Python types)
    return [tuple(r) for r in df.astype(object).where(df.notna(), None).values.tolist()]


def insert_rows(conn, table, rows, columns=None):
    # Bulk insert with one round trip per batch instead of one per row
    if not rows:
        return
    cols = f" ({', '.join(columns)})" if columns else ''
    placeholders = ', '.join('?' * len(rows[0]))
    cur = conn.cursor()
    cur.fast_executemany = True
    cur.executemany(f'INSERT INTO {table}{cols} VALUES ({placeholders})', rows)
    cur.close()
