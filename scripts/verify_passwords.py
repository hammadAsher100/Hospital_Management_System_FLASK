"""Verify password for dr_ahmed."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import psycopg2, psycopg2.extras, bcrypt

DATABASE_URL = os.environ.get('DATABASE_URL', '')
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# Check dr_ahmed with DrAhmed@123
cur.execute("SELECT username, password_hash FROM users WHERE username IN ('dr_ahmed', 'doctor')")
for u in cur.fetchall():
    for pwd in ['DrAhmed@123', 'Doctor@123', 'doctor123', 'Password@123']:
        ok = bcrypt.checkpw(pwd.encode('utf-8'), u['password_hash'].encode('utf-8'))
        print(f"  {u['username']!r} + {pwd!r} = {ok}")

cur.close()
conn.close()
