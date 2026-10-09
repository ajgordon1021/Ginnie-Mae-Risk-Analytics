import os
from getpass import getpass

import pyodbc

# Azure SQL connection settings (override any of these with environment variables)
SERVER = os.getenv('GINNIE_DB_SERVER', 'ginnie-mae-risk-db.database.windows.net')
DATABASE = os.getenv('GINNIE_DB_NAME', 'Ginnie_Mae_Risk')
USERNAME = os.getenv('GINNIE_DB_USER', 'andrewgordon')


def get_connection():
    # Password comes from GINNIE_DB_PASSWORD, or is prompted for if not set
    password = os.getenv('GINNIE_DB_PASSWORD') or getpass('Azure SQL password: ')
    return pyodbc.connect(
        'Driver={ODBC Driver 18 for SQL Server};'
        f'Server=tcp:{SERVER},1433;'
        f'Database={DATABASE};'
        f'Uid={USERNAME};'
        f'Pwd={{{password}}};'
        'Encrypt=yes;'
        'TrustServerCertificate=no;',
        # Login timeout in seconds; long enough for a paused serverless database to wake up
        timeout=60,
    )
