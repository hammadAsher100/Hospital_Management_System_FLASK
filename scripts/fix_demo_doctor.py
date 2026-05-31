"""Fix: create missing doctors/nurses table rows for demo accounts.

The demo 'doctor' user (user_id=11) exists in the users table with role='doctor'
but has no corresponding row in the doctors table. Similarly, the demo 'nurse'
user (user_id=12) may be missing from the nurses table.

This script inserts the missing rows so that login + dashboard works correctly.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

try:
    # ── Fix demo 'doctor' user ───────────────────────────────────
    cur.execute("SELECT user_id FROM users WHERE username='doctor' AND role='doctor'")
    doctor_user = cur.fetchone()
    if doctor_user:
        uid = doctor_user['user_id']
        cur.execute("SELECT doctor_id FROM doctors WHERE user_id=%s", (uid,))
        existing = cur.fetchone()
        if existing:
            print(f"[OK] 'doctor' user (user_id={uid}) already has a doctors row (doctor_id={existing['doctor_id']}).")
        else:
            cur.execute(
                "INSERT INTO doctors (user_id, first_name, last_name, specialization, phone, email, "
                "consultation_fee, availability_status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE) RETURNING doctor_id",
                (uid, 'Demo', 'Doctor', 'General Physician', '0300-0000000', 'doctor@medicore.com', 1500.00),
            )
            new_id = cur.fetchone()['doctor_id']
            print(f"[FIXED] Created doctors row: doctor_id={new_id} for 'doctor' user (user_id={uid}).")

            # Add a default Mon-Fri 9-5 schedule for the demo doctor
            for day in range(5):  # Mon-Fri
                cur.execute(
                    "INSERT INTO doctor_schedules (doctor_id, day_of_week, start_time, end_time, max_appointments) "
                    "VALUES (%s, %s, '09:00', '17:00', 12) "
                    "ON CONFLICT (doctor_id, day_of_week) DO NOTHING",
                    (new_id, day),
                )
            print(f"[FIXED] Added Mon-Fri 9-5 schedule for demo doctor (doctor_id={new_id}).")
    else:
        print("[INFO] No 'doctor' username with role='doctor' found in users table.")

    # ── Fix demo 'nurse' user ────────────────────────────────────
    cur.execute("SELECT user_id FROM users WHERE username='nurse' AND role='nurse'")
    nurse_user = cur.fetchone()
    if nurse_user:
        uid = nurse_user['user_id']
        cur.execute("SELECT nurse_id FROM nurses WHERE user_id=%s", (uid,))
        existing = cur.fetchone()
        if existing:
            print(f"[OK] 'nurse' user (user_id={uid}) already has a nurses row (nurse_id={existing['nurse_id']}).")
        else:
            cur.execute(
                "INSERT INTO nurses (user_id, first_name, last_name, phone, email, assigned_ward) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING nurse_id",
                (uid, 'Demo', 'Nurse', '0300-0000001', 'nurse@medicore.com', 'General Ward'),
            )
            new_id = cur.fetchone()['nurse_id']
            print(f"[FIXED] Created nurses row: nurse_id={new_id} for 'nurse' user (user_id={uid}).")
    else:
        print("[INFO] No 'nurse' username with role='nurse' found in users table.")

    conn.commit()
    print("\n[OK] Migration complete.")

except Exception as e:
    conn.rollback()
    print(f"\n[ERROR] Migration failed: {e}")
    raise
finally:
    cur.close()
    conn.close()
