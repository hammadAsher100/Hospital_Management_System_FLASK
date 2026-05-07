"""Patient routes — all database operations go through stored procedures via db_operations."""

from datetime import date, datetime, timedelta
from math import ceil
from types import SimpleNamespace

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from hms import db_operations
from hms.utils import role_required

# ── Design Pattern: Chain of Responsibility ─────────────────────────────────────────
# PatientRequestChain routes every new appointment through:
#   TriageHandler → DiagnosisHandler → BillingHandler
# The final context dict carries triage_level, diagnosis_status,
# billing_status, and a one-line 'summary' for the flash message.
from hms.patterns.chain_of_responsibility import PatientRequestChain

patients_bp = Blueprint("patients", __name__)


class SimplePagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = ceil(total / per_page) if per_page else 0
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1
        self.next_num = page + 1

    def iter_pages(self, left_edge=2, left_current=2, right_current=2, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or (self.page - left_current <= num <= self.page + right_current) or num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num


def _parse_date(value):
    if isinstance(value, date):
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


def _age_from_dob(dob):
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _map_patient_ns(ns):
    """Map a SimpleNamespace from db_operations to template-ready patient object."""
    p = SimpleNamespace(**ns.__dict__)
    p.dob = _parse_date(p.dob)
    p.registration_date = _parse_dt(p.registration_date) if hasattr(p, 'registration_date') and p.registration_date else datetime.utcnow()
    if not hasattr(p, 'full_name') or not p.full_name:
        p.full_name = f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip()
    if not hasattr(p, 'age') or p.age is None:
        p.age = _age_from_dob(p.dob)
    else:
        p.age = int(p.age)
    return p


def _map_appointment_ns(ns):
    """Map appointment namespace from db_operations to template-ready object."""
    appt = SimpleNamespace(**ns.__dict__)
    appt.appointment_date = _parse_date(appt.appointment_date)
    if hasattr(appt, 'appointment_time') and appt.appointment_time:
        appt.appointment_time = _parse_time(appt.appointment_time)
    if hasattr(appt, 'created_at') and appt.created_at:
        appt.created_at = _parse_dt(appt.created_at)
    # Build nested doctor object from flat SP columns
    appt.doctor = SimpleNamespace(
        full_name=getattr(appt, 'doctor_full_name', ''),
        specialization=getattr(appt, 'doctor_specialization', ''),
        phone=getattr(appt, 'patient_phone', None),
        consultation_fee=None,
    )
    # Fetch consultation_fee from doctor if needed
    if hasattr(appt, 'doctor_id') and appt.doctor_id:
        doc = db_operations.get_doctor_by_id(appt.doctor_id)
        if doc:
            appt.doctor.consultation_fee = float(getattr(doc, 'consultation_fee', 0) or 0)
            appt.doctor.phone = getattr(doc, 'phone', None)
    return appt


def _get_patient_by_id(patient_id):
    """Get patient by ID using stored procedure."""
    ns = db_operations.get_patient_by_id(patient_id)
    return _map_patient_ns(ns) if ns else None


def _get_current_patient():
    """Get current logged-in patient using stored procedure."""
    ns = db_operations.get_patient_by_user_id(current_user.user_id)
    if not ns:
        flash("Patient profile not found.", "danger")
        return None
    return _map_patient_ns(ns)


@patients_bp.route("/")
@login_required
def list_patients():
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 15
    skip = (page - 1) * per_page

    # Use stored procedures for search and pagination
    total = db_operations.search_patients_count(search=search or None)
    patients_ns = db_operations.search_patients(search=search or None, skip=skip, take=per_page)
    patients = [_map_patient_ns(p) for p in patients_ns]

    return render_template("patients/list.html",
                           patients=SimplePagination(patients, page, per_page, total),
                           search=search)


@patients_bp.route("/add", methods=["GET", "POST"])
@login_required
@role_required("admin", "doctor", "nurse")
def add_patient():
    if request.method == "POST":
        try:
            # Use usp_CreatePatient via db_operations
            patient_id = db_operations.create_patient(
                first_name=request.form["first_name"],
                last_name=request.form["last_name"],
                dob=datetime.strptime(request.form["dob"], "%Y-%m-%d").date(),
                gender=request.form["gender"],
                phone=request.form["phone"],
                email=request.form.get("email"),
                address=request.form.get("address"),
                emergency_contact=request.form.get("emergency_contact"),
                blood_group=request.form.get("blood_group"),
                allergies=request.form.get("allergies"),
            )
            patient = _get_patient_by_id(patient_id)
            flash(f"Patient {patient.full_name} registered successfully.", "success")
            return redirect(url_for("patients.view_patient", id=patient_id))
        except Exception as e:
            flash(f"Error registering patient: {e}", "danger")
    return render_template("patients/form.html", patient=None, action="Add")


@patients_bp.route("/<int:id>")
@login_required
def view_patient(id):
    patient = _get_patient_by_id(id)
    if not patient:
        abort(404)
    tab = request.args.get("tab", "info")

    # Appointments via stored procedure
    appts_ns = db_operations.list_appointments(patient_id=id, skip=0, take=500)
    appts = [_map_appointment_ns(a) for a in appts_ns]

    # Prescriptions via stored procedure
    rx = []
    for pr in db_operations.list_prescriptions(patient_id=id, skip=0, take=500):
        x = SimpleNamespace(**pr.__dict__)
        x.prescribed_date = _parse_dt(x.prescribed_date)
        x.doctor = SimpleNamespace(full_name=getattr(x, "doctor_full_name", None) or "—")
        x.items = db_operations.get_prescription_items(x.prescription_id)
        rx.append(x)

    # Bills via stored procedure
    bills_ns = db_operations.list_bills(patient_id=id, skip=0, take=500)
    bills = []
    for b in bills_ns:
        bill = SimpleNamespace(**b.__dict__)
        bill.bill_date = _parse_dt(bill.bill_date)
        bill.total_amount = float(bill.total_amount or 0)
        bill.paid_amount = float(bill.paid_amount or 0)
        bill.status_badge = {"paid": "success", "partial": "warning", "pending": "secondary"}.get(bill.status, "secondary")
        bill.get_balance = lambda bill=bill: bill.total_amount - bill.paid_amount
        bills.append(bill)

    return render_template("patients/view.html", patient=patient, tab=tab, appointments=appts, prescriptions=rx, bills=bills)


@patients_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "doctor", "nurse")
def edit_patient(id):
    patient = _get_patient_by_id(id)
    if not patient:
        abort(404)
    if request.method == "POST":
        try:
            # Use usp_UpdatePatientFull via db_operations
            db_operations.update_patient_full(
                patient_id=id,
                first_name=request.form["first_name"],
                last_name=request.form["last_name"],
                dob=datetime.strptime(request.form["dob"], "%Y-%m-%d").date(),
                gender=request.form["gender"],
                phone=request.form["phone"],
                email=request.form.get("email"),
                address=request.form.get("address"),
                emergency_contact=request.form.get("emergency_contact"),
                blood_group=request.form.get("blood_group"),
                allergies=request.form.get("allergies"),
            )
            flash("Patient information updated.", "success")
            return redirect(url_for("patients.view_patient", id=id))
        except Exception as e:
            flash(f"Error updating patient: {e}", "danger")
    return render_template("patients/form.html", patient=patient, action="Edit")


@patients_bp.route("/<int:id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_patient(id):
    if not _get_patient_by_id(id):
        abort(404)
    try:
        # Use usp_DeletePatient via db_operations
        db_operations.delete_patient(id)
        flash("Patient record deleted.", "success")
    except Exception as e:
        flash(f"Cannot delete patient: {e}", "danger")
    return redirect(url_for("patients.list_patients"))


@patients_bp.route("/dashboard")
@login_required
def patient_dashboard():
    if not current_user.is_patient():
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("auth.login"))
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for("auth.logout"))

    today = date.today()

    # Upcoming appointments via stored procedure
    upcoming_ns = db_operations.list_appointments(
        patient_id=patient.patient_id, status='scheduled',
        appointment_date=None, skip=0, take=500,
    )
    upcoming = [_map_appointment_ns(a) for a in upcoming_ns if a.appointment_date >= today]

    # Past appointments via stored procedure (last 5)
    all_appts = db_operations.list_appointments(
        patient_id=patient.patient_id, skip=0, take=500,
    )
    past = [_map_appointment_ns(a) for a in all_appts if a.appointment_date < today][:5]

    # Dashboard stats via stored procedure
    stats = db_operations.get_patient_dashboard_stats(patient.patient_id)

    return render_template("patients/patient_dashboard.html",
                           patient=patient,
                           upcoming_appointments=upcoming,
                           past_appointments=past,
                           total_appointments=stats["total_appointments"],
                           completed_appointments=stats["completed_appointments"])


@patients_bp.route("/book-appointment", methods=["GET", "POST"])
@login_required
def book_appointment():
    if not current_user.is_patient():
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("auth.login"))
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for("auth.logout"))

    if request.method == "POST":
        doctor_id = request.form.get("doctor_id", type=int)
        reason = request.form.get("reason", "")
        try:
            appt_date = datetime.strptime(request.form.get("appointment_date"), "%Y-%m-%d").date()
            appt_time = datetime.strptime(request.form.get("appointment_time"), "%H:%M").time()
            if appt_date < date.today():
                flash("Cannot book appointment for past dates.", "danger")
                return redirect(url_for("patients.book_appointment"))
            if appt_date > date.today() + timedelta(days=90):
                flash("Appointments can only be booked up to 90 days in advance.", "danger")
                return redirect(url_for("patients.book_appointment"))

            # Use usp_CheckAppointmentConflict via db_operations
            if db_operations.check_appointment_conflict(doctor_id, appt_date, appt_time):
                flash("This time slot is already booked. Please choose another.", "danger")
            else:
                # Use usp_CreateAppointment via db_operations
                appt_id = db_operations.create_appointment(
                    patient_id=patient.patient_id,
                    doctor_id=doctor_id,
                    appointment_date=appt_date,
                    appointment_time=appt_time,
                    reason=reason,
                )

                # ── Chain of Responsibility ─────────────────────────────────
                # Pass the new appointment through Triage → Diagnosis → Billing.
                # Any exception is caught so it never breaks the success path.
                try:
                    chain_ctx = {
                        "patient_id":   patient.patient_id,
                        "request_type": "appointment",
                        "priority":     "urgent" if "urgent" in reason.lower() or "emergency" in reason.lower() else "normal",
                        "diagnosis":    "",
                        "reason":       reason,
                        "bill_id":      None,
                    }
                    result = PatientRequestChain().process(chain_ctx)
                    flash(
                        f"Request processed — {result.get('summary', 'OK')}",
                        "info",
                    )
                except Exception as chain_err:
                    print(f"[PatientRequestChain] Non-critical error: {chain_err}")
                # ────────────────────────────────────────────────

                flash("Appointment booked successfully!", "success")
                return redirect(url_for("patients.patient_view_appointment", id=appt_id))
        except ValueError:
            flash("Invalid date or time format.", "danger")
        except Exception as e:
            flash(f"Error booking appointment: {e}", "danger")

    # Active doctors via stored procedure
    doctors = db_operations.list_active_doctors()
    return render_template("patients/book_appointment.html",
                           patient=patient,
                           doctors=doctors,
                           min_booking_date=(date.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
                           max_booking_date=(date.today() + timedelta(days=90)).strftime("%Y-%m-%d"))


@patients_bp.route("/my-appointments")
@login_required
def my_appointments():
    if not current_user.is_patient():
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("auth.login"))
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for("auth.logout"))

    status_filter = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page

    # Count and list via stored procedures
    total = db_operations.count_appointments(
        patient_id=patient.patient_id,
        status=status_filter or None,
    )
    appts_ns = db_operations.list_appointments(
        patient_id=patient.patient_id,
        status=status_filter or None,
        skip=skip,
        take=per_page,
    )
    appointments = [_map_appointment_ns(a) for a in appts_ns]

    return render_template("patients/my_appointments.html",
                           patient=patient,
                           appointments=SimplePagination(appointments, page, per_page, total),
                           status_filter=status_filter)


@patients_bp.route("/appointment/<int:id>/view")
@login_required
def patient_view_appointment(id):
    if not current_user.is_patient():
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("auth.login"))

    # Use usp_GetAppointmentById via db_operations
    appt_ns = db_operations.get_appointment_by_id(id)
    if not appt_ns:
        abort(404)
    appt = _map_appointment_ns(appt_ns)

    patient = _get_current_patient()
    if not patient:
        return redirect(url_for("auth.logout"))
    if appt.patient_id != patient.patient_id:
        flash("You do not have access to this appointment.", "danger")
        return redirect(url_for("patients.my_appointments"))
    return render_template("patients/patient_view_appointment.html", appointment=appt)


@patients_bp.route("/appointment/<int:id>/cancel", methods=["POST"])
@login_required
def cancel_patient_appointment(id):
    if not current_user.is_patient():
        flash("You do not have access to this action.", "danger")
        return redirect(url_for("auth.login"))

    # Use usp_GetAppointmentById via db_operations
    appt_ns = db_operations.get_appointment_by_id(id)
    if not appt_ns:
        abort(404)
    appt = _map_appointment_ns(appt_ns)

    patient = _get_current_patient()
    if not patient:
        return redirect(url_for("auth.logout"))
    if appt.patient_id != patient.patient_id:
        flash("You do not have access to this appointment.", "danger")
        return redirect(url_for("patients.my_appointments"))
    if appt.status == "scheduled":
        if datetime.combine(appt.appointment_date, appt.appointment_time) < datetime.utcnow() + timedelta(hours=24):
            flash("Cannot cancel appointments within 24 hours of scheduled time.", "danger")
        else:
            # Use usp_UpdateAppointmentStatus via db_operations
            db_operations.update_appointment_status(id, 'cancelled')
            flash("Appointment cancelled successfully.", "warning")
    else:
        flash("Only scheduled appointments can be cancelled.", "danger")
    return redirect(url_for("patients.my_appointments"))


@patients_bp.route("/profile", methods=["GET", "POST"])
@login_required
def patient_profile():
    if not current_user.is_patient():
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("auth.login"))
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for("auth.logout"))

    if request.method == "POST":
        try:
            email = request.form.get("email", "").strip() or None
            # Use usp_UpdatePatientProfile via db_operations (updates both Patients + Users)
            db_operations.update_patient_profile(
                patient_id=patient.patient_id,
                user_id=current_user.user_id,
                email=email,
                phone=request.form.get("phone", "").strip(),
                address=request.form.get("address", "").strip() or None,
                emergency_contact=request.form.get("emergency_contact", "").strip() or None,
                blood_group=request.form.get("blood_group", "").strip() or None,
                allergies=request.form.get("allergies", "").strip() or None,
            )
            current_user.email = email
            flash("My Profile updated successfully.", "success")
            return redirect(url_for("patients.patient_profile"))
        except Exception as e:
            flash(f"Error updating profile: {e}", "danger")

    return render_template("patients/patient_profile.html", patient=_get_current_patient(), user=current_user)
