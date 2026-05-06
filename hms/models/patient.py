"""Patient model — CRUD, profile management, dashboard data, registration."""

from datetime import datetime, date
from hms import db_operations
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
        """Update profile fields (patient-facing). Uses usp_UpdatePatientProfile."""
        db_operations.update_patient_profile(
            patient_id=self.patient_id,
            user_id=self.user_id,
            email=email,
            phone=phone,
            address=address,
            emergency_contact=emergency_contact,
            blood_group=blood_group,
            allergies=allergies,
        )

    @staticmethod
    def delete(patient_id: int):
        """Delete a patient record. Uses usp_DeletePatient."""
        success = db_operations.delete_patient(patient_id)
        if not success:
            raise ValidationError('Cannot delete patient.')

    # ── Lookups ─────────────────────────────────────────────

    @staticmethod
    def get_by_id(patient_id: int) -> 'Patient':
        """Get patient by ID. Uses usp_GetPatientById."""
        ns = db_operations.get_patient_by_id(patient_id)
        return _from_namespace(ns) if ns else None

    @staticmethod
    def get_by_user_id(user_id: int) -> 'Patient':
        """Get patient by user ID. Uses usp_GetPatientByUserId."""
        ns = db_operations.get_patient_by_user_id(user_id)
        return _from_namespace(ns) if ns else None

    @staticmethod
    def list_paginated(search: str = '', page: int = 1, per_page: int = 15):
        """List patients with search and pagination. Uses usp_SearchPatients.

        Returns (patients_list, total_count).
        """
        skip = (page - 1) * per_page
        total = db_operations.search_patients_count(search=search or None)
        patients_ns = db_operations.search_patients(search=search or None, skip=skip, take=per_page)
        patients = [_from_namespace(p) for p in patients_ns]
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
        Uses usp_GetPatientDashboardStats + usp_ListAppointments.

        Returns dict with: upcoming_appointments, past_appointments,
        total_appointments, completed_appointments.
        """
        from hms.models.appointment import Appointment

        upcoming = Appointment.list_for_patient(
            self.patient_id, upcoming=True, status='scheduled',
        )
        past = Appointment.list_for_patient(
            self.patient_id, upcoming=False, limit=5,
        )
        stats = db_operations.get_patient_dashboard_stats(self.patient_id)
        return {
            'upcoming_appointments': upcoming,
            'past_appointments': past,
            'total_appointments': stats['total_appointments'],
            'completed_appointments': stats['completed_appointments'],
        }

    def get_appointments(self):
        """Get all appointments for this patient."""
        from hms.models.appointment import Appointment
        return Appointment.list_for_patient_view(self.patient_id)

    def get_prescriptions(self):
        """Get all prescriptions for this patient. Uses usp_ListPrescriptions."""
        from types import SimpleNamespace
        presc_data = db_operations.list_prescriptions(patient_id=self.patient_id, skip=0, take=500)
        result = []
        for p in presc_data:
            x = SimpleNamespace(**p.__dict__)
            x.prescribed_date = _parse_dt(x.prescribed_date)
            result.append(x)
        return result

    def get_bills(self):
        """Get all bills for this patient. Uses usp_ListBills."""
        from types import SimpleNamespace
        bills_data = db_operations.list_bills(patient_id=self.patient_id, skip=0, take=500)
        bills = []
        for b in bills_data:
            bill = SimpleNamespace(**b.__dict__)
            bill.bill_date = _parse_dt(bill.bill_date)
            bill.total_amount = float(bill.total_amount or 0)
            bill.paid_amount = float(bill.paid_amount or 0)
            bill.status_badge = {"paid": "success", "partial": "warning", "pending": "secondary"}.get(bill.status, "secondary")
            bill.get_balance = lambda b=bill: b.total_amount - b.paid_amount
            bills.append(bill)
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
