"""
init_db.py — Initialize the PostgreSQL database for MediCore HMS.

Usage:
    python database/init_db.py

Reads DATABASE_URL from the .env file (or environment).
Runs schema_postgres.sql then seed_postgres.sql in order.
"""

import os
import sys

# Allow running from project root or from database/ directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, '.env'))

import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set. Check your .env file.")
    sys.exit(1)

# Fix Render's postgres:// quirk
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

SCHEMA_FILE = os.path.join(script_dir, 'schema_postgres.sql')
SEED_FILE   = os.path.join(script_dir, 'seed_postgres.sql')


def run_sql_file(conn, filepath, label):
    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print(f"{label} loaded successfully.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR loading {label}: {e}")
        raise


def main():
    print(f"Connecting to database...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        print("Connected.")
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    try:
        run_sql_file(conn, SCHEMA_FILE, "Schema")
        run_sql_file(conn, SEED_FILE,   "Seed data")
    finally:
        conn.close()
        print("Done.")


if __name__ == '__main__':
    main()
