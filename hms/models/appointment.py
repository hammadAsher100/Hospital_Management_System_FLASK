"""Appointment model — booking, cancellation, rescheduling, conflict checks, available slots."""

from datetime import datetime, date, time, timedelta
from types import SimpleNamespace
from hms import db_operations
from hms.db_queries import fetch_rows, exec_procedure, is_sql_server
from hms.utils.exceptions import ValidationError


class Appointment:
    """Appointment model with business logic for booking, cancellation, and scheduling."""

    STATUS_BADGES = {
        'scheduled': 'primary',
        'completed': 'success',
        'cancelled': 'danger',
    }

    def __init__(self, appointment_id: int, patient_id: int, doctor_id: int,
                 appointment_date: date, appointment_time: time, status: str = 'scheduled',
                 reason: str = None, notes: str = None, created_at: datetime = None,
                 doctor=None, patient=None, **extra):
        self.appointment_id = appointment_id
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.appointment_date = _parse_date(appointment_date)
        self.appointment_time = _parse_time(appointment_time) if appointment_time else None
        self.status = status
        self.reason = reason
        self.notes = notes
        self.created_at = created_at or datetime.utcnow()
        # Related objects (populated by mapping helpers)
        self.doctor = doctor
        self.patient = patient
        # Store any extra DB columns (e.g. patient_full_name, doctor_specialization)
        for k, v in extra.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    @property
    def status_badge(self):
        return self.STATUS_BADGES.get(self.status, 'secondary')

    def __repr__(self):
        return f'<Appointment {self.appointment_id} - {self.status}>'

    # ── Actions ─────────────────────────────────────────────

    @staticmethod
    def book(patient_id: int, doctor_id: int, date_str: str, time_str: str,
             reason: str = '') -> int:
        """Book a new appointment. Returns appointment_id.

        Validates:
        - Date not in the past
        - Not more than 90 days in advance
        - No conflict with existing appointments

        Raises ValidationError on failure.
        """
        try:
            appt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            appt_time = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            raise ValidationError("Invalid date or time format.")

        today = date.today()
        if appt_date < today:
            raise ValidationError("Cannot book appointment for past dates.")
        if appt_date > today + timedelta(days=90):
            raise ValidationError("Appointments can only be booked up to 90 days in advance.")

        if Appointment.has_conflict(doctor_id, appt_date, appt_time):
            raise ValidationError("This time slot is already booked. Please choose another.")

        from hms import db
        from hms.db_queries import _convert_named_params
        conn = None
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            sql = """
                INSERT INTO Appointments (patient_id,doctor_id,appointment_date,appointment_time,reason,status)
                OUTPUT INSERTED.appointment_id AS id
                VALUES (:patient_id,:doctor_id,:appointment_date,:appointment_time,:reason,'scheduled')
            """
            params = {
                "patient_id": patient_id, "doctor_id": doctor_id,
                "appointment_date": appt_date, "appointment_time": appt_time,
                "reason": reason,
            }
            sql, params = _convert_named_params(sql, params)
            cursor.execute(sql, params) if params else cursor.execute(sql)
            row = cursor.fetchone()
            conn.commit()
            cursor.close()
            return int(row[0]) if row else None
        except Exception as e:
            if conn:
                conn.rollback()
            raise ValidationError(f"Error booking appointment: {e}")
        finally:
            if conn:
                conn.close()

    @staticmethod
    def book_by_staff(patient_id: int, doctor_id: int, date_str: str, time_str: str,
                      reason: str = '') -> int:
        """Book appointment by admin/nurse — no 90-day limit but still checks conflicts."""
        try:
            appt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            appt_time = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            raise ValidationError("Invalid date or time format.")

        if Appointment.has_conflict(doctor_id, appt_date, appt_time):
            raise ValidationError("This time slot is already booked. Please choose another.")

        appt_id = db_operations.create_appointment(
            patient_id=patient_id, doctor_id=doctor_id,
            appointment_date=appt_date, appointment_time=appt_time, reason=reason,
        )
        if not appt_id:
            raise ValidationError("Failed to create appointment.")
        return appt_id

    def cancel(self, by_patient: bool = False):
        """Cancel a scheduled appointment.

        If by_patient is True, enforces the 24-hour cancellation rule.
        Raises ValidationError if not allowed.
        """
        if self.status != 'scheduled':
            raise ValidationError("Only scheduled appointments can be cancelled.")

        if by_patient:
            appt_dt = datetime.combine(self.appointment_date, self.appointment_time)
            if appt_dt < datetime.utcnow() + timedelta(hours=24):
                raise ValidationError("Cannot cancel appointments within 24 hours of scheduled time.")

        db_operations.update_appointment_status(self.appointment_id, 'cancelled')
        self.status = 'cancelled'

    def complete(self, notes: str = None):
        """Mark appointment as completed. Raises ValidationError if not scheduled."""
        if self.status != 'scheduled':
            raise ValidationError("Only scheduled appointments can be completed.")
        db_operations.update_appointment_status(self.appointment_id, 'completed', notes=notes)
        self.status = 'completed'
        self.notes = notes

    def reschedule(self, new_date_str: str, new_time_str: str):
        """Reschedule to a new date/time. Checks for conflicts.

        Raises ValidationError on failure.
        """
        try:
            new_date = datetime.strptime(new_date_str, "%Y-%m-%d").date()
            new_time = datetime.strptime(new_time_str, "%H:%M").time()
        except ValueError:
            raise ValidationError("Invalid date or time format.")

        if Appointment.has_conflict(self.doctor_id, new_date, new_time, exclude_id=self.appointment_id):
            raise ValidationError("That time slot is already taken.")

        db_operations.reschedule_appointment(self.appointment_id, new_date, new_time)
        self.appointment_date = new_date
        self.appointment_time = new_time

    # ── Lookups ─────────────────────────────────────────────

    @staticmethod
    def has_conflict(doctor_id: int, appointment_date: date, appointment_time: time,
                     exclude_id: int = None) -> bool:
        """Check if appointment time slot has a conflict."""
        if is_sql_server():
            c = exec_procedure("dbo.usp_CheckAppointmentConflict", {
                "doctor_id": doctor_id, "appointment_date": appointment_date,
                "appointment_time": appointment_time, "exclude_id": exclude_id,
            })
            return bool(c and c[0]["has_conflict"])
        else:
            count = int(fetch_rows(
                "SELECT COUNT(*) AS c FROM Appointments WHERE doctor_id=:d AND appointment_date=:ad "
                "AND appointment_time=:at AND status='scheduled'",
                {"d": doctor_id, "ad": appointment_date, "at": appointment_time},
            )[0]["c"])
            return count > 0

    @staticmethod
    def get_available_slots(doctor_id: int, date_str: str):
        """Get available time slots for a doctor on a given date.

        Returns dict: {slots: [...], message: str or None}.
        """
        try:
            appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return {'slots': [], 'message': 'Invalid date'}

        day_of_week = appt_date.weekday()
        schedule = db_operations.get_doctor_schedule_by_day(doctor_id, day_of_week)
        if not schedule:
            return {'slots': [], 'message': 'Doctor not available on this day'}

        booked_times = set(db_operations.get_doctor_booked_slots(doctor_id, appt_date))

        slots = []
        current = datetime.combine(appt_date, schedule.start_time)
        end = datetime.combine(appt_date, schedule.end_time)
        while current < end:
            t_str = current.strftime('%H:%M')
            slots.append({'time': t_str, 'available': t_str not in booked_times})
            current += timedelta(minutes=30)

        return {'slots': slots, 'message': None}

    @staticmethod
    def get_by_id(appointment_id: int) -> 'Appointment':
        """Get appointment by ID (via stored procedure, includes joined data)."""
        appt_data = db_operations.get_appointment_by_id(appointment_id)
        if not appt_data:
            return None
        return _from_db_namespace(appt_data)

    @staticmethod
    def get_by_id_rich(appointment_id: int) -> 'Appointment':
        """Get appointment by ID with full doctor join (for patient-facing views)."""
        rows = fetch_rows(_appointment_sql("a.appointment_id=:id", "a.appointment_date DESC"), {"id": appointment_id})
        if not rows:
            return None
        return _map_appointment_row(rows[0])

    @staticmethod
    def list_paginated(status: str = None, doctor_id: int = None, date_filter: date = None,
                       page: int = 1, per_page: int = 15):
        """List appointments with filters and pagination.

        Returns (items, total).
        """
        skip = (page - 1) * per_page
        total = db_operations.count_appointments(
            status=status or None, doctor_id=doctor_id,
            appointment_date=date_filter,
        )
        rows = db_operations.list_appointments(
            status=status or None, doctor_id=doctor_id,
            appointment_date=date_filter, skip=skip, take=per_page,
        )
        items = [_from_db_namespace(a) for a in rows]
        return items, total

    @staticmethod
    def list_for_patient(patient_id: int, upcoming: bool = True, status: str = None,
                         limit: int = 500):
        """List appointments for a patient (used in patient dashboard)."""
        today = date.today()
        if upcoming:
            rows = fetch_rows(
                _appointment_sql(
                    "a.patient_id = :pid AND a.appointment_date >= :today AND a.status='scheduled'",
                    "a.appointment_date, a.appointment_time",
                ),
                {"pid": patient_id, "today": today},
            )
        else:
            tail = f"OFFSET 0 ROWS FETCH NEXT {limit} ROWS ONLY" if is_sql_server() else f"LIMIT {limit}"
            rows = fetch_rows(
                _appointment_sql(
                    "a.patient_id = :pid AND a.appointment_date < :today",
                    "a.appointment_date DESC, a.appointment_time DESC",
                    tail,
                ),
                {"pid": patient_id, "today": today},
            )
        return [_map_appointment_row(r) for r in rows]

    @staticmethod
    def list_for_patient_view(patient_id: int):
        """List all appointments for the patient detail view."""
        rows = fetch_rows(
            _appointment_sql("a.patient_id = :pid", "a.appointment_date DESC, a.appointment_time DESC"),
            {"pid": patient_id},
        )
        return [_map_appointment_row(r) for r in rows]

    @staticmethod
    def list_for_patient_paginated(patient_id: int, status_filter: str = '',
                                   page: int = 1, per_page: int = 10):
        """List appointments for "My Appointments" with pagination.

        Returns (items, total).
        """
        offset = (page - 1) * per_page
        status_clause = "AND a.status = :status" if status_filter else ""
        count_params = {"pid": patient_id, "status": status_filter} if status_filter else {"pid": patient_id}
        total = int(fetch_rows(
            f"SELECT COUNT(*) AS total FROM Appointments a WHERE a.patient_id=:pid {status_clause}",
            count_params,
        )[0]["total"])
        tail = "OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY" if is_sql_server() else "LIMIT :limit OFFSET :offset"
        page_params = {"pid": patient_id, "status": status_filter, "offset": offset, "limit": per_page} if status_filter \
            else {"pid": patient_id, "offset": offset, "limit": per_page}
        rows = fetch_rows(
            _appointment_sql(f"a.patient_id=:pid {status_clause}",
                             "a.appointment_date DESC, a.appointment_time DESC", tail),
            page_params,
        )
        items = [_map_appointment_row(r) for r in rows]
        return items, total

    @staticmethod
    def count(doctor_id: int = None, status: str = None, appointment_date: date = None) -> int:
        """Count appointments with optional filters."""
        return db_operations.count_appointments(status=status, doctor_id=doctor_id, appointment_date=appointment_date)


# ── Active Doctor Helpers ───────────────────────────────────

def get_active_doctors():
    """Get active doctors for dropdowns."""
    from hms.db_queries import rows_to_objects
    if is_sql_server():
        return rows_to_objects(
            fetch_rows("SELECT doctor_id, full_name, specialization, consultation_fee "
                        "FROM dbo.vw_ActiveDoctors ORDER BY full_name")
        )
    rows = fetch_rows(
        "SELECT d.doctor_id, d.first_name, d.last_name, d.specialization, d.consultation_fee "
        "FROM Doctors d INNER JOIN Users u ON u.user_id = d.user_id "
        "WHERE u.is_active = 1 AND (d.availability_status = 1 OR d.availability_status IS NULL) "
        "ORDER BY d.last_name, d.first_name"
    )
    doctors = rows_to_objects(rows)
    for d in doctors:
        d.full_name = f"Dr. {d.first_name} {d.last_name}"
    return doctors


# ── Private helpers ─────────────────────────────────────────

def _parse_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _parse_time(value):
    if hasattr(value, "hour") and not isinstance(value, datetime):
        return value
    raw = str(value)
    return datetime.strptime(raw, "%H:%M:%S" if len(raw) > 5 else "%H:%M").time()


def _parse_dt(value):
    if isinstance(value, datetime):
        return value
    raw = str(value).replace("T", " ")
    return datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")


def _doctor_name_expr():
    return "CONCAT('Dr. ', d.first_name, ' ', d.last_name)" if is_sql_server() \
        else "('Dr. ' || d.first_name || ' ' || d.last_name)"


def _appointment_sql(where_sql, order_sql, tail=""):
    return f"""
        SELECT a.*, {_doctor_name_expr()} AS doctor_full_name, d.specialization, d.phone AS doctor_phone, d.consultation_fee
        FROM Appointments a
        INNER JOIN Doctors d ON d.doctor_id = a.doctor_id
        WHERE {where_sql}
        ORDER BY {order_sql}
        {tail}
    """


def _map_appointment_row(row):
    """Map a raw dict row to an Appointment with nested doctor/patient objects."""
    appt = Appointment(
        appointment_id=row["appointment_id"],
        patient_id=row["patient_id"],
        doctor_id=row["doctor_id"],
        appointment_date=row["appointment_date"],
        appointment_time=row.get("appointment_time"),
        status=row["status"],
        reason=row.get("reason"),
        notes=row.get("notes"),
        created_at=row.get("created_at"),
    )
    if row.get("created_at"):
        appt.created_at = _parse_dt(row["created_at"])
    appt.doctor = SimpleNamespace(
        full_name=row.get("doctor_full_name", ""),
        specialization=row.get("specialization", ""),
        phone=row.get("doctor_phone"),
        consultation_fee=row.get("consultation_fee"),
    )
    return appt


def _from_db_namespace(ns):
    """Create Appointment from a SimpleNamespace returned by db_operations."""
    appt = Appointment(
        appointment_id=ns.appointment_id,
        patient_id=ns.patient_id,
        doctor_id=ns.doctor_id,
        appointment_date=ns.appointment_date,
        appointment_time=getattr(ns, 'appointment_time', None),
        status=ns.status,
        reason=getattr(ns, 'reason', None),
        notes=getattr(ns, 'notes', None),
        created_at=getattr(ns, 'created_at', None),
    )
    # Populate patient/doctor sub-objects if the SP returned joined columns
    appt.patient = SimpleNamespace(
        full_name=getattr(ns, 'patient_full_name', ''),
        first_name=getattr(ns, 'patient_first_name', ''),
        last_name=getattr(ns, 'patient_last_name', ''),
        age=int(getattr(ns, 'patient_age', 0) or 0),
        gender=getattr(ns, 'patient_gender', ''),
        phone=getattr(ns, 'patient_phone', ''),
        blood_group=getattr(ns, 'patient_blood_group', None),
        allergies=getattr(ns, 'patient_allergies', None),
    )
    appt.doctor = SimpleNamespace(
        full_name=getattr(ns, 'doctor_full_name', ''),
        specialization=getattr(ns, 'doctor_specialization', ''),
    )
    return appt
