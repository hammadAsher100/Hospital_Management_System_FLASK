"""Patient model — CRUD, profile management, dashboard data, registration."""

from datetime import datetime, date
from hms import db_operations
from hms.db_queries import fetch_rows, exec_procedure, is_sql_server, rows_to_objects
from hms.utils.exceptions import ValidationError


class Patient:
    """Patient model with business logic for registration, profile, and data retrieval."""

    def __init__(self, patient_id: int, user_id: int = None, first_name: str = None,
                 last_name: str = None, dob: date = None, gender: str = None,
                 phone: str = None, email: str = None, address: str = None,
                 emergency_contact: str = None, blood_group: str = None,
                 allergies: str = None, registration_date: datetime = None):
        self.patient_id = patient_id
        self.user_id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.dob = _parse_date(dob) if dob else None
        self.gender = gender
        self.phone = phone
        self.email = email
        self.address = address
        self.emergency_contact = emergency_contact
        self.blood_group = blood_group
        self.allergies = allergies
        self.registration_date = registration_date or datetime.utcnow()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        if not self.dob:
            return 0
        today = date.today()
        return today.year - self.dob.year - (
            (today.month, today.day) < (self.dob.month, self.dob.day)
        )

    def __repr__(self):
        return f'<Patient {self.full_name}>'

    # ── CRUD ────────────────────────────────────────────────

    @staticmethod
    def register(first_name: str, last_name: str, dob: date, gender: str, phone: str,
                 user_id: int = None, email: str = None, address: str = None,
                 emergency_contact: str = None, blood_group: str = None,
                 allergies: str = None) -> int:
        """Register a new patient. Returns patient_id. Raises on failure."""
        patient_id = db_operations.create_patient(
            first_name=first_name, last_name=last_name, dob=dob, gender=gender,
            phone=phone, user_id=user_id, email=email, address=address,
            emergency_contact=emergency_contact, blood_group=blood_group,
            allergies=allergies,
        )
        if not patient_id:
            raise ValidationError('Error creating patient profile.')
        return patient_id

    @staticmethod
    def signup(username: str, email: str, password: str, confirm_password: str,
               first_name: str, last_name: str, phone: str, dob_str: str, gender: str):
        """Full patient sign-up (user account + patient profile).

        Returns (user_id, patient_id). Raises ValidationError on failure.
        """
        if not all([username, email, password, first_name, last_name, phone, dob_str, gender]):
            raise ValidationError('All fields are required.')
        if password != confirm_password:
            raise ValidationError('Passwords do not match.')
        if len(password) < 6:
            raise ValidationError('Password must be at least 6 characters.')

        try:
            dob_value = datetime.strptime(dob_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError('Invalid date of birth.')

        if dob_value > date.today():
            raise ValidationError('Date of birth cannot be in the future.')

        from hms.models.user import User
        user_id = User.create_account(
            username=username, email=email, password=password,
            confirm_password=confirm_password,
            full_name=f"{first_name} {last_name}", role='patient',
        )

        patient_id = Patient.register(
            user_id=user_id, first_name=first_name, last_name=last_name,
            phone=phone, email=email, dob=dob_value, gender=gender,
        )
        return user_id, patient_id

    def update(self, first_name: str, last_name: str, phone: str,
               email: str = None, address: str = None, emergency_contact: str = None,
               blood_group: str = None, allergies: str = None, dob: date = None,
               gender: str = None):
        """Update patient information. Raises ValidationError on failure."""
        success = db_operations.update_patient(
            patient_id=self.patient_id, first_name=first_name, last_name=last_name,
            phone=phone, email=email, address=address,
            emergency_contact=emergency_contact, blood_group=blood_group,
            allergies=allergies,
        )
        if not success:
            raise ValidationError('Error updating patient.')

    def update_profile(self, email: str = None, phone: str = None, address: str = None,
                       emergency_contact: str = None, blood_group: str = None,
                       allergies: str = None):
        """Update profile fields (patient-facing)."""
        from hms import db
        from hms.db_queries import _convert_named_params
        conn = None
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            sql = """
                UPDATE Patients SET email=:email, phone=:phone, address=:address,
                    emergency_contact=:emergency_contact, blood_group=:blood_group,
                    allergies=:allergies
                WHERE patient_id=:id
            """
            params = {
                "id": self.patient_id, "email": email, "phone": phone,
                "address": address, "emergency_contact": emergency_contact,
                "blood_group": blood_group, "allergies": allergies,
            }
            sql, params = _convert_named_params(sql, params)
            cursor.execute(sql, params) if params else cursor.execute(sql)
            conn.commit()
            cursor.close()
        finally:
            if conn:
                conn.close()

        # Also update the Users table email
        from hms import db as db_inst
        conn2 = None
        try:
            conn2 = db_inst.get_connection()
            cursor2 = conn2.cursor()
            sql2 = "UPDATE Users SET email=? WHERE user_id=?"
            cursor2.execute(sql2, (email, self.user_id))
            conn2.commit()
            cursor2.close()
        finally:
            if conn2:
                conn2.close()

    @staticmethod
    def delete(patient_id: int):
        """Delete a patient record. Raises on failure."""
        from hms import db
        conn = None
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Patients WHERE patient_id = ?", (patient_id,))
            conn.commit()
            cursor.close()
        except Exception as e:
            if conn:
                conn.rollback()
            raise ValidationError(f'Cannot delete patient: {e}')
        finally:
            if conn:
                conn.close()

    # ── Lookups ─────────────────────────────────────────────

    @staticmethod
    def get_by_id(patient_id: int) -> 'Patient':
        """Get patient by ID using rich SQL query with age calculation."""
        rows = fetch_rows(_patient_select("p.patient_id = :patient_id"), {"patient_id": patient_id})
        return _map_row_to_patient(rows[0]) if rows else None

    @staticmethod
    def get_by_user_id(user_id: int) -> 'Patient':
        """Get patient by user ID."""
        rows = fetch_rows(_patient_select("p.user_id = :user_id"), {"user_id": user_id})
        return _map_row_to_patient(rows[0]) if rows else None

    @staticmethod
    def list_paginated(search: str = '', page: int = 1, per_page: int = 15):
        """List patients with search and pagination.

        Returns (patients_list, total_count).
        """
        offset = (page - 1) * per_page
        where = ""
        count_params = None
        page_params = None

        if search:
            where = "WHERE p.first_name LIKE ? OR p.last_name LIKE ? OR p.phone LIKE ? OR p.email LIKE ?"
            search_param = f"%{search}%"
            count_params = (search_param, search_param, search_param, search_param)
            page_params = (search_param, search_param, search_param, search_param, offset, per_page)
        else:
            page_params = (offset, per_page)

        total = int(fetch_rows(f"SELECT COUNT(*) AS total FROM Patients p {where}", count_params)[0]["total"])

        if is_sql_server():
            sql = """
                SELECT p.*, CONCAT(p.first_name, ' ', p.last_name) AS full_name, dbo.ufn_CalculateAge(p.dob) AS age
                FROM Patients p
                {where}
                ORDER BY p.registration_date DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """.format(where=where)
        else:
            sql = """
                SELECT p.*, (p.first_name || ' ' || p.last_name) AS full_name
                FROM Patients p
                {where}
                ORDER BY p.registration_date DESC
                LIMIT ? OFFSET ?
            """.format(where=where)
            page_params = (per_page, offset)

        rows = fetch_rows(sql, page_params)
        patients = [_map_row_to_patient(r) for r in rows]
        return patients, total

    @staticmethod
    def list_all(skip: int = 0, take: int = 50):
        """List all patients via stored procedure."""
        patients_data = db_operations.list_patients(skip, take)
        return [
            _from_namespace(p) for p in patients_data
        ]

    # ── Dashboard data ──────────────────────────────────────

    def get_dashboard_data(self):
        """Get all data needed for the patient dashboard.

        Returns dict with: upcoming_appointments, past_appointments,
        total_appointments, completed_appointments.
        """
        from hms.models.appointment import Appointment
        today = date.today()

        upcoming = Appointment.list_for_patient(
            self.patient_id, upcoming=True, status='scheduled',
        )
        past = Appointment.list_for_patient(
            self.patient_id, upcoming=False, limit=5,
        )
        stat = fetch_rows(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed "
            "FROM Appointments WHERE patient_id=:pid",
            {"pid": self.patient_id},
        )[0]
        return {
            'upcoming_appointments': upcoming,
            'past_appointments': past,
            'total_appointments': int(stat["total"] or 0),
            'completed_appointments': int(stat["completed"] or 0),
        }

    def get_appointments(self):
        """Get all appointments for this patient."""
        from hms.models.appointment import Appointment
        return Appointment.list_for_patient_view(self.patient_id)

    def get_prescriptions(self):
        """Get all prescriptions for this patient."""
        from types import SimpleNamespace
        rows = fetch_rows(
            "SELECT * FROM Prescriptions WHERE patient_id = :pid ORDER BY prescribed_date DESC",
            {"pid": self.patient_id},
        )
        result = []
        for row in rows:
            x = SimpleNamespace(**dict(row))
            x.prescribed_date = _parse_dt(x.prescribed_date)
            result.append(x)
        return result

    def get_bills(self):
        """Get all bills for this patient."""
        from types import SimpleNamespace
        rows = fetch_rows(
            "SELECT * FROM Billing WHERE patient_id = :pid ORDER BY bill_date DESC",
            {"pid": self.patient_id},
        )
        bills = []
        for row in rows:
            b = SimpleNamespace(**dict(row))
            b.bill_date = _parse_dt(b.bill_date)
            b.total_amount = float(b.total_amount or 0)
            b.paid_amount = float(b.paid_amount or 0)
            b.status_badge = {"paid": "success", "partial": "warning", "pending": "secondary"}.get(b.status, "secondary")
            b.get_balance = lambda bill=b: bill.total_amount - bill.paid_amount
            bills.append(b)
        return bills


# ── Private helpers ─────────────────────────────────────────

def _parse_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _parse_dt(value):
    if isinstance(value, datetime):
        return value
    raw = str(value).replace("T", " ")
    return datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")


def _patient_select(where_sql):
    if is_sql_server():
        return f"""
            SELECT p.*, CONCAT(p.first_name, ' ', p.last_name) AS full_name, dbo.ufn_CalculateAge(p.dob) AS age
            FROM Patients p
            WHERE {where_sql}
        """
    return f"""
        SELECT p.*, (p.first_name || ' ' || p.last_name) AS full_name
        FROM Patients p
        WHERE {where_sql}
    """


def _map_row_to_patient(row):
    """Map a raw dict row to a Patient object."""
    p = Patient(
        patient_id=row["patient_id"],
        user_id=row.get("user_id"),
        first_name=row.get("first_name"),
        last_name=row.get("last_name"),
        dob=row.get("dob"),
        gender=row.get("gender"),
        phone=row.get("phone"),
        email=row.get("email"),
        address=row.get("address"),
        emergency_contact=row.get("emergency_contact"),
        blood_group=row.get("blood_group"),
        allergies=row.get("allergies"),
        registration_date=row.get("registration_date"),
    )
    # Override age if the DB computed it
    if row.get("age") is not None:
        p._db_age = int(row["age"])
    return p


def _from_namespace(ns):
    """Create a Patient from a SimpleNamespace returned by db_operations."""
    return Patient(
        patient_id=ns.patient_id,
        user_id=ns.user_id,
        first_name=ns.first_name,
        last_name=ns.last_name,
        dob=ns.dob,
        gender=ns.gender,
        phone=ns.phone,
        email=ns.email,
        address=ns.address,
        emergency_contact=ns.emergency_contact,
        blood_group=ns.blood_group,
        allergies=ns.allergies,
        registration_date=ns.registration_date,
    )
