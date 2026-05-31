"""Diagnostic script: check database connection and doctor user accounts."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get('DATABASE_URL', '')
print(f"DATABASE_URL present: {bool(DATABASE_URL)}")
print(f"DATABASE_URL starts with: {DATABASE_URL[:30]}...")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    print("\n[OK] Connected to database successfully.\n")

    # 1. Check all users
    cur.execute("SELECT user_id, username, role, email, is_active FROM users ORDER BY user_id")
    users = cur.fetchall()
    print("=== ALL USERS ===")
    for u in users:
        print(f"  id={u['user_id']}  username={u['username']!r:15s}  role={u['role']!r:10s}  active={u['is_active']}  email={u['email']}")

    # 2. Check doctor-role users specifically
    print("\n=== DOCTOR-ROLE USERS ===")
    cur.execute("SELECT user_id, username, role, email, is_active FROM users WHERE role='doctor' ORDER BY user_id")
    doctors = cur.fetchall()
    for d in doctors:
        print(f"  id={d['user_id']}  username={d['username']!r}  active={d['is_active']}")

    # 3. Check if 'doctor' username exists (the demo credential shown in login page)
    print("\n=== CHECKING DEMO CREDENTIAL 'doctor' ===")
    cur.execute("SELECT user_id, username, role, email, is_active FROM users WHERE username='doctor'")
    demo_doc = cur.fetchone()
    if demo_doc:
        print(f"  FOUND: {demo_doc}")
    else:
        print("  NOT FOUND: No user with username='doctor' exists!")

    # 4. Check the doctors table
    print("\n=== DOCTORS TABLE ===")
    cur.execute("SELECT doctor_id, user_id, first_name, last_name, specialization FROM doctors ORDER BY doctor_id")
    doc_profiles = cur.fetchall()
    for dp in doc_profiles:
        print(f"  doctor_id={dp['doctor_id']}  user_id={dp['user_id']}  name={dp['first_name']} {dp['last_name']}  spec={dp['specialization']}")

    # 5. Check password hashes for doctor users
    print("\n=== PASSWORD HASHES (doctor role) ===")
    cur.execute("SELECT user_id, username, password_hash FROM users WHERE role='doctor'")
    for u in cur.fetchall():
        ph = u['password_hash']
        print(f"  {u['username']!r}: hash_len={len(ph)}, starts_with={ph[:7]!r}")

    cur.close()
    conn.close()
    print("\n[OK] Diagnostic complete.")

except Exception as e:
    print(f"\n[ERROR] Database connection failed: {e}")
