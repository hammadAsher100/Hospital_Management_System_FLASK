"""
Database Operations Module
Replaces SQLAlchemy ORM with raw SQL queries and stored procedures.
All functions call stored procedures and return data as dictionaries or custom objects.
"""

import re
from datetime import datetime, date, time
from typing import List, Optional, Dict, Any, Tuple
from types import SimpleNamespace
from hms import db


def _convert_named_params(sql, params):
    """Convert :name style parameters to ? positional style for pyodbc.

    pyodbc does NOT support :name parameters -- only ? placeholders.
    This helper rewrites the SQL and returns an ordered tuple of values.
    """
    if params is None:
        return sql, None
    if not isinstance(params, dict):
        # Already positional (tuple/list) -- leave as-is
        return sql, params

    ordered_values = []

    def _replacer(match):
        name = match.group(1)
        ordered_values.append(params.get(name))
        return "?"

    converted_sql = re.sub(r":(\w+)", _replacer, sql)
    return converted_sql, tuple(ordered_values) if ordered_values else None


def is_sql_server():
    """Check if using SQL Server"""
    return True


def is_sqlite():
    """Check if using SQLite"""
    return False


def is_postgres():
    """Check if using PostgreSQL"""
    return False


def execute_query(sql: str, params: Any = None, commit_after: bool = False) -> List[Dict]:
    """Execute a SQL statement and return row dicts.

    Stored procedures that perform INSERT/UPDATE must set ``commit_after=True`` so
    changes persist before the connection closes (pyodbc does not autocommit by default).
    """
    conn = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        sql, params = _convert_named_params(sql, params)
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        # SQL Server nested EXEC (e.g. usp_RecordPayment calling usp_RefreshBillTotals) can yield
        # multiple sequential result sets. We must iterate with nextset() and keep the latest
        # nonempty SELECT so pyodbc/ODBC completes the batch reliably and callers still get
        # the typical final result row (e.g. SCOPE_IDENTITY / success bit).
        rows_out: List[Dict] = []
        while True:
            if cursor.description is not None:
                columns = [column[0] for column in cursor.description]
                batch = [dict(zip(columns, row)) for row in cursor.fetchall()]
                if batch:
                    rows_out = batch
            try:
                if not cursor.nextset():
                    break
            except Exception:
                break

        cursor.close()
        if commit_after:
            conn.commit()
        return rows_out
    except Exception as e:
        print(f"Query Error: {str(e)}")
        if conn and commit_after:
            try:
                conn.rollback()
            except Exception:
                pass
        return []
    finally:
        if conn:
            conn.close()


def execute_procedure(procedure_name: str, params: Dict[str, Any] = None) -> List[Dict]:
    """Execute stored procedure and return results"""
    params = params or {}
    
    # SQL Server: EXEC procedure_name @param1=?, @param2=?
    placeholders = ", ".join(f"@{key}=?" for key in params.keys())
    sql = f"EXEC {procedure_name}" + (f" {placeholders}" if placeholders else "")
    
    # Convert to tuple for pyodbc
    param_tuple = tuple(params.values()) if params else None
    
    return execute_query(sql, param_tuple, commit_after=True)


def execute_update(sql: str, params: Any = None) -> bool:
    """Execute INSERT/UPDATE/DELETE query"""
    conn = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        sql, params = _convert_named_params(sql, params)
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Update Error: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def execute_insert(sql: str, params: Any = None) -> Optional[int]:
    """Execute INSERT query and return the new ID"""
    conn = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        sql, params = _convert_named_params(sql, params)
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        # If the INSERT used OUTPUT clause, read that result first
        if cursor.description:
            row = cursor.fetchone()
            conn.commit()
            cursor.close()
            return int(row[0]) if row and row[0] is not None else None

        conn.commit()
        # Fallback: SCOPE_IDENTITY()
        cursor.execute("SELECT SCOPE_IDENTITY() as id")
        row = cursor.fetchone()
        cursor.close()
        return int(row[0]) if row and row[0] is not None else None
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Insert Error: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()


def rows_to_objects(rows: List[Dict]) -> List[SimpleNamespace]:
    """Convert list of dictionaries to SimpleNamespace objects"""
    return [SimpleNamespace(**row) for row in rows]


def dict_to_object(row_dict: Dict) -> SimpleNamespace:
    """Convert dictionary to SimpleNamespace object"""
    if not row_dict:
        return None
    return SimpleNamespace(**row_dict)


# ============================================================
# USER OPERATIONS
# ============================================================

def get_user_by_username(username: str) -> Optional[SimpleNamespace]:
    """Get user by username"""
    rows = execute_procedure("usp_GetUserByUsername", {"username": username})
    return dict_to_object(rows[0]) if rows else None


def get_user_by_email(email: str) -> Optional[SimpleNamespace]:
    """Get user by email (direct query)."""
    if not email:
        return None
    rows = execute_query(
        "SELECT user_id, username, password_hash, role, email, full_name, created_at, last_login, is_active FROM Users WHERE email = ?",
        (email,),
    )
    return dict_to_object(rows[0]) if rows else None


def get_user_by_id(user_id: int) -> Optional[SimpleNamespace]:
    """Get user by ID"""
    rows = execute_procedure("usp_GetUserById", {"user_id": user_id})
    return dict_to_object(rows[0]) if rows else None


def create_user(username: str, password_hash: str, role: str, email: str, full_name: str) -> Optional[int]:
    """Create new user and return user_id"""
    rows = execute_procedure("usp_CreateUser", {
        "username": username,
        "password_hash": password_hash,
        "role": role,
        "email": email,
        "full_name": full_name
    })
    return int(rows[0]["id"]) if rows else None


def update_last_login(user_id: int) -> bool:
    """Update user's last login timestamp"""
    return bool(execute_procedure("usp_UpdateLastLogin", {"user_id": user_id}))


def update_user_profile(user_id: int, full_name: str, email: str) -> bool:
    """Update user profile basics"""
    rows = execute_procedure(
        "usp_UpdateUserProfile",
        {"user_id": user_id, "full_name": full_name, "email": email},
    )
    return bool(rows)


def update_user_password_hash(user_id: int, password_hash: str) -> bool:
    """Update user password hash"""
    rows = execute_procedure(
        "usp_UpdateUserPasswordHash",
        {"user_id": user_id, "password_hash": password_hash},
    )
    return bool(rows)


# ============================================================
# PATIENT OPERATIONS
# ============================================================

def get_patient_by_id(patient_id: int) -> Optional[SimpleNamespace]:
    """Get patient by ID"""
    rows = execute_procedure("usp_GetPatientById", {"patient_id": patient_id})
    if rows:
        p = dict_to_object(rows[0])
        p.dob = p.dob if isinstance(p.dob, date) else datetime.strptime(str(p.dob), "%Y-%m-%d").date()
        return p
    return None


def get_patient_by_user_id(user_id: int) -> Optional[SimpleNamespace]:
    """Get patient by user ID"""
    rows = execute_procedure("usp_GetPatientByUserId", {"user_id": user_id})
    if rows:
        p = dict_to_object(rows[0])
        p.dob = p.dob if isinstance(p.dob, date) else datetime.strptime(str(p.dob), "%Y-%m-%d").date()
        return p
    return None


def list_patients(skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    """List all patients with pagination"""
    rows = execute_procedure("usp_ListPatients", {"skip": skip, "take": take})
    patients = []
    for row in rows:
        p = dict_to_object(row)
        p.dob = p.dob if isinstance(p.dob, date) else datetime.strptime(str(p.dob), "%Y-%m-%d").date()
        patients.append(p)
    return patients


def create_patient(first_name: str, last_name: str, dob: date, gender: str, phone: str,
                  user_id: int = None, email: str = None, address: str = None,
                  emergency_contact: str = None, blood_group: str = None, allergies: str = None) -> Optional[int]:
    """Create new patient and return patient_id"""
    rows = execute_procedure("usp_CreatePatient", {
        "user_id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "gender": gender,
        "phone": phone,
        "email": email,
        "address": address,
        "emergency_contact": emergency_contact,
        "blood_group": blood_group,
        "allergies": allergies
    })
    return int(rows[0]["id"]) if rows else None


def update_patient(patient_id: int, first_name: str, last_name: str, phone: str,
                  email: str = None, address: str = None, emergency_contact: str = None,
                  blood_group: str = None, allergies: str = None) -> bool:
    """Update patient information"""
    return bool(execute_procedure("usp_UpdatePatient", {
        "patient_id": patient_id,
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "email": email,
        "address": address,
        "emergency_contact": emergency_contact,
        "blood_group": blood_group,
        "allergies": allergies
    }))


def update_patient_full(patient_id: int, first_name: str, last_name: str, dob: date,
                        gender: str, phone: str, email: str = None, address: str = None,
                        emergency_contact: str = None, blood_group: str = None,
                        allergies: str = None) -> bool:
    """Update all patient fields including dob and gender (staff-facing edit)"""
    return bool(execute_procedure("usp_UpdatePatientFull", {
        "patient_id": patient_id,
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "gender": gender,
        "phone": phone,
        "email": email,
        "address": address,
        "emergency_contact": emergency_contact,
        "blood_group": blood_group,
        "allergies": allergies
    }))


def delete_patient(patient_id: int) -> bool:
    """Delete a patient record"""
    return bool(execute_procedure("usp_DeletePatient", {"patient_id": patient_id}))


def search_patients_count(search: str = None) -> int:
    """Count patients matching search term"""
    rows = execute_procedure("usp_SearchPatientsCount", {"search": search})
    return int(rows[0]["total_count"]) if rows else 0


def search_patients(search: str = None, skip: int = 0, take: int = 15) -> List[SimpleNamespace]:
    """Search patients with pagination (includes full_name and age)"""
    rows = execute_procedure("usp_SearchPatients", {"search": search, "skip": skip, "take": take})
    patients = []
    for row in rows:
        p = dict_to_object(row)
        p.dob = p.dob if isinstance(p.dob, date) else datetime.strptime(str(p.dob), "%Y-%m-%d").date()
        patients.append(p)
    return patients


def update_patient_profile(patient_id: int, user_id: int, email: str = None, phone: str = None,
                           address: str = None, emergency_contact: str = None,
                           blood_group: str = None, allergies: str = None) -> bool:
    """Update patient profile (patient-facing self-edit, also updates Users.email)"""
    return bool(execute_procedure("usp_UpdatePatientProfile", {
        "patient_id": patient_id,
        "user_id": user_id,
        "email": email,
        "phone": phone,
        "address": address,
        "emergency_contact": emergency_contact,
        "blood_group": blood_group,
        "allergies": allergies
    }))


def get_patient_dashboard_stats(patient_id: int) -> Dict[str, int]:
    """Get patient appointment statistics (total + completed)"""
    rows = execute_procedure("usp_GetPatientDashboardStats", {"patient_id": patient_id})
    if rows:
        return {
            "total_appointments": int(rows[0].get("total_appointments") or 0),
            "completed_appointments": int(rows[0].get("completed_appointments") or 0),
        }
    return {"total_appointments": 0, "completed_appointments": 0}


# ============================================================
# APPOINTMENT OPERATIONS
# ============================================================

def check_appointment_conflict(doctor_id: int, appointment_date: date, appointment_time: time, exclude_id: int = None) -> bool:
    """Check if appointment time slot is available"""
    rows = execute_procedure("usp_CheckAppointmentConflict", {
        "doctor_id": doctor_id,
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "exclude_id": exclude_id
    })
    return bool(rows and rows[0].get("has_conflict", 0))


def get_doctor_booked_slots(doctor_id: int, appointment_date: date) -> List[str]:
    """Get booked appointment times for a doctor on a specific date"""
    rows = execute_procedure("usp_GetDoctorBookedSlots", {
        "doctor_id": doctor_id,
        "appointment_date": appointment_date
    })
    return [str(row["appointment_time"])[:5] for row in rows]


def get_doctor_schedule_by_day(doctor_id: int, day_of_week: int) -> Optional[SimpleNamespace]:
    """Get one doctor's schedule row for a specific weekday"""
    rows = execute_procedure("usp_GetDoctorScheduleByDay", {
        "doctor_id": doctor_id,
        "day_of_week": day_of_week
    })
    if not rows:
        return None
    schedule = dict_to_object(rows[0])
    schedule.start_time = datetime.strptime(str(schedule.start_time)[:8], "%H:%M:%S").time()
    schedule.end_time = datetime.strptime(str(schedule.end_time)[:8], "%H:%M:%S").time()
    return schedule


def count_appointments(status: str = None, doctor_id: int = None, patient_id: int = None,
                      appointment_date: date = None) -> int:
    """Count appointments with optional filters"""
    rows = execute_procedure("usp_CountAppointments", {
        "status": status,
        "doctor_id": doctor_id,
        "patient_id": patient_id,
        "appointment_date": appointment_date
    })
    return int(rows[0]["total_count"]) if rows else 0


def list_appointments(status: str = None, doctor_id: int = None, patient_id: int = None,
                     appointment_date: date = None, skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    """List appointments with optional filters"""
    rows = execute_procedure("usp_ListAppointments", {
        "status": status,
        "doctor_id": doctor_id,
        "patient_id": patient_id,
        "appointment_date": appointment_date,
        "skip": skip,
        "take": take
    })
    appointments = []
    for row in rows:
        appt = dict_to_object(row)
        appt.appointment_date = appt.appointment_date if isinstance(appt.appointment_date, date) else datetime.strptime(str(appt.appointment_date), "%Y-%m-%d").date()
        if hasattr(appt, "appointment_time"):
            raw_time = str(appt.appointment_time)
            if ":" in raw_time:
                appt.appointment_time = datetime.strptime(raw_time[:8], "%H:%M:%S").time()
        appointments.append(appt)
    return appointments


def get_appointment_by_id(appointment_id: int) -> Optional[SimpleNamespace]:
    """Get appointment by ID"""
    rows = execute_procedure("usp_GetAppointmentById", {"appointment_id": appointment_id})
    if rows:
        appt = dict_to_object(rows[0])
        appt.appointment_date = appt.appointment_date if isinstance(appt.appointment_date, date) else datetime.strptime(str(appt.appointment_date), "%Y-%m-%d").date()
        return appt
    return None


def create_appointment(patient_id: int, doctor_id: int, appointment_date: date, 
                      appointment_time: time, reason: str = None) -> Optional[int]:
    """Create new appointment"""
    rows = execute_procedure("usp_CreateAppointment", {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "reason": reason
    })
    return int(rows[0]["id"]) if rows else None


def update_appointment_status(appointment_id: int, status: str, notes: str = None) -> bool:
    """Update appointment status (scheduled, completed, cancelled)"""
    return bool(execute_procedure("usp_UpdateAppointmentStatus", {
        "appointment_id": appointment_id,
        "status": status,
        "notes": notes
    }))


def reschedule_appointment(appointment_id: int, new_date: date, new_time: time) -> bool:
    """Reschedule appointment to new date and time"""
    return bool(execute_procedure("usp_RescheduleAppointment", {
        "appointment_id": appointment_id,
        "new_date": new_date,
        "new_time": new_time
    }))


# ============================================================
# DOCTOR OPERATIONS
# ============================================================

def get_doctor_by_id(doctor_id: int) -> Optional[SimpleNamespace]:
    """Get doctor by ID"""
    rows = execute_procedure("usp_GetDoctorById", {"doctor_id": doctor_id})
    return dict_to_object(rows[0]) if rows else None


def get_doctor_by_user_id(user_id: int) -> Optional[SimpleNamespace]:
    """Get doctor by user ID"""
    rows = execute_procedure("usp_GetDoctorByUserId", {"user_id": user_id})
    return dict_to_object(rows[0]) if rows else None


def list_active_doctors() -> List[SimpleNamespace]:
    """List all active doctors"""
    rows = execute_procedure("usp_ListActiveDoctors")
    return rows_to_objects(rows)


def list_doctors() -> List[SimpleNamespace]:
    rows = execute_procedure("usp_ListDoctors")
    return rows_to_objects(rows)


def create_doctor_with_user(username: str, password_hash: str, email: str, first_name: str, last_name: str,
                            specialization: str, phone: str = None, consultation_fee: float = 0) -> Optional[int]:
    rows = execute_procedure("usp_CreateDoctorWithUser", {
        "username": username,
        "password_hash": password_hash,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "specialization": specialization,
        "phone": phone,
        "consultation_fee": consultation_fee
    })
    return int(rows[0]["id"]) if rows else None


def list_nurses() -> List[SimpleNamespace]:
    rows = execute_procedure("usp_ListNurses")
    return rows_to_objects(rows)


def get_nurse_by_user_id(user_id: int) -> Optional[SimpleNamespace]:
    rows = execute_procedure("usp_GetNurseByUserId", {"user_id": user_id})
    return dict_to_object(rows[0]) if rows else None


def create_nurse_with_user(username: str, password_hash: str, email: str, first_name: str, last_name: str,
                           phone: str = None, assigned_ward: str = None) -> Optional[int]:
    rows = execute_procedure("usp_CreateNurseWithUser", {
        "username": username,
        "password_hash": password_hash,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "assigned_ward": assigned_ward
    })
    return int(rows[0]["id"]) if rows else None


def list_users() -> List[SimpleNamespace]:
    return rows_to_objects(execute_procedure("usp_ListUsers"))


def toggle_user_active(user_id: int) -> Optional[SimpleNamespace]:
    rows = execute_procedure("usp_ToggleUserActive", {"user_id": user_id})
    return dict_to_object(rows[0]) if rows else None


def list_doctor_schedules(doctor_id: int) -> List[SimpleNamespace]:
    return rows_to_objects(execute_procedure("usp_ListDoctorSchedules", {"doctor_id": doctor_id}))


def clear_doctor_schedules(doctor_id: int) -> bool:
    return bool(execute_procedure("usp_ClearDoctorSchedules", {"doctor_id": doctor_id}))


def add_doctor_schedule(doctor_id: int, day_of_week: int, start_time: time, end_time: time, max_appointments: int = 10) -> bool:
    return bool(execute_procedure("usp_AddDoctorSchedule", {
        "doctor_id": doctor_id,
        "day_of_week": day_of_week,
        "start_time": start_time,
        "end_time": end_time,
        "max_appointments": max_appointments
    }))


def count_recent_unique_patients(days: int = 30) -> int:
    rows = execute_procedure("usp_CountRecentUniquePatients", {"days": days})
    return int(rows[0]["total_count"]) if rows else 0


# ============================================================
# MEDICINE OPERATIONS
# ============================================================

def get_medicine_by_id(medicine_id: int) -> Optional[SimpleNamespace]:
    """Get medicine by ID"""
    rows = execute_procedure("usp_GetMedicineById", {"medicine_id": medicine_id})
    return dict_to_object(rows[0]) if rows else None


def list_medicines(search: str = None, category: str = None, skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    """List medicines with optional search and category filter"""
    rows = execute_procedure("usp_ListMedicines", {
        "search": search,
        "category": category,
        "skip": skip,
        "take": take
    })
    return rows_to_objects(rows)


def count_medicines(search: str = None, category: str = None) -> int:
    """Count medicines with optional filters"""
    rows = execute_procedure("usp_CountMedicines", {"search": search, "category": category})
    return int(rows[0]["total_count"]) if rows else 0


def list_medicine_categories() -> List[str]:
    """List distinct medicine categories"""
    rows = execute_procedure("usp_ListMedicineCategories")
    return [r["category"] for r in rows if r.get("category")]


def create_medicine(name: str, unit_price: float, category: str = None, manufacturer: str = None,
                   stock_quantity: int = 0, reorder_level: int = 10, expiry_date: date = None) -> Optional[int]:
    """Create new medicine"""
    rows = execute_procedure("usp_CreateMedicine", {
        "name": name,
        "category": category,
        "manufacturer": manufacturer,
        "unit_price": unit_price,
        "stock_quantity": stock_quantity,
        "reorder_level": reorder_level,
        "expiry_date": expiry_date
    })
    return int(rows[0]["id"]) if rows else None


def update_medicine(medicine_id: int, name: str, unit_price: float, category: str = None,
                   manufacturer: str = None, reorder_level: int = 10, expiry_date: date = None) -> bool:
    """Update medicine information"""
    return bool(execute_procedure("usp_UpdateMedicine", {
        "medicine_id": medicine_id,
        "name": name,
        "category": category,
        "manufacturer": manufacturer,
        "unit_price": unit_price,
        "reorder_level": reorder_level,
        "expiry_date": expiry_date
    }))


def update_medicine_stock(medicine_id: int, quantity_change: int) -> bool:
    """Update medicine stock (positive or negative)"""
    return bool(execute_procedure("usp_UpdateMedicineStock", {
        "medicine_id": medicine_id,
        "quantity": quantity_change
    }))


def get_low_stock_medicines() -> List[SimpleNamespace]:
    """Get medicines with low stock"""
    rows = execute_procedure("usp_GetLowStockMedicines")
    return rows_to_objects(rows)


# ============================================================
# BILLING OPERATIONS
# ============================================================

def get_bill_by_id(bill_id: int) -> Optional[SimpleNamespace]:
    """Get bill by ID"""
    rows = execute_procedure("usp_GetBillById", {"bill_id": bill_id})
    return dict_to_object(rows[0]) if rows else None


def get_bill_by_appointment_id(appointment_id: int) -> Optional[SimpleNamespace]:
    """Get bill by appointment ID"""
    rows = execute_procedure("usp_GetBillByAppointmentId", {"appointment_id": appointment_id})
    return dict_to_object(rows[0]) if rows else None


def count_bills(patient_id: int = None, status: str = None) -> int:
    """Count bills with optional filters"""
    rows = execute_procedure("usp_CountBills", {"patient_id": patient_id, "status": status})
    return int(rows[0]["total_count"]) if rows else 0


def list_bills(patient_id: int = None, status: str = None, skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    """List bills with optional filters"""
    rows = execute_procedure("usp_ListBills", {
        "patient_id": patient_id,
        "status": status,
        "skip": skip,
        "take": take
    })
    bills = []
    for row in rows:
        bill = dict_to_object(row)
        bill.bill_date = bill.bill_date if isinstance(bill.bill_date, datetime) else datetime.strptime(str(bill.bill_date), "%Y-%m-%d %H:%M:%S")
        bills.append(bill)
    return bills


def get_bill_items(bill_id: int) -> List[SimpleNamespace]:
    """Get bill items by bill id"""
    rows = execute_procedure("usp_ListBillItems", {"bill_id": bill_id})
    return rows_to_objects(rows)


def refresh_bill_totals(bill_id: int) -> bool:
    """Recalculate bill total/status from line items"""
    return bool(execute_procedure("usp_RefreshBillTotals", {"bill_id": bill_id}))


def create_bill(patient_id: int, appointment_id: int = None, admission_id: int = None,
               payment_method: str = None, total_amount: float = 0) -> Optional[int]:
    """Create new bill"""
    rows = execute_procedure("usp_CreateBill", {
        "patient_id": patient_id,
        "appointment_id": appointment_id,
        "admission_id": admission_id,
        "payment_method": payment_method,
        "total_amount": total_amount
    })
    return int(rows[0]["id"]) if rows else None


def add_bill_item(bill_id: int, description: str, quantity: int, unit_price: float) -> Optional[int]:
    """Add item to bill"""
    rows = execute_procedure("usp_AddBillItem", {
        "bill_id": bill_id,
        "description": description,
        "quantity": quantity,
        "unit_price": unit_price
    })
    return int(rows[0]["id"]) if rows else None


def record_payment(bill_id: int, payment_amount: float, payment_method: str) -> bool:
    """Record payment for a bill"""
    return bool(execute_procedure("usp_RecordPayment", {
        "bill_id": bill_id,
        "payment_amount": payment_amount,
        "payment_method": payment_method
    }))


def list_completed_appointments(patient_id: int = None, skip: int = 0, take: int = 100) -> List[SimpleNamespace]:
    """List completed appointments, optional patient filter"""
    rows = execute_procedure("usp_ListCompletedAppointments", {
        "patient_id": patient_id,
        "skip": skip,
        "take": take
    })
    appointments = []
    for row in rows:
        appt = dict_to_object(row)
        appt.appointment_date = appt.appointment_date if isinstance(appt.appointment_date, date) else datetime.strptime(str(appt.appointment_date), "%Y-%m-%d").date()
        if hasattr(appt, "appointment_time"):
            raw_time = str(appt.appointment_time)
            if ":" in raw_time:
                appt.appointment_time = datetime.strptime(raw_time[:8], "%H:%M:%S").time()
        appointments.append(appt)
    return appointments


# ============================================================
# ADMISSION OPERATIONS
# ============================================================

def get_admission_by_id(admission_id: int) -> Optional[SimpleNamespace]:
    """Get admission by ID"""
    rows = execute_procedure("usp_GetAdmissionById", {"admission_id": admission_id})
    return dict_to_object(rows[0]) if rows else None


def list_active_admissions(skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    """List active admissions"""
    rows = execute_procedure("usp_ListActiveAdmissions", {"skip": skip, "take": take})
    return rows_to_objects(rows)


def create_admission(patient_id: int, doctor_id: int, nurse_id: int = None,
                    room_number: str = None, diagnosis: str = None) -> Optional[int]:
    """Create new admission"""
    rows = execute_procedure("usp_CreateAdmission", {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "nurse_id": nurse_id,
        "room_number": room_number,
        "diagnosis": diagnosis
    })
    return int(rows[0]["id"]) if rows else None


def discharge_patient(admission_id: int) -> bool:
    """Discharge a patient from admission"""
    return bool(execute_procedure("usp_DischargePatient", {"admission_id": admission_id}))


# ============================================================
# PRESCRIPTION OPERATIONS
# ============================================================

def get_prescription_by_id(prescription_id: int) -> Optional[SimpleNamespace]:
    """Get prescription by ID"""
    rows = execute_procedure("usp_GetPrescriptionById", {"prescription_id": prescription_id})
    return dict_to_object(rows[0]) if rows else None


def list_prescriptions(patient_id: int = None, doctor_id: int = None, is_dispensed: bool = None,
                      skip: int = 0, take: int = 50) -> List[SimpleNamespace]:
    """List prescriptions with optional filters"""
    rows = execute_procedure("usp_ListPrescriptions", {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "is_dispensed": is_dispensed,
        "skip": skip,
        "take": take
    })
    return rows_to_objects(rows)


def count_prescriptions(patient_id: int = None, doctor_id: int = None, is_dispensed: bool = None) -> int:
    """Count prescriptions with optional filters"""
    rows = execute_procedure("usp_CountPrescriptions", {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "is_dispensed": is_dispensed
    })
    return int(rows[0]["total_count"]) if rows else 0


def get_prescription_items(prescription_id: int) -> List[SimpleNamespace]:
    """Get prescription line items with medicine names"""
    rows = execute_procedure("usp_ListPrescriptionItems", {"prescription_id": prescription_id})
    return rows_to_objects(rows)


def create_prescription(patient_id: int, doctor_id: int, appointment_id: int = None, notes: str = None) -> Optional[int]:
    """Create new prescription"""
    rows = execute_procedure("usp_CreatePrescription", {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "appointment_id": appointment_id,
        "notes": notes
    })
    return int(rows[0]["id"]) if rows else None


def add_prescription_item(prescription_id: int, medicine_id: int, dosage: str, 
                         frequency: str, duration: str, quantity: int = 1) -> Optional[int]:
    """Add medicine to prescription"""
    rows = execute_procedure("usp_AddPrescriptionItem", {
        "prescription_id": prescription_id,
        "medicine_id": medicine_id,
        "dosage": dosage,
        "frequency": frequency,
        "duration": duration,
        "quantity": quantity
    })
    return int(rows[0]["id"]) if rows else None


def mark_prescription_dispensed(prescription_id: int) -> bool:
    """Mark prescription as dispensed"""
    return bool(execute_procedure("usp_MarkPrescriptionDispensed", {"prescription_id": prescription_id}))


# ============================================================
# ADMIN REPORT OPERATIONS
# ============================================================

def get_admin_dashboard_metrics(today: date) -> Dict[str, Any]:
    """Get all dashboard metrics in a single call"""
    rows = execute_procedure("usp_GetAdminDashboardMetrics", {"today": today})
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
    return {
        "total_patients": 0, "today_appointments": 0, "active_admissions": 0,
        "low_stock_count": 0, "monthly_revenue": 0, "pending_bills_count": 0,
    }


def get_dashboard_today_appointments(today: date, limit: int = 5) -> List[Dict]:
    """Get today's appointments for admin dashboard"""
    rows = execute_query(
        f"SELECT TOP({limit}) patient_id, appointment_time, status, patient_name, doctor_name "
        "FROM dbo.vw_TodayAppointmentsDetailed "
        "WHERE appointment_date = :today ORDER BY appointment_time",
        {"today": today},
    )
    return rows


def get_dashboard_recent_patients(limit: int = 5) -> List[Dict]:
    """Get recently registered patients for admin dashboard"""
    rows = execute_query(
        f"SELECT TOP({limit}) patient_id, full_name, gender, phone, registration_date "
        "FROM dbo.vw_RecentPatients ORDER BY registration_date DESC",
    )
    return rows


def get_daily_revenue_range(start_date: date, end_date: date) -> Dict:
    """Get daily revenue between date range"""
    rows = execute_query(
        "SELECT bill_day, paid_amount FROM dbo.vw_DailyRevenue "
        "WHERE bill_day BETWEEN :start_day AND :end_day",
        {"start_day": start_date, "end_day": end_date},
    )
    return {row["bill_day"]: float(row["paid_amount"] or 0) for row in rows}


def get_patient_count() -> int:
    """Get total patient count"""
    rows = execute_procedure("usp_GetPatientCount")
    return int(rows[0]["total_count"]) if rows else 0


def get_patient_gender_summary() -> List[tuple]:
    """Get patient counts by gender"""
    rows = execute_procedure("usp_GetPatientGenderSummary")
    return [(r["gender"], int(r["patient_count"])) for r in rows]


def get_patient_blood_group_summary() -> List[tuple]:
    """Get patient counts by blood group"""
    rows = execute_procedure("usp_GetPatientBloodGroupSummary")
    return [(r["blood_group"], int(r["patient_count"])) for r in rows]


def get_patient_monthly_registrations(limit: int = 12) -> List[tuple]:
    """Get monthly patient registration counts"""
    rows = execute_procedure("usp_GetPatientMonthlyRegistrations", {"limit": limit})
    return [(int(r["yr"]), int(r["mo"]), int(r["cnt"])) for r in rows]


def get_revenue_trend_daily(start_date: date) -> List[tuple]:
    """Get daily revenue trend"""
    rows = execute_procedure("usp_GetRevenueTrendDaily", {"start_date": start_date})
    return [(str(r["period"]), float(r["total"] or 0), float(r["paid"] or 0)) for r in rows]


def get_revenue_trend_weekly(start_date: date) -> List[tuple]:
    """Get weekly revenue trend"""
    rows = execute_procedure("usp_GetRevenueTrendWeekly", {"start_date": start_date})
    return [(str(r["period"]), float(r["total"] or 0), float(r["paid"] or 0)) for r in rows]


def get_revenue_trend_monthly(limit: int = 12) -> List[tuple]:
    """Get monthly revenue trend"""
    rows = execute_procedure("usp_GetRevenueTrendMonthly", {"limit": limit})
    return [(f"{int(r['yr'])}-{int(r['mo']):02d}", float(r["total"] or 0), float(r["paid"] or 0)) for r in rows]


def get_revenue_totals() -> Dict[str, float]:
    """Get total revenue and total pending amounts"""
    rows = execute_procedure("usp_GetRevenueTotals")
    if rows:
        return {
            "total_revenue": float(rows[0]["total_revenue"] or 0),
            "total_pending": float(rows[0]["total_pending"] or 0),
        }
    return {"total_revenue": 0, "total_pending": 0}


def get_inventory_all() -> List[SimpleNamespace]:
    """List all medicines ordered by stock quantity"""
    rows = execute_procedure("usp_GetInventoryAll")
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
    """Get total inventory value"""
    rows = execute_procedure("usp_GetInventoryTotalValue")
    return float(rows[0]["total_value"]) if rows else 0


def get_medicine_category_summary() -> List[tuple]:
    """Get medicine counts and stock by category using the view"""
    rows = execute_query(
        "SELECT category, medicine_count, total_stock, total_value "
        "FROM dbo.vw_MedicineCategorySummary ORDER BY category"
    )
    return rows


def get_appointment_status_summary() -> List[tuple]:
    """Get appointment counts by status using the view"""
    rows = execute_query(
        "SELECT status, appointment_count FROM dbo.vw_AppointmentStatusSummary"
    )
    return [(r["status"], int(r["appointment_count"] or 0)) for r in rows]


def get_appointment_doctor_summary() -> List[tuple]:
    """Get appointment counts by doctor using the view"""
    rows = execute_query(
        "SELECT first_name, last_name, appointment_count FROM dbo.vw_AppointmentDoctorSummary"
    )
    return [(r["first_name"], r["last_name"], int(r["appointment_count"] or 0)) for r in rows]
