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


def _sqlalchemy_database_uri():
    """Full URI wins (needed for Azure SQL: encrypt, driver 18, etc.)."""
    explicit = (
        os.environ.get('SQLALCHEMY_DATABASE_URI')
        or os.environ.get('DATABASE_URL')
        or ''
    ).strip()

    # Vercel/Linux: Flask-SQLAlchemy 3 creates engines inside init_app(), so mssql+pyodbc
    # imports pyodbc immediately. Default Vercel runtimes usually lack MS ODBC → import crash.
    if _is_vercel_runtime():
        if explicit:
            lower = explicit.lower()
            if lower.startswith('sqlite') or 'postgresql' in lower or lower.startswith(
                'postgres'
            ):
                return explicit
            if 'mssql' in lower and os.environ.get('VERCEL_USE_MSSQL'):
                return explicit
            if 'mssql' in lower and not os.environ.get('VERCEL_USE_MSSQL'):
                print(
                    '[config] Vercel: ignoring MSSQL URI (set VERCEL_USE_MSSQL=1 if ODBC works). '
                    'Using SQLite fallback so the app can boot.'
                )
        return 'sqlite:////tmp/hms_vercel.sqlite3'

    if explicit:
        return explicit

    server = os.environ.get('DB_SERVER', r'localhost\SQLEXPRESS')
    db = os.environ.get('DB_NAME', 'HMS_DB')
    username = os.environ.get('DB_USERNAME', '')
    password = os.environ.get('DB_PASSWORD', '')
    # Spaces → + in SQLAlchemy URLs; override via env on Linux/production (e.g. Driver 18 for Azure).
    driver = os.environ.get(
        'MSSQL_ODBC_DRIVER',
        'ODBC Driver 17 for SQL Server',
    )
    driver_q = quote_plus(driver)

    if username and password:
        return (
            f'mssql+pyodbc://{quote_plus(username)}:{quote_plus(password)}@{server}/{db}'
            f'?driver={driver_q}'
        )
    return (
        f'mssql+pyodbc://@{server}/{db}'
        f'?driver={driver_q}&trusted_connection=yes'
    )


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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
