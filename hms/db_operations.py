"""
Database Operations Module — PostgreSQL / psycopg2
All stored procedure calls have been replaced with inline SQL.
psycopg2 uses %s positional placeholders; named :param style is
converted automatically by _convert_named_params().
"""

import re
from datetime import datetime, date, time
from typing import List, Optional, Dict, Any
from types import SimpleNamespace
import psycopg2
import psycopg2.extras
from hms import db


# ── Low-level helpers ────────────────────────────────────────────────────────

def _convert_named_params(sql, params):
    """Convert :name → %s for psycopg2."""
    if params is None:
        return sql, None
    if not isinstance(params, dict):
        return sql, params
    ordered = []

    def _rep(m):
        ordered.append(params.get(m.group(1)))
        return "%s"

    return re.sub(r":(\w+)", _rep, sql), tuple(ordered) if ordered else None


def is_sql_server():
    return False


def is_sqlite():
    return False


def is_postgres():
    return True


def _get_conn():
    return db.get_connection()


def execute_query(sql: str, params=None, commit_after: bool = False) -> List[Dict]:
    """Execute SQL and return list of dicts."""
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql, params = _convert_named_params(sql, params)
        cur.execute(sql, params)
        rows = []
        if cur.description:
            rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        if commit_after:
            conn.commit()
        return rows
    except Exception as e:
        print(f"Query Error: {e}")
        if conn and commit_after:
            try:
                conn.rollback()
            except Exception:
                pass
        return []
    finally:
        if conn:
            conn.close()


def execute_update(sql: str, params=None) -> bool:
    """Execute INSERT/UPDATE/DELETE. Returns True on success."""
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        sql, params = _convert_named_params(sql, params)
        cur.execute(sql, params)
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Update Error: {e}")
        return False
    finally:
        if conn:
            conn.close()


def execute_insert(sql: str, params=None) -> Optional[int]:
    """Execute INSERT … RETURNING id and return the new id."""
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        sql, params = _convert_named_params(sql, params)
        cur.execute(sql, params)
        row = cur.fetchone()
        conn.commit()
        cur.close()
        return int(row[0]) if row and row[0] is not None else None
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Insert Error: {e}")
        return None
    finally:
        if conn:
            conn.close()


def rows_to_objects(rows: List[Dict]) -> List[SimpleNamespace]:
    return [SimpleNamespace(**r) for r in rows]


def dict_to_object(row_dict: Dict) -> Optional[SimpleNamespace]:
    return SimpleNamespace(**row_dict) if row_dict else None


# ── USER OPERATIONS ──────────────────────────────────────────────────────────

_USER_COLS = "user_id, username, password_hash, role, email, full_name, created_at, last_login, is_active"


def get_user_by_username(username: str) -> Optional[SimpleNamespace]:
    rows = execute_query(f"SELECT {_USER_COLS} FROM users WHERE username = %s", (username,))
    return dict_to_object(rows[0]) if rows else None


def get_user_by_email(email: str) -> Optional[SimpleNamespace]:
    if not email:
        return None
    rows = execute_query(f"SELECT {_USER_COLS} FROM users WHERE email = %s", (email,))
    return dict_to_object(rows[0]) if rows else None


def get_user_by_id(user_id: int) -> Optional[SimpleNamespace]:
    rows = execute_query(f"SELECT {_USER_COLS} FROM users WHERE user_id = %s", (user_id,))
    return dict_to_object(rows[0]) if rows else None


def create_user(username: str, password_hash: str, role: str, email: str, full_name: str) -> Optional[int]:
    return execute_insert(
        "INSERT INTO users (username, password_hash, role, email, full_name, is_active) "
        "VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING user_id",
        (username, password_hash, role, email, full_name),
    )


def update_last_login(user_id: int) -> bool:
    return execute_update("UPDATE users SET last_login = NOW() WHERE user_id = %s", (user_id,))


def update_user_profile(user_id: int, full_name: str, email: str) -> bool:
    return execute_update(
        "UPDATE users SET full_name = %s, email = %s WHERE user_id = %s",
        (full_name, email, user_id),
    )


def update_user_password_hash(user_id: int, password_hash: str) -> bool:
    return execute_update(
        "UPDATE users SET password_hash = %s WHERE user_id = %s",
        (password_hash, user_id),
    )


def list_users() -> List[SimpleNamespace]:
    rows = execute_query(f"SELECT {_USER_COLS} FROM users ORDER BY full_name")
    return rows_to_objects(rows)


def toggle_user_active(user_id: int) -> Optional[SimpleNamespace]:
    execute_update(
        "UPDATE users SET is_active = NOT is_active WHERE user_id = %s", (user_id,)
    )
    rows = execute_query(f"SELECT {_USER_COLS} FROM users WHERE user_id = %s", (user_id,))
    return dict_to_object(rows[0]) if rows else None


# ── PATIENT OPERATIONS ───────────────────────────────────────────────────────

_PAT_COLS = ("patient_id, user_id, first_name, last_name, dob, gender, phone, email, "
             "address, emergency_contact, blood_group, allergies, registration_date")


def _fix_patient(p: SimpleNamespace) -> SimpleNamespace:
    if p and p.dob and not isinstance(p.dob, date):
        p.dob = datetime.strptime(str(p.dob), "%Y-%m-%d").date()
    return p


def get_patient_by_id(patient_id: int) -> Optional[SimpleNamespace]:
    rows = execute_query(f"SELECT {_PAT_COLS} FROM patients WHERE patient_id = %s", (patient_id,))
    return _fix_patient(dict_to_object(rows[0])) if rows else None


def get_patient_by_user_id(user_id: int) -> Optional[SimpleNamespace]:
    rows = execute_query(f"SELECT {_PAT_COLS} FROM patients WHERE user_id = %s", (user_id,))
    return _fix_patient(dict_to_object(rows[0])) if rows else None


def list_patients(skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    rows = execute_query(
        f"SELECT {_PAT_COLS} FROM patients ORDER BY last_name, first_name LIMIT %s OFFSET %s",
        (take, skip),
    )
    return [_fix_patient(dict_to_object(r)) for r in rows]


def create_patient(first_name: str, last_name: str, dob: date, gender: str, phone: str,
                   user_id: int = None, email: str = None, address: str = None,
                   emergency_contact: str = None, blood_group: str = None,
                   allergies: str = None) -> Optional[int]:
    return execute_insert(
        "INSERT INTO patients (user_id, first_name, last_name, dob, gender, phone, email, "
        "address, emergency_contact, blood_group, allergies) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING patient_id",
        (user_id, first_name, last_name, dob, gender, phone, email,
         address, emergency_contact, blood_group, allergies),
    )


def update_patient(patient_id: int, first_name: str, last_name: str, phone: str,
                   email: str = None, address: str = None, emergency_contact: str = None,
                   blood_group: str = None, allergies: str = None) -> bool:
    return execute_update(
        "UPDATE patients SET first_name=%s, last_name=%s, phone=%s, email=%s, "
        "address=%s, emergency_contact=%s, blood_group=%s, allergies=%s "
        "WHERE patient_id=%s",
        (first_name, last_name, phone, email, address, emergency_contact,
         blood_group, allergies, patient_id),
    )


def update_patient_full(patient_id: int, first_name: str, last_name: str, dob: date,
                        gender: str, phone: str, email: str = None, address: str = None,
                        emergency_contact: str = None, blood_group: str = None,
                        allergies: str = None) -> bool:
    return execute_update(
        "UPDATE patients SET first_name=%s, last_name=%s, dob=%s, gender=%s, phone=%s, "
        "email=%s, address=%s, emergency_contact=%s, blood_group=%s, allergies=%s "
        "WHERE patient_id=%s",
        (first_name, last_name, dob, gender, phone, email, address,
         emergency_contact, blood_group, allergies, patient_id),
    )


def delete_patient(patient_id: int) -> bool:
    return execute_update("DELETE FROM patients WHERE patient_id = %s", (patient_id,))


def search_patients_count(search: str = None) -> int:
    if search:
        term = f"%{search}%"
        rows = execute_query(
            "SELECT COUNT(*) AS c FROM patients "
            "WHERE first_name ILIKE %s OR last_name ILIKE %s OR phone ILIKE %s",
            (term, term, term),
        )
    else:
        rows = execute_query("SELECT COUNT(*) AS c FROM patients")
    return int(rows[0]["c"]) if rows else 0


def search_patients(search: str = None, skip: int = 0, take: int = 15) -> List[SimpleNamespace]:
    if search:
        term = f"%{search}%"
        rows = execute_query(
            f"SELECT {_PAT_COLS} FROM patients "
            "WHERE first_name ILIKE %s OR last_name ILIKE %s OR phone ILIKE %s "
            "ORDER BY last_name, first_name LIMIT %s OFFSET %s",
            (term, term, term, take, skip),
        )
    else:
        rows = execute_query(
            f"SELECT {_PAT_COLS} FROM patients ORDER BY last_name, first_name LIMIT %s OFFSET %s",
            (take, skip),
        )
    return [_fix_patient(dict_to_object(r)) for r in rows]


def update_patient_profile(patient_id: int, user_id: int, email: str = None,
                           phone: str = None, address: str = None,
                           emergency_contact: str = None, blood_group: str = None,
                           allergies: str = None) -> bool:
    ok = execute_update(
        "UPDATE patients SET email=%s, phone=%s, address=%s, emergency_contact=%s, "
        "blood_group=%s, allergies=%s WHERE patient_id=%s",
        (email, phone, address, emergency_contact, blood_group, allergies, patient_id),
    )
    if ok and user_id and email:
        execute_update("UPDATE users SET email=%s WHERE user_id=%s", (email, user_id))
    return ok


def get_patient_dashboard_stats(patient_id: int) -> Dict[str, int]:
    rows = execute_query(
        "SELECT COUNT(*) AS total_appointments, "
        "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed_appointments "
        "FROM appointments WHERE patient_id = %s",
        (patient_id,),
    )
    if rows:
        return {
            "total_appointments": int(rows[0].get("total_appointments") or 0),
            "completed_appointments": int(rows[0].get("completed_appointments") or 0),
        }
    return {"total_appointments": 0, "completed_appointments": 0}


# ── APPOINTMENT OPERATIONS ───────────────────────────────────────────────────

_APPT_DETAIL_SQL = """
    SELECT a.*,
           p.first_name AS patient_first_name, p.last_name AS patient_last_name,
           (p.first_name || ' ' || p.last_name) AS patient_full_name,
           p.gender AS patient_gender, p.phone AS patient_phone,
           p.blood_group AS patient_blood_group, p.allergies AS patient_allergies,
           DATE_PART('year', AGE(p.dob))::int AS patient_age,
           d.first_name AS doctor_first_name, d.last_name AS doctor_last_name,
           ('Dr. ' || d.first_name || ' ' || d.last_name) AS doctor_full_name,
           d.specialization AS doctor_specialization, d.consultation_fee
    FROM appointments a
    INNER JOIN patients p ON p.patient_id = a.patient_id
    INNER JOIN doctors d ON d.doctor_id = a.doctor_id
"""


def _fix_appt(appt: SimpleNamespace) -> SimpleNamespace:
    if appt.appointment_date and not isinstance(appt.appointment_date, date):
        appt.appointment_date = datetime.strptime(str(appt.appointment_date), "%Y-%m-%d").date()
    if hasattr(appt, "appointment_time") and appt.appointment_time:
        raw = str(appt.appointment_time)
        if ":" in raw and not hasattr(appt.appointment_time, "hour"):
            appt.appointment_time = datetime.strptime(raw[:8], "%H:%M:%S").time()
    return appt


def check_appointment_conflict(doctor_id: int, appointment_date: date,
                                appointment_time: time, exclude_id: int = None) -> bool:
    if exclude_id:
        rows = execute_query(
            "SELECT COUNT(*) AS c FROM appointments WHERE doctor_id=%s AND appointment_date=%s "
            "AND appointment_time=%s AND status='scheduled' AND appointment_id<>%s",
            (doctor_id, appointment_date, appointment_time, exclude_id),
        )
    else:
        rows = execute_query(
            "SELECT COUNT(*) AS c FROM appointments WHERE doctor_id=%s AND appointment_date=%s "
            "AND appointment_time=%s AND status='scheduled'",
            (doctor_id, appointment_date, appointment_time),
        )
    return int(rows[0]["c"]) > 0 if rows else False


def get_doctor_booked_slots(doctor_id: int, appointment_date: date) -> List[str]:
    rows = execute_query(
        "SELECT appointment_time FROM appointments "
        "WHERE doctor_id=%s AND appointment_date=%s AND status='scheduled'",
        (doctor_id, appointment_date),
    )
    return [str(r["appointment_time"])[:5] for r in rows]


def get_doctor_schedule_by_day(doctor_id: int, day_of_week: int) -> Optional[SimpleNamespace]:
    rows = execute_query(
        "SELECT schedule_id, doctor_id, day_of_week, start_time, end_time, max_appointments "
        "FROM doctor_schedules WHERE doctor_id=%s AND day_of_week=%s",
        (doctor_id, day_of_week),
    )
    if not rows:
        return None
    s = dict_to_object(rows[0])
    if s.start_time and not hasattr(s.start_time, "hour"):
        s.start_time = datetime.strptime(str(s.start_time)[:8], "%H:%M:%S").time()
    if s.end_time and not hasattr(s.end_time, "hour"):
        s.end_time = datetime.strptime(str(s.end_time)[:8], "%H:%M:%S").time()
    return s


def count_appointments(status: str = None, doctor_id: int = None,
                       patient_id: int = None, appointment_date: date = None) -> int:
    conds, vals = ["1=1"], []
    if status:
        conds.append("status=%s"); vals.append(status)
    if doctor_id:
        conds.append("doctor_id=%s"); vals.append(doctor_id)
    if patient_id:
        conds.append("patient_id=%s"); vals.append(patient_id)
    if appointment_date:
        conds.append("appointment_date=%s"); vals.append(appointment_date)
    rows = execute_query(
        f"SELECT COUNT(*) AS c FROM appointments WHERE {' AND '.join(conds)}",
        tuple(vals) if vals else None,
    )
    return int(rows[0]["c"]) if rows else 0


def list_appointments(status: str = None, doctor_id: int = None, patient_id: int = None,
                      appointment_date: date = None, skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    conds, vals = ["1=1"], []
    if status:
        conds.append("a.status=%s"); vals.append(status)
    if doctor_id:
        conds.append("a.doctor_id=%s"); vals.append(doctor_id)
    if patient_id:
        conds.append("a.patient_id=%s"); vals.append(patient_id)
    if appointment_date:
        conds.append("a.appointment_date=%s"); vals.append(appointment_date)
    vals += [take, skip]
    rows = execute_query(
        f"{_APPT_DETAIL_SQL} WHERE {' AND '.join(conds)} "
        "ORDER BY a.appointment_date DESC, a.appointment_time DESC LIMIT %s OFFSET %s",
        tuple(vals),
    )
    return [_fix_appt(dict_to_object(r)) for r in rows]


def get_appointment_by_id(appointment_id: int) -> Optional[SimpleNamespace]:
    rows = execute_query(
        f"{_APPT_DETAIL_SQL} WHERE a.appointment_id = %s", (appointment_id,)
    )
    return _fix_appt(dict_to_object(rows[0])) if rows else None


def create_appointment(patient_id: int, doctor_id: int, appointment_date: date,
                       appointment_time: time, reason: str = None) -> Optional[int]:
    return execute_insert(
        "INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, "
        "status, reason) VALUES (%s,%s,%s,%s,'scheduled',%s) RETURNING appointment_id",
        (patient_id, doctor_id, appointment_date, appointment_time, reason),
    )


def update_appointment_status(appointment_id: int, status: str, notes: str = None) -> bool:
    if notes is not None:
        return execute_update(
            "UPDATE appointments SET status=%s, notes=%s WHERE appointment_id=%s",
            (status, notes, appointment_id),
        )
    return execute_update(
        "UPDATE appointments SET status=%s WHERE appointment_id=%s",
        (status, appointment_id),
    )


def reschedule_appointment(appointment_id: int, new_date: date, new_time: time) -> bool:
    return execute_update(
        "UPDATE appointments SET appointment_date=%s, appointment_time=%s WHERE appointment_id=%s",
        (new_date, new_time, appointment_id),
    )


def list_completed_appointments(patient_id: int = None, skip: int = 0, take: int = 100) -> List[SimpleNamespace]:
    if patient_id:
        rows = execute_query(
            f"{_APPT_DETAIL_SQL} WHERE a.status='completed' AND a.patient_id=%s "
            "ORDER BY a.appointment_date DESC LIMIT %s OFFSET %s",
            (patient_id, take, skip),
        )
    else:
        rows = execute_query(
            f"{_APPT_DETAIL_SQL} WHERE a.status='completed' "
            "ORDER BY a.appointment_date DESC LIMIT %s OFFSET %s",
            (take, skip),
        )
    return [_fix_appt(dict_to_object(r)) for r in rows]


# ── DOCTOR / NURSE / SCHEDULE OPERATIONS ────────────────────────────────────

_DOC_COLS = ("doctor_id, user_id, first_name, last_name, specialization, "
             "phone, email, consultation_fee, availability_status")


def get_doctor_by_id(doctor_id: int) -> Optional[SimpleNamespace]:
    rows = execute_query(f"SELECT {_DOC_COLS} FROM doctors WHERE doctor_id=%s", (doctor_id,))
    return dict_to_object(rows[0]) if rows else None


def get_doctor_by_user_id(user_id: int) -> Optional[SimpleNamespace]:
    rows = execute_query(f"SELECT {_DOC_COLS} FROM doctors WHERE user_id=%s", (user_id,))
    return dict_to_object(rows[0]) if rows else None


def list_doctors() -> List[SimpleNamespace]:
    rows = execute_query(
        f"SELECT d.{_DOC_COLS.replace(', ', ', d.')}, "
        "COUNT(a.appointment_id) AS total_appointments "
        "FROM doctors d LEFT JOIN appointments a ON a.doctor_id=d.doctor_id "
        "GROUP BY d.doctor_id ORDER BY d.last_name, d.first_name"
    )
    return rows_to_objects(rows)


def list_active_doctors() -> List[SimpleNamespace]:
    rows = execute_query(
        "SELECT d.doctor_id, d.first_name, d.last_name, d.specialization, d.consultation_fee, "
        "('Dr. ' || d.first_name || ' ' || d.last_name) AS full_name "
        "FROM doctors d INNER JOIN users u ON u.user_id=d.user_id "
        "WHERE u.is_active=TRUE AND (d.availability_status=TRUE OR d.availability_status IS NULL) "
        "ORDER BY d.last_name, d.first_name"
    )
    return rows_to_objects(rows)


def create_doctor_with_user(username: str, password_hash: str, email: str,
                             first_name: str, last_name: str, specialization: str,
                             phone: str = None, consultation_fee: float = 0) -> Optional[int]:
    user_id = execute_insert(
        "INSERT INTO users (username, password_hash, role, email, full_name, is_active) "
        "VALUES (%s,%s,'doctor',%s,%s,TRUE) RETURNING user_id",
        (username, password_hash, email, f"{first_name} {last_name}"),
    )
    if not user_id:
        return None
    return execute_insert(
        "INSERT INTO doctors (user_id, first_name, last_name, specialization, phone, email, "
        "consultation_fee, availability_status) VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE) RETURNING doctor_id",
        (user_id, first_name, last_name, specialization, phone, email, consultation_fee),
    )


def list_nurses() -> List[SimpleNamespace]:
    rows = execute_query(
        "SELECT n.nurse_id, n.user_id, n.first_name, n.last_name, n.phone, n.email, "
        "n.assigned_ward, COUNT(a.admission_id) AS active_admissions_count "
        "FROM nurses n LEFT JOIN admissions a ON a.nurse_id=n.nurse_id AND a.discharge_date IS NULL "
        "GROUP BY n.nurse_id ORDER BY n.last_name, n.first_name"
    )
    return rows_to_objects(rows)


def get_nurse_by_user_id(user_id: int) -> Optional[SimpleNamespace]:
    rows = execute_query(
        "SELECT nurse_id, user_id, first_name, last_name, phone, email, assigned_ward "
        "FROM nurses WHERE user_id=%s", (user_id,)
    )
    return dict_to_object(rows[0]) if rows else None


def create_nurse_with_user(username: str, password_hash: str, email: str,
                            first_name: str, last_name: str,
                            phone: str = None, assigned_ward: str = None) -> Optional[int]:
    user_id = execute_insert(
        "INSERT INTO users (username, password_hash, role, email, full_name, is_active) "
        "VALUES (%s,%s,'nurse',%s,%s,TRUE) RETURNING user_id",
        (username, password_hash, email, f"{first_name} {last_name}"),
    )
    if not user_id:
        return None
    return execute_insert(
        "INSERT INTO nurses (user_id, first_name, last_name, phone, email, assigned_ward) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING nurse_id",
        (user_id, first_name, last_name, phone, email, assigned_ward),
    )


def list_doctor_schedules(doctor_id: int) -> List[SimpleNamespace]:
    rows = execute_query(
        "SELECT schedule_id, doctor_id, day_of_week, start_time, end_time, max_appointments "
        "FROM doctor_schedules WHERE doctor_id=%s ORDER BY day_of_week", (doctor_id,)
    )
    return rows_to_objects(rows)


def clear_doctor_schedules(doctor_id: int) -> bool:
    return execute_update("DELETE FROM doctor_schedules WHERE doctor_id=%s", (doctor_id,))


def add_doctor_schedule(doctor_id: int, day_of_week: int, start_time: time,
                         end_time: time, max_appointments: int = 10) -> bool:
    return execute_update(
        "INSERT INTO doctor_schedules (doctor_id, day_of_week, start_time, end_time, max_appointments) "
        "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (doctor_id, day_of_week) DO UPDATE "
        "SET start_time=EXCLUDED.start_time, end_time=EXCLUDED.end_time, "
        "max_appointments=EXCLUDED.max_appointments",
        (doctor_id, day_of_week, start_time, end_time, max_appointments),
    )


def count_recent_unique_patients(days: int = 30) -> int:
    rows = execute_query(
        "SELECT COUNT(DISTINCT patient_id) AS c FROM appointments "
        "WHERE appointment_date >= CURRENT_DATE - (%s * INTERVAL '1 day')",
        (days,),
    )
    return int(rows[0]["c"]) if rows else 0


# ── MEDICINE / PHARMACY OPERATIONS ──────────────────────────────────────────

_MED_COLS = ("medicine_id, name, category, manufacturer, unit_price, "
             "stock_quantity, reorder_level, expiry_date")


def get_medicine_by_id(medicine_id: int) -> Optional[SimpleNamespace]:
    rows = execute_query(f"SELECT {_MED_COLS} FROM medicines WHERE medicine_id=%s", (medicine_id,))
    return dict_to_object(rows[0]) if rows else None


def list_medicines(search: str = None, category: str = None,
                   skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    conds, vals = ["1=1"], []
    if search:
        conds.append("name ILIKE %s"); vals.append(f"%{search}%")
    if category:
        conds.append("category=%s"); vals.append(category)
    vals += [take, skip]
    rows = execute_query(
        f"SELECT {_MED_COLS} FROM medicines WHERE {' AND '.join(conds)} "
        "ORDER BY name LIMIT %s OFFSET %s", tuple(vals)
    )
    return rows_to_objects(rows)


def count_medicines(search: str = None, category: str = None) -> int:
    conds, vals = ["1=1"], []
    if search:
        conds.append("name ILIKE %s"); vals.append(f"%{search}%")
    if category:
        conds.append("category=%s"); vals.append(category)
    rows = execute_query(
        f"SELECT COUNT(*) AS c FROM medicines WHERE {' AND '.join(conds)}",
        tuple(vals) if vals else None,
    )
    return int(rows[0]["c"]) if rows else 0


def list_medicine_categories() -> List[str]:
    rows = execute_query(
        "SELECT DISTINCT category FROM medicines WHERE category IS NOT NULL ORDER BY category"
    )
    return [r["category"] for r in rows]


def create_medicine(name: str, unit_price: float, category: str = None,
                    manufacturer: str = None, stock_quantity: int = 0,
                    reorder_level: int = 10, expiry_date: date = None) -> Optional[int]:
    return execute_insert(
        f"INSERT INTO medicines (name, category, manufacturer, unit_price, stock_quantity, "
        f"reorder_level, expiry_date) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING medicine_id",
        (name, category or None, manufacturer or None, unit_price,
         max(0, stock_quantity), max(0, reorder_level), expiry_date),
    )


def update_medicine(medicine_id: int, name: str, unit_price: float, category: str = None,
                    manufacturer: str = None, reorder_level: int = 10,
                    expiry_date: date = None) -> bool:
    return execute_update(
        "UPDATE medicines SET name=%s, category=%s, manufacturer=%s, unit_price=%s, "
        "reorder_level=%s, expiry_date=%s WHERE medicine_id=%s",
        (name, category or None, manufacturer or None, unit_price,
         reorder_level, expiry_date, medicine_id),
    )


def update_medicine_stock(medicine_id: int, quantity_change: int) -> bool:
    return execute_update(
        "UPDATE medicines SET stock_quantity = GREATEST(0, stock_quantity + %s) "
        "WHERE medicine_id=%s",
        (quantity_change, medicine_id),
    )


def get_low_stock_medicines() -> List[SimpleNamespace]:
    rows = execute_query(
        f"SELECT {_MED_COLS} FROM medicines WHERE stock_quantity <= reorder_level ORDER BY name"
    )
    return rows_to_objects(rows)


# ── PRESCRIPTION OPERATIONS ──────────────────────────────────────────────────

def get_prescription_by_id(prescription_id: int) -> Optional[SimpleNamespace]:
    rows = execute_query(
        "SELECT prescription_id, patient_id, doctor_id, appointment_id, "
        "prescribed_date, notes, is_dispensed FROM prescriptions WHERE prescription_id=%s",
        (prescription_id,),
    )
    return dict_to_object(rows[0]) if rows else None


def list_prescriptions(patient_id: int = None, doctor_id: int = None,
                       is_dispensed: bool = None, skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    conds, vals = ["1=1"], []
    if patient_id is not None:
        conds.append("patient_id=%s"); vals.append(patient_id)
    if doctor_id is not None:
        conds.append("doctor_id=%s"); vals.append(doctor_id)
    if is_dispensed is not None:
        conds.append("is_dispensed=%s"); vals.append(is_dispensed)
    vals += [take, skip]
    rows = execute_query(
        f"SELECT prescription_id, patient_id, doctor_id, appointment_id, "
        f"prescribed_date, notes, is_dispensed FROM prescriptions "
        f"WHERE {' AND '.join(conds)} ORDER BY prescribed_date DESC LIMIT %s OFFSET %s",
        tuple(vals),
    )
    return rows_to_objects(rows)


def count_prescriptions(patient_id: int = None, doctor_id: int = None,
                        is_dispensed: bool = None) -> int:
    conds, vals = ["1=1"], []
    if patient_id is not None:
        conds.append("patient_id=%s"); vals.append(patient_id)
    if doctor_id is not None:
        conds.append("doctor_id=%s"); vals.append(doctor_id)
    if is_dispensed is not None:
        conds.append("is_dispensed=%s"); vals.append(is_dispensed)
    rows = execute_query(
        f"SELECT COUNT(*) AS c FROM prescriptions WHERE {' AND '.join(conds)}",
        tuple(vals) if vals else None,
    )
    return int(rows[0]["c"]) if rows else 0


def get_prescription_items(prescription_id: int) -> List[SimpleNamespace]:
    rows = execute_query(
        "SELECT pi.pres_item_id, pi.prescription_id, pi.medicine_id, m.name AS medicine_name, "
        "pi.dosage, pi.frequency, pi.duration, pi.quantity "
        "FROM prescription_items pi INNER JOIN medicines m ON m.medicine_id=pi.medicine_id "
        "WHERE pi.prescription_id=%s ORDER BY pi.pres_item_id",
        (prescription_id,),
    )
    return rows_to_objects(rows)


def create_prescription(patient_id: int, doctor_id: int,
                        appointment_id: int = None, notes: str = None) -> Optional[int]:
    return execute_insert(
        "INSERT INTO prescriptions (patient_id, doctor_id, appointment_id, notes, is_dispensed) "
        "VALUES (%s,%s,%s,%s,FALSE) RETURNING prescription_id",
        (patient_id, doctor_id, appointment_id, notes),
    )


def add_prescription_item(prescription_id: int, medicine_id: int, dosage: str,
                           frequency: str, duration: str, quantity: int = 1) -> Optional[int]:
    return execute_insert(
        "INSERT INTO prescription_items (prescription_id, medicine_id, dosage, frequency, "
        "duration, quantity) VALUES (%s,%s,%s,%s,%s,%s) RETURNING pres_item_id",
        (prescription_id, medicine_id, dosage, frequency, duration, quantity),
    )


def mark_prescription_dispensed(prescription_id: int) -> bool:
    return execute_update(
        "UPDATE prescriptions SET is_dispensed=TRUE WHERE prescription_id=%s",
        (prescription_id,),
    )


def add_prescription_atomic(patient_id: int, doctor_id: int, items: list,
                             appointment_id: int = None, notes: str = None) -> Optional[int]:
    """Create prescription + all items in one transaction."""
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO prescriptions (patient_id, doctor_id, appointment_id, notes, is_dispensed) "
            "VALUES (%s,%s,%s,%s,FALSE) RETURNING prescription_id",
            (patient_id, doctor_id, appointment_id, notes),
        )
        prescription_id = cur.fetchone()[0]
        for item in items:
            cur.execute(
                "INSERT INTO prescription_items (prescription_id, medicine_id, dosage, "
                "frequency, duration, quantity) VALUES (%s,%s,%s,%s,%s,%s)",
                (prescription_id, item["medicine_id"], item.get("dosage"),
                 item.get("frequency"), item.get("duration"), item.get("quantity", 1)),
            )
        conn.commit()
        cur.close()
        return prescription_id
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"add_prescription_atomic error: {e}")
        return None
    finally:
        if conn:
            conn.close()


# ── BILLING OPERATIONS ───────────────────────────────────────────────────────

_BILL_DETAIL_SQL = """
    SELECT b.bill_id, b.patient_id, b.appointment_id, b.admission_id,
           b.bill_date, b.total_amount, b.paid_amount, b.status, b.payment_method,
           p.first_name AS patient_first_name, p.last_name AS patient_last_name,
           (p.first_name || ' ' || p.last_name) AS patient_full_name,
           p.phone AS patient_phone, p.email AS patient_email,
           p.address AS patient_address, p.blood_group AS patient_blood_group
    FROM billing b
    INNER JOIN patients p ON p.patient_id = b.patient_id
"""


def _fix_bill(b: SimpleNamespace) -> SimpleNamespace:
    if b and b.bill_date and not isinstance(b.bill_date, datetime):
        try:
            b.bill_date = datetime.strptime(str(b.bill_date)[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return b


def get_bill_by_id(bill_id: int) -> Optional[SimpleNamespace]:
    rows = execute_query(f"{_BILL_DETAIL_SQL} WHERE b.bill_id=%s", (bill_id,))
    return _fix_bill(dict_to_object(rows[0])) if rows else None


def get_bill_by_appointment_id(appointment_id: int) -> Optional[SimpleNamespace]:
    rows = execute_query(f"{_BILL_DETAIL_SQL} WHERE b.appointment_id=%s", (appointment_id,))
    return _fix_bill(dict_to_object(rows[0])) if rows else None


def count_bills(patient_id: int = None, status: str = None) -> int:
    conds, vals = ["1=1"], []
    if patient_id:
        conds.append("patient_id=%s"); vals.append(patient_id)
    if status:
        conds.append("status=%s"); vals.append(status)
    rows = execute_query(
        f"SELECT COUNT(*) AS c FROM billing WHERE {' AND '.join(conds)}",
        tuple(vals) if vals else None,
    )
    return int(rows[0]["c"]) if rows else 0


def list_bills(patient_id: int = None, status: str = None,
               skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    conds, vals = ["1=1"], []
    if patient_id:
        conds.append("b.patient_id=%s"); vals.append(patient_id)
    if status:
        conds.append("b.status=%s"); vals.append(status)
    vals += [take, skip]
    rows = execute_query(
        f"{_BILL_DETAIL_SQL} WHERE {' AND '.join(conds)} "
        "ORDER BY b.bill_date DESC LIMIT %s OFFSET %s",
        tuple(vals),
    )
    return [_fix_bill(dict_to_object(r)) for r in rows]


def get_bill_items(bill_id: int) -> List[SimpleNamespace]:
    rows = execute_query(
        "SELECT item_id, bill_id, description, quantity, unit_price, total_price "
        "FROM bill_items WHERE bill_id=%s ORDER BY item_id",
        (bill_id,),
    )
    return rows_to_objects(rows)


def create_bill(patient_id: int, appointment_id: int = None, admission_id: int = None,
                payment_method: str = None, total_amount: float = 0) -> Optional[int]:
    return execute_insert(
        "INSERT INTO billing (patient_id, appointment_id, admission_id, payment_method, "
        "total_amount, paid_amount, status) VALUES (%s,%s,%s,%s,%s,0,'pending') RETURNING bill_id",
        (patient_id, appointment_id, admission_id, payment_method, total_amount),
    )


def add_bill_item(bill_id: int, description: str, quantity: int, unit_price: float) -> Optional[int]:
    total = quantity * unit_price
    return execute_insert(
        "INSERT INTO bill_items (bill_id, description, quantity, unit_price, total_price) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING item_id",
        (bill_id, description, quantity, unit_price, total),
    )


def refresh_bill_totals(bill_id: int) -> bool:
    return execute_update(
        """
        UPDATE billing SET
            total_amount = COALESCE((SELECT SUM(total_price) FROM bill_items WHERE bill_id=%s), 0),
            status = CASE
                WHEN COALESCE((SELECT SUM(total_price) FROM bill_items WHERE bill_id=%s), 0) <= 0
                    THEN 'pending'
                WHEN paid_amount >= COALESCE((SELECT SUM(total_price) FROM bill_items WHERE bill_id=%s), 0)
                    THEN 'paid'
                WHEN paid_amount > 0 THEN 'partial'
                ELSE 'pending'
            END
        WHERE bill_id=%s
        """,
        (bill_id, bill_id, bill_id, bill_id),
    )


def record_payment(bill_id: int, payment_amount: float, payment_method: str) -> bool:
    ok = execute_update(
        "UPDATE billing SET paid_amount = paid_amount + %s, payment_method=%s WHERE bill_id=%s",
        (payment_amount, payment_method, bill_id),
    )
    if ok:
        refresh_bill_totals(bill_id)
    return ok


# ── ADMISSION OPERATIONS ─────────────────────────────────────────────────────

def get_admission_by_id(admission_id: int) -> Optional[SimpleNamespace]:
    rows = execute_query(
        "SELECT admission_id, patient_id, doctor_id, nurse_id, admission_date, "
        "discharge_date, room_number, diagnosis FROM admissions WHERE admission_id=%s",
        (admission_id,),
    )
    return dict_to_object(rows[0]) if rows else None


def list_active_admissions(skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    rows = execute_query(
        "SELECT a.admission_id, a.patient_id, a.doctor_id, a.nurse_id, "
        "a.admission_date, a.discharge_date, a.room_number, a.diagnosis, "
        "(p.first_name || ' ' || p.last_name) AS patient_full_name, "
        "('Dr. ' || d.first_name || ' ' || d.last_name) AS doctor_full_name "
        "FROM admissions a "
        "INNER JOIN patients p ON p.patient_id=a.patient_id "
        "INNER JOIN doctors d ON d.doctor_id=a.doctor_id "
        "WHERE a.discharge_date IS NULL "
        "ORDER BY a.admission_date DESC LIMIT %s OFFSET %s",
        (take, skip),
    )
    return rows_to_objects(rows)


def create_admission(patient_id: int, doctor_id: int, nurse_id: int = None,
                     room_number: str = None, diagnosis: str = None) -> Optional[int]:
    return execute_insert(
        "INSERT INTO admissions (patient_id, doctor_id, nurse_id, room_number, diagnosis) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING admission_id",
        (patient_id, doctor_id, nurse_id, room_number, diagnosis),
    )


def discharge_patient(admission_id: int) -> bool:
    return execute_update(
        "UPDATE admissions SET discharge_date=NOW() WHERE admission_id=%s",
        (admission_id,),
    )


# ── ADMIN DASHBOARD / REPORT OPERATIONS ─────────────────────────────────────

def get_admin_dashboard_metrics(today: date) -> Dict[str, Any]:
    month_start = today.replace(day=1)
    rows = execute_query(
        """
        SELECT
            (SELECT COUNT(*) FROM patients) AS total_patients,
            (SELECT COUNT(*) FROM appointments WHERE appointment_date=%s) AS today_appointments,
            (SELECT COUNT(*) FROM admissions WHERE discharge_date IS NULL) AS active_admissions,
            (SELECT COUNT(*) FROM medicines WHERE stock_quantity <= reorder_level) AS low_stock_count,
            (SELECT COALESCE(SUM(paid_amount),0) FROM billing WHERE bill_date >= %s) AS monthly_revenue,
            (SELECT COUNT(*) FROM billing WHERE status='pending') AS pending_bills_count
        """,
        (today, month_start),
    )
    if rows:
        r = rows[0]
        return {
            "total_patients": int(r.get("total_patients") or 0),
            "today_appointments": int(r.get("today_appointments") or 0),
            "active_admissions": int(r.get("active_admissions") or 0),
            "low_stock_count": int(r.get("low_stock_count") or 0),
            "monthly_revenue": float(r.get("monthly_revenue") or 0),
            "pending_bills_count": int(r.get("pending_bills_count") or 0),
        }
    return {k: 0 for k in ("total_patients", "today_appointments", "active_admissions",
                            "low_stock_count", "monthly_revenue", "pending_bills_count")}


def get_dashboard_today_appointments(today: date, limit: int = 5) -> List[Dict]:
    return execute_query(
        "SELECT a.patient_id, a.appointment_time, a.status, "
        "(p.first_name || ' ' || p.last_name) AS patient_name, "
        "('Dr. ' || d.first_name || ' ' || d.last_name) AS doctor_name "
        "FROM appointments a "
        "INNER JOIN patients p ON p.patient_id=a.patient_id "
        "INNER JOIN doctors d ON d.doctor_id=a.doctor_id "
        "WHERE a.appointment_date=%s ORDER BY a.appointment_time LIMIT %s",
        (today, limit),
    )


def get_dashboard_recent_patients(limit: int = 5) -> List[Dict]:
    return execute_query(
        "SELECT patient_id, (first_name || ' ' || last_name) AS full_name, "
        "gender, phone, registration_date FROM patients "
        "ORDER BY registration_date DESC LIMIT %s",
        (limit,),
    )


def get_daily_revenue_range(start_date: date, end_date: date) -> Dict:
    rows = execute_query(
        "SELECT bill_date::date AS bill_day, SUM(paid_amount) AS paid_amount "
        "FROM billing WHERE bill_date::date BETWEEN %s AND %s "
        "GROUP BY bill_date::date ORDER BY bill_day",
        (start_date, end_date),
    )
    return {row["bill_day"]: float(row["paid_amount"] or 0) for row in rows}


def get_patient_count() -> int:
    rows = execute_query("SELECT COUNT(*) AS c FROM patients")
    return int(rows[0]["c"]) if rows else 0


def get_patient_gender_summary() -> List[tuple]:
    rows = execute_query(
        "SELECT gender, COUNT(*) AS patient_count FROM patients GROUP BY gender"
    )
    return [(r["gender"], int(r["patient_count"])) for r in rows]


def get_patient_blood_group_summary() -> List[tuple]:
    rows = execute_query(
        "SELECT blood_group, COUNT(*) AS patient_count FROM patients "
        "WHERE blood_group IS NOT NULL GROUP BY blood_group"
    )
    return [(r["blood_group"], int(r["patient_count"])) for r in rows]


def get_patient_monthly_registrations(limit: int = 12) -> List[tuple]:
    rows = execute_query(
        "SELECT EXTRACT(YEAR FROM registration_date)::int AS yr, "
        "EXTRACT(MONTH FROM registration_date)::int AS mo, COUNT(*) AS cnt "
        "FROM patients GROUP BY yr, mo ORDER BY yr DESC, mo DESC LIMIT %s",
        (limit,),
    )
    return [(int(r["yr"]), int(r["mo"]), int(r["cnt"])) for r in rows]


def get_revenue_trend_daily(start_date: date) -> List[tuple]:
    rows = execute_query(
        "SELECT bill_date::date AS period, SUM(total_amount) AS total, SUM(paid_amount) AS paid "
        "FROM billing WHERE bill_date::date >= %s GROUP BY period ORDER BY period",
        (start_date,),
    )
    return [(str(r["period"]), float(r["total"] or 0), float(r["paid"] or 0)) for r in rows]


def get_revenue_trend_weekly(start_date: date) -> List[tuple]:
    rows = execute_query(
        "SELECT DATE_TRUNC('week', bill_date)::date AS period, "
        "SUM(total_amount) AS total, SUM(paid_amount) AS paid "
        "FROM billing WHERE bill_date >= %s GROUP BY period ORDER BY period",
        (start_date,),
    )
    return [(str(r["period"]), float(r["total"] or 0), float(r["paid"] or 0)) for r in rows]


def get_revenue_trend_monthly(limit: int = 12) -> List[tuple]:
    rows = execute_query(
        "SELECT EXTRACT(YEAR FROM bill_date)::int AS yr, "
        "EXTRACT(MONTH FROM bill_date)::int AS mo, "
        "SUM(total_amount) AS total, SUM(paid_amount) AS paid "
        "FROM billing GROUP BY yr, mo ORDER BY yr DESC, mo DESC LIMIT %s",
        (limit,),
    )
    return [(f"{int(r['yr'])}-{int(r['mo']):02d}", float(r["total"] or 0), float(r["paid"] or 0))
            for r in rows]


def get_revenue_totals() -> Dict[str, float]:
    rows = execute_query(
        "SELECT COALESCE(SUM(total_amount),0) AS total_revenue, "
        "COALESCE(SUM(CASE WHEN status='pending' THEN total_amount-paid_amount ELSE 0 END),0) AS total_pending "
        "FROM billing"
    )
    if rows:
        return {"total_revenue": float(rows[0]["total_revenue"]),
                "total_pending": float(rows[0]["total_pending"])}
    return {"total_revenue": 0, "total_pending": 0}


def get_inventory_all() -> List[SimpleNamespace]:
    rows = execute_query(
        "SELECT medicine_id, name, category, manufacturer, unit_price, "
        "stock_quantity, reorder_level, expiry_date FROM medicines ORDER BY stock_quantity"
    )
    meds = []
    for r in rows:
        m = dict_to_object(r)
        m.unit_price = float(m.unit_price or 0)
        m.stock_quantity = int(m.stock_quantity or 0)
        m.reorder_level = int(m.reorder_level or 0)
        m.is_low_stock = lambda x=m: x.stock_quantity <= x.reorder_level
        meds.append(m)
    return meds


def get_inventory_total_value() -> float:
    rows = execute_query(
        "SELECT COALESCE(SUM(unit_price * stock_quantity), 0) AS total_value FROM medicines"
    )
    return float(rows[0]["total_value"]) if rows else 0


def get_medicine_category_summary() -> List[Dict]:
    return execute_query(
        "SELECT COALESCE(category,'Uncategorized') AS category, COUNT(*) AS medicine_count, "
        "SUM(stock_quantity) AS total_stock, SUM(unit_price * stock_quantity) AS total_value "
        "FROM medicines GROUP BY COALESCE(category,'Uncategorized') ORDER BY category"
    )


def get_appointment_status_summary() -> List[tuple]:
    rows = execute_query(
        "SELECT status, COUNT(*) AS appointment_count FROM appointments GROUP BY status"
    )
    return [(r["status"], int(r["appointment_count"] or 0)) for r in rows]


def get_appointment_doctor_summary() -> List[tuple]:
    rows = execute_query(
        "SELECT d.first_name, d.last_name, COUNT(a.appointment_id) AS appointment_count "
        "FROM doctors d INNER JOIN appointments a ON a.doctor_id=d.doctor_id "
        "GROUP BY d.doctor_id, d.first_name, d.last_name"
    )
    return [(r["first_name"], r["last_name"], int(r["appointment_count"] or 0)) for r in rows]


# ── AUDIT LOG OPERATIONS ─────────────────────────────────────────────────────

def list_audit_logs(table_name: str = None, operation: str = None,
                    skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    conds, vals = ["1=1"], []
    if table_name:
        conds.append("table_name=%s"); vals.append(table_name)
    if operation:
        conds.append("operation=%s"); vals.append(operation)
    vals += [take, skip]
    rows = execute_query(
        f"SELECT * FROM audit_log WHERE {' AND '.join(conds)} "
        "ORDER BY changed_at DESC LIMIT %s OFFSET %s",
        tuple(vals),
    )
    return rows_to_objects(rows)


def count_audit_logs(table_name: str = None, operation: str = None) -> int:
    conds, vals = ["1=1"], []
    if table_name:
        conds.append("table_name=%s"); vals.append(table_name)
    if operation:
        conds.append("operation=%s"); vals.append(operation)
    rows = execute_query(
        f"SELECT COUNT(*) AS c FROM audit_log WHERE {' AND '.join(conds)}",
        tuple(vals) if vals else None,
    )
    return int(rows[0]["c"]) if rows else 0
