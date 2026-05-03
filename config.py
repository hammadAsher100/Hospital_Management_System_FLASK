import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _sqlalchemy_database_uri():
    """Full URI wins (needed for Azure SQL: encrypt, driver 18, etc.)."""
    explicit = (
        os.environ.get('SQLALCHEMY_DATABASE_URI')
        or os.environ.get('DATABASE_URL')
        or ''
    ).strip()
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

    SQLALCHEMY_DATABASE_URI = _sqlalchemy_database_uri()


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
