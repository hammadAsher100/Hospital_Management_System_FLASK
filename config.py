import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _is_vercel_runtime():
    """Vercel sets these at runtime; check several because some builds omit VERCEL early."""
    return bool(
        os.environ.get('VERCEL')
        or os.environ.get('VERCEL_ENV')
        or os.environ.get('VERCEL_URL')
        or os.environ.get('VERCEL_REGION')
    )


def get_db_connection_params():
    """Get database connection parameters as a dictionary."""
    explicit = (
        os.environ.get('SQLALCHEMY_DATABASE_URI')
        or os.environ.get('DATABASE_URL')
        or ''
    ).strip()

    # Vercel/Linux fallback
    if _is_vercel_runtime():
        if explicit:
            lower = explicit.lower()
            if lower.startswith('sqlite') or 'postgresql' in lower or lower.startswith(
                'postgres'
            ):
                return {'uri': explicit, 'type': 'sqlite' if 'sqlite' in lower else 'postgres'}
            if 'mssql' in lower and os.environ.get('VERCEL_USE_MSSQL'):
                return {'uri': explicit, 'type': 'mssql'}
        return {'uri': 'sqlite:////tmp/hms_vercel.sqlite3', 'type': 'sqlite'}

    if explicit:
        return {'uri': explicit, 'type': 'mssql' if 'mssql' in explicit.lower() else 'unknown'}

    server = os.environ.get('DB_SERVER', r'localhost\SQLEXPRESS')
    db_name = os.environ.get('DB_NAME', 'HMS_DB')
    username = os.environ.get('DB_USERNAME', '')
    password = os.environ.get('DB_PASSWORD', '')
    driver = os.environ.get(
        'MSSQL_ODBC_DRIVER',
        'ODBC Driver 17 for SQL Server',
    )

    return {
        'driver': driver,
        'server': server,
        'database': db_name,
        'username': username if username else None,
        'password': password if password else None,
        'uri': f'mssql+pyodbc://{server}/{db_name}?driver={quote_plus(driver)}',
        'type': 'mssql'
    }


def _sqlalchemy_database_uri():
    """Full URI wins (needed for Azure SQL: encrypt, driver 18, etc.)."""
    params = get_db_connection_params()
    return params.get('uri', '')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    DB_SERVER = os.environ.get('DB_SERVER', r'localhost\SQLEXPRESS')
    DB_NAME = os.environ.get('DB_NAME', 'HMS_DB')
    DB_USERNAME = os.environ.get('DB_USERNAME', '')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')

    # Set in create_app() so the URI sees final process env (e.g. Vercel) and matches init_app().


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
