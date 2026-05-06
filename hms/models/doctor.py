"""Doctor, Nurse, DoctorSchedule models — staff creation, dashboard data, schedule management."""

from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from hms import db_operations
from hms.utils.exceptions import ValidationError


class Doctor:
    """Doctor model with business logic for creation, dashboard, and schedule management."""

    def __init__(self, doctor_id: int, user_id: int = 0, first_name: str = '',
                 last_name: str = '', specialization: str = '', phone: str = None,
                 email: str = None, consultation_fee: float = 0,
                 availability_status: bool = True, **extra):
        self.doctor_id = doctor_id
        self.user_id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.specialization = specialization
        self.phone = phone
        self.email = email
        self.consultation_fee = float(consultation_fee or 0)
        self.availability_status = availability_status
        # Extra columns from joined queries (e.g. total_appointments)
        for k, v in extra.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    @property
    def full_name(self):
        fn = getattr(self, '_full_name', None)
        if fn:
            return fn
        return f"Dr. {self.first_name} {self.last_name}"

    @full_name.setter
    def full_name(self, value):
        self._full_name = value

    def is_available(self):
        return self.availability_status

    def __repr__(self):
        return f'<Doctor {self.full_name}>'

    # ── Creation ────────────────────────────────────────────

    @staticmethod
    def create_with_user(username: str, password: str, email: str, first_name: str,
                         last_name: str, specialization: str, phone: str = None,
                         consultation_fee_str: str = '0') -> int:
        """Create a doctor with associated user account.

        Returns doctor_id. Raises ValidationError on failure.
        """
        if not all([username, email, first_name, last_name, specialization]):
            raise ValidationError('Please fill in all required fields.')

        try:
            fee = float(Decimal(consultation_fee_str.strip() or '0'))
        except (InvalidOperation, ValueError):
            raise ValidationError('Invalid consultation fee. Please enter a valid number.')

        from hms.models.user import User
        user = User(user_id=0, username=username, email=email,
                    full_name=f"{first_name} {last_name}", role='doctor', password_hash='')
        user.set_password(password)

        doctor_id = db_operations.create_doctor_with_user(
            username=username, password_hash=user.password_hash, email=email,
            first_name=first_name, last_name=last_name,
            specialization=specialization, phone=phone, consultation_fee=fee,
        )
        if not doctor_id:
            raise ValidationError('Failed to add doctor.')
        return doctor_id

    # ── Schedule management ─────────────────────────────────

    @staticmethod
    def update_schedule(doctor_id: int, days: list, starts: list, ends: list, maxes: list):
        """Clear and re-add doctor schedule entries.

        Raises ValidationError on failure.
        """
        db_operations.clear_doctor_schedules(doctor_id)
        for day, start, end, mx in zip(days, starts, ends, maxes):
            if start and end:
                db_operations.add_doctor_schedule(
                    doctor_id=doctor_id,
                    day_of_week=int(day),
                    start_time=datetime.strptime(start, '%H:%M').time(),
                    end_time=datetime.strptime(end, '%H:%M').time(),
                    max_appointments=int(mx) if mx else 10,
                )

    @staticmethod
    def get_schedules(doctor_id: int) -> dict:
        """Get schedule dict keyed by day_of_week."""
        return {int(s.day_of_week): s for s in db_operations.list_doctor_schedules(doctor_id)}

    # ── Dashboard ───────────────────────────────────────────

    def get_dashboard_data(self):
        """Get doctor dashboard stats and appointment lists.

        Returns dict with: today_appointments, upcoming_appointments,
        total/completed/pending counts, completion_rate_percent.
        """
        today = date.today()
        week_later = today + timedelta(days=7)

        today_appts = db_operations.list_appointments(
            status='scheduled', doctor_id=self.doctor_id,
            appointment_date=today, skip=0, take=500,
        )
        upcoming_all = db_operations.list_appointments(
            status='scheduled', doctor_id=self.doctor_id, skip=0, take=1000,
        )
        upcoming = [a for a in upcoming_all if a.appointment_date > today and a.appointment_date <= week_later]

        total = db_operations.count_appointments(doctor_id=self.doctor_id)
        completed = db_operations.count_appointments(doctor_id=self.doctor_id, status='completed')
        pending = db_operations.count_appointments(doctor_id=self.doctor_id, status='scheduled')
        rate = int((completed / total) * 100) if total > 0 else 0

        return {
            'today_appointments': [_map_staff_appt(a) for a in today_appts],
            'upcoming_appointments': [_map_staff_appt(a) for a in upcoming],
            'total_appointments': total,
            'completed_appointments': completed,
            'pending_appointments': pending,
            'completion_rate_percent': rate,
        }

    # ── Lookups ─────────────────────────────────────────────

    @staticmethod
    def get_by_id(doctor_id: int) -> 'Doctor':
        """Get doctor by ID"""
        d = db_operations.get_doctor_by_id(doctor_id)
        if not d:
            return None
        return _from_namespace_doctor(d)

    @staticmethod
    def get_by_user_id(user_id: int) -> 'Doctor':
        """Get doctor by user ID"""
        d = db_operations.get_doctor_by_user_id(user_id)
        if not d:
            return None
        return _from_namespace_doctor(d)

    @staticmethod
    def list_all() -> list:
        """List all doctors with mapped data."""
        return [_from_namespace_doctor(d) for d in db_operations.list_doctors()]

    @staticmethod
    def list_active() -> list:
        """List active doctors."""
        return [_from_namespace_doctor(d) for d in db_operations.list_active_doctors()]

    @staticmethod
    def get_doctor_id_for_user(user_id: int):
        """Get doctor_id for a user, or None."""
        doctor = db_operations.get_doctor_by_user_id(user_id)
        return doctor.doctor_id if doctor else None


class Nurse:
    """Nurse model with creation and dashboard logic."""

    def __init__(self, nurse_id: int = 0, user_id: int = 0, first_name: str = '',
                 last_name: str = '', phone: str = None, email: str = None,
                 assigned_ward: str = None, **extra):
        self.nurse_id = nurse_id
        self.user_id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.phone = phone
        self.email = email
        self.assigned_ward = assigned_ward
        for k, v in extra.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    @property
    def full_name(self):
        fn = getattr(self, '_full_name', None)
        return fn if fn else f"{self.first_name} {self.last_name}"

    @full_name.setter
    def full_name(self, value):
        self._full_name = value

    def __repr__(self):
        return f'<Nurse {self.full_name}>'

    @staticmethod
    def create_with_user(username: str, password: str, email: str, first_name: str,
                         last_name: str, phone: str = None, assigned_ward: str = None) -> int:
        """Create a nurse with associated user account. Returns nurse_id."""
        from hms.models.user import User
        user = User(user_id=0, username=username, email=email,
                    full_name=f"{first_name} {last_name}", role='nurse', password_hash='')
        user.set_password(password)

        nurse_id = db_operations.create_nurse_with_user(
            username=username, password_hash=user.password_hash, email=email,
            first_name=first_name, last_name=last_name,
            phone=phone, assigned_ward=assigned_ward,
        )
        if not nurse_id:
            raise ValidationError('Failed to add nurse.')
        return nurse_id

    def get_dashboard_data(self):
        """Get nurse dashboard data."""
        today_appts = db_operations.list_appointments(
            status='scheduled', appointment_date=date.today(), skip=0, take=500,
        )
        total_patients = db_operations.count_recent_unique_patients(days=30)
        return {
            'today_appointments': [_map_staff_appt(a) for a in today_appts],
            'total_patients': total_patients,
        }

    @staticmethod
    def get_by_user_id(user_id: int) -> 'Nurse':
        ns = db_operations.get_nurse_by_user_id(user_id)
        if not ns:
            return None
        return _from_namespace_nurse(ns)

    @staticmethod
    def list_all() -> list:
        return [_from_namespace_nurse(n) for n in db_operations.list_nurses()]


class DoctorSchedule:
    """Doctor Schedule model"""

    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    def __init__(self, schedule_id: int, doctor_id: int, day_of_week: int,
                 start_time, end_time, max_appointments: int = 10):
        self.schedule_id = schedule_id
        self.doctor_id = doctor_id
        self.day_of_week = day_of_week
        self.start_time = start_time
        self.end_time = end_time
        self.max_appointments = max_appointments

    @property
    def day_name(self):
        return self.DAY_NAMES[self.day_of_week]

    def __repr__(self):
        return f'<Schedule {self.day_name} {self.start_time}-{self.end_time}>'


# ── Private helpers ─────────────────────────────────────────

def _from_namespace_doctor(ns):
    """Build Doctor from a SimpleNamespace."""
    d = Doctor(
        doctor_id=ns.doctor_id,
        user_id=getattr(ns, 'user_id', 0),
        first_name=getattr(ns, 'first_name', ''),
        last_name=getattr(ns, 'last_name', ''),
        specialization=getattr(ns, 'specialization', ''),
        phone=getattr(ns, 'phone', None),
        email=getattr(ns, 'email', None),
        consultation_fee=getattr(ns, 'consultation_fee', 0),
        availability_status=getattr(ns, 'availability_status', True),
    )
    if hasattr(ns, 'full_name'):
        d.full_name = ns.full_name
    # Copy any extra attributes (total_appointments, etc.)
    for attr in ('total_appointments',):
        if hasattr(ns, attr):
            setattr(d, attr, getattr(ns, attr))
    return d


def _from_namespace_nurse(ns):
    """Build Nurse from a SimpleNamespace."""
    n = Nurse(
        nurse_id=getattr(ns, 'nurse_id', 0),
        user_id=getattr(ns, 'user_id', 0),
        first_name=getattr(ns, 'first_name', ''),
        last_name=getattr(ns, 'last_name', ''),
        phone=getattr(ns, 'phone', None),
        email=getattr(ns, 'email', None),
        assigned_ward=getattr(ns, 'assigned_ward', None),
    )
    if hasattr(ns, 'full_name'):
        n.full_name = ns.full_name
    for attr in ('active_admissions_count',):
        if hasattr(ns, attr):
            setattr(n, attr, getattr(ns, attr))
    return n


def _map_staff_appt(a):
    """Map an appointment namespace for staff dashboard views."""
    appt = SimpleNamespace(**a.__dict__)
    appt.patient = SimpleNamespace(
        patient_id=a.patient_id,
        full_name=getattr(a, 'patient_full_name', ''),
        phone=getattr(a, 'patient_phone', ''),
    )
    appt.doctor = SimpleNamespace(
        first_name=getattr(a, 'doctor_first_name', ''),
        last_name=getattr(a, 'doctor_last_name', ''),
        full_name=getattr(a, 'doctor_full_name', ''),
    )
    return appt
