import re
from datetime import date, datetime, timedelta
from math import ceil
from types import SimpleNamespace

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from hms import db, db_operations
from hms.db_queries import exec_procedure, fetch_rows, is_sql_server, rows_to_objects
from hms.utils import role_required

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


# ── CHANGED: _get_patient_by_id now calls usp_GetPatientById instead of raw SQL ──
def _get_patient_by_id(patient_id):
    p = db_operations.get_patient_by_id(patient_id)
    if not p:
        return None
    p.dob = _parse_date(p.dob)
    p.registration_date = _parse_dt(p.registration_date)
    if not hasattr(p, "full_name") or not p.full_name:
        p.full_name = f"{p.first_name} {p.last_name}"
    if not hasattr(p, "age") or p.age is None:
        p.age = _age_from_dob(p.dob)
    return p


# ── CHANGED: _get_current_patient now calls usp_GetPatientByUserId instead of raw SQL ──
def _get_current_patient():
    p = db_operations.get_patient_by_user_id(current_user.user_id)
    if not p:
        flash("Patient profile not found.", "danger")
        return None
    p.dob = _parse_date(p.dob)
    p.registration_date = _parse_dt(p.registration_date)
    if not hasattr(p, "full_name") or not p.full_name:
        p.full_name = f"{p.first_name} {p.last_name}"
    if not hasattr(p, "age") or p.age is None:
        p.age = _age_from_dob(p.dob)
    return p


def _map_appointment(row):
    """Map a raw row dict (from vw_AppointmentDetails) to a SimpleNamespace."""
    appt = SimpleNamespace(**dict(row))
    appt.appointment_date = _parse_date(appt.appointment_date)
    appt.appointment_time = _parse_time(appt.appointment_time)
    appt.created_at = _parse_dt(appt.created_at)
    # vw_AppointmentDetails already has doctor_full_name, doctor_specialization, etc.
    appt.doctor = SimpleNamespace(
        full_name=getattr(appt, "doctor_full_name", None) or "—",
        specialization=getattr(appt, "doctor_specialization", None),
        phone=getattr(appt, "doctor_phone", None),
        consultation_fee=getattr(appt, "consultation_fee", None),
    )
    return appt


# ── CHANGED: _fetch_active_doctors now reads vw_ActiveDoctors view via db_operations ──
def _fetch_active_doctors():
    return db_operations.list_active_doctors()


@patients_bp.route("/")
@login_required
def list_patients():
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 15
    offset = (page - 1) * per_page

    # ── CHANGED: list/count now use usp_ListPatients & usp_CountPatients
    #    (search falls back to a direct query since usp_ListPatients has no search param)
    if search:
        search_param = f"%{search}%"
        total = int(fetch_rows(
            "SELECT COUNT(*) AS total FROM Patients p "
            "WHERE p.first_name LIKE ? OR p.last_name LIKE ? OR p.phone LIKE ? OR p.email LIKE ?",
            (search_param, search_param, search_param, search_param)
        )[0]["total"])
        # Use view to get full_name + age for search results
        rows = fetch_rows(
            "SELECT p.*, CONCAT(p.first_name, ' ', p.last_name) AS full_name, "
            "dbo.ufn_CalculateAge(p.dob) AS age "
            "FROM Patients p "
            "WHERE p.first_name LIKE ? OR p.last_name LIKE ? OR p.phone LIKE ? OR p.email LIKE ? "
            "ORDER BY p.registration_date DESC "
            "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
            (search_param, search_param, search_param, search_param, offset, per_page)
        )
        patients_raw = [SimpleNamespace(**dict(r)) for r in rows]
        for p in patients_raw:
            p.dob = _parse_date(p.dob)
            p.registration_date = _parse_dt(p.registration_date)
            p.age = int(p.age) if hasattr(p, "age") and p.age is not None else _age_from_dob(p.dob)
    else:
        # ── CHANGED: use usp_ListPatients stored procedure ──
        total_rows = fetch_rows("SELECT COUNT(*) AS total FROM Patients")
        total = int(total_rows[0]["total"]) if total_rows else 0
        raw_patients = db_operations.list_patients(skip=offset, take=per_page)
        patients_raw = []
        for p in raw_patients:
            p.dob = _parse_date(p.dob)
            p.registration_date = _parse_dt(getattr(p, "registration_date", datetime.now()))
            if not hasattr(p, "age") or p.age is None:
                p.age = _age_from_dob(p.dob)
            patients_raw.append(p)

    return render_template(
        "patients/list.html",
        patients=SimplePagination(patients_raw, page, per_page, total),
        search=search
    )


@patients_bp.route("/add", methods=["GET", "POST"])
@login_required
@role_required("admin", "doctor", "nurse")
def add_patient():
    if request.method == "POST":
        try:
            # ── CHANGED: use usp_CreatePatient stored procedure ──
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

    # ── CHANGED: appointments fetched via usp_ListAppointments (uses vw_AppointmentDetails) ──
    appts_raw = db_operations.list_appointments(patient_id=id, skip=0, take=500)
    appts = []
    for a in appts_raw:
        a.appointment_date = _parse_date(a.appointment_date)
        a.appointment_time = _parse_time(a.appointment_time)
        if not hasattr(a, "created_at"):
            a.created_at = datetime.now()
        else:
            a.created_at = _parse_dt(a.created_at)
        a.doctor = SimpleNamespace(
            full_name=getattr(a, "doctor_full_name", "—"),
            specialization=getattr(a, "doctor_specialization", None),
            phone=None,
            consultation_fee=None,
        )
        appts.append(a)

    # ── CHANGED: prescriptions fetched via usp_ListPrescriptions ──
    rx = []
    for pr in db_operations.list_prescriptions(patient_id=id, skip=0, take=500):
        x = SimpleNamespace(**pr.__dict__)
        x.prescribed_date = _parse_dt(x.prescribed_date)
        x.doctor = SimpleNamespace(full_name=getattr(x, "doctor_full_name", None) or "—")
        # ── CHANGED: prescription items via usp_ListPrescriptionItems ──
        x.items = db_operations.get_prescription_items(x.prescription_id)
        rx.append(x)

    # ── CHANGED: bills fetched via usp_ListBills (uses vw_BillDetails) ──
    bills = []
    for b in db_operations.list_bills(patient_id=id, skip=0, take=500):
        b.bill_date = _parse_dt(b.bill_date)
        b.total_amount = float(b.total_amount or 0)
        b.paid_amount = float(b.paid_amount or 0)
        b.status_badge = {"paid": "success", "partial": "warning", "pending": "secondary"}.get(b.status, "secondary")
        b.get_balance = lambda bill=b: bill.total_amount - bill.paid_amount
        bills.append(b)

    return render_template(
        "patients/view.html",
        patient=patient, tab=tab,
        appointments=appts, prescriptions=rx, bills=bills
    )


@patients_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "doctor", "nurse")
def edit_patient(id):
    patient = _get_patient_by_id(id)
    if not patient:
        abort(404)

    if request.method == "POST":
        try:
            # ── CHANGED: use usp_UpdatePatient stored procedure ──
            db_operations.update_patient(
                patient_id=id,
                first_name=request.form["first_name"],
                last_name=request.form["last_name"],
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
        # NOTE: No stored procedure for delete was defined in schema.
        # This stays as a direct query (cascades are handled by DB foreign keys).
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Patients WHERE patient_id = ?", (id,))
        conn.commit()
        cursor.close()
        conn.close()
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

    # ── CHANGED: uses usp_GetPatientByUserId ──
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for("auth.logout"))

    today = date.today()

    # ── CHANGED: upcoming appointments via usp_ListAppointments (status=scheduled) ──
    upcoming_raw = db_operations.list_appointments(
        patient_id=patient.patient_id,
        status="scheduled",
        appointment_date=None,
        skip=0, take=100
    )
    upcoming = []
    for a in upcoming_raw:
        if _parse_date(a.appointment_date) >= today:
            a.appointment_date = _parse_date(a.appointment_date)
            a.appointment_time = _parse_time(a.appointment_time)
            a.doctor = SimpleNamespace(
                full_name=getattr(a, "doctor_full_name", "—"),
                specialization=getattr(a, "doctor_specialization", None),
                phone=None,
                consultation_fee=None,
            )
            upcoming.append(a)

    # ── CHANGED: past appointments via usp_ListAppointments filtered client-side ──
    past_raw = db_operations.list_appointments(
        patient_id=patient.patient_id,
        skip=0, take=5
    )
    past = []
    for a in past_raw:
        appt_date = _parse_date(a.appointment_date)
        if appt_date < today:
            a.appointment_date = appt_date
            a.appointment_time = _parse_time(a.appointment_time)
            a.doctor = SimpleNamespace(
                full_name=getattr(a, "doctor_full_name", "—"),
                specialization=getattr(a, "doctor_specialization", None),
                phone=None,
                consultation_fee=None,
            )
            past.append(a)

    # ── CHANGED: appointment stats via usp_CountAppointments ──
    total_appointments = db_operations.count_appointments(patient_id=patient.patient_id)
    completed_appointments = db_operations.count_appointments(patient_id=patient.patient_id, status="completed")

    return render_template(
        "patients/patient_dashboard.html",
        patient=patient,
        upcoming_appointments=upcoming,
        past_appointments=past,
        total_appointments=total_appointments,
        completed_appointments=completed_appointments,
    )


@patients_bp.route("/book-appointment", methods=["GET", "POST"])
@login_required
def book_appointment():
    if not current_user.is_patient():
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("auth.login"))

    # ── CHANGED: uses usp_GetPatientByUserId ──
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

            # ── CHANGED: conflict check via usp_CheckAppointmentConflict ──
            has_conflict = db_operations.check_appointment_conflict(
                doctor_id=doctor_id,
                appointment_date=appt_date,
                appointment_time=appt_time,
                exclude_id=None
            )

            if has_conflict:
                flash("This time slot is already booked. Please choose another.", "danger")
            else:
                # ── CHANGED: create appointment via usp_CreateAppointment ──
                appt_id = db_operations.create_appointment(
                    patient_id=patient.patient_id,
                    doctor_id=doctor_id,
                    appointment_date=appt_date,
                    appointment_time=appt_time,
                    reason=reason,
                )
                flash("Appointment booked successfully!", "success")
                return redirect(url_for("patients.patient_view_appointment", id=appt_id))

        except ValueError:
            flash("Invalid date or time format.", "danger")
        except Exception as e:
            flash(f"Error booking appointment: {e}", "danger")

    # ── CHANGED: doctors from vw_ActiveDoctors via db_operations.list_active_doctors() ──
    return render_template(
        "patients/book_appointment.html",
        patient=patient,
        doctors=_fetch_active_doctors(),
        min_booking_date=(date.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
        max_booking_date=(date.today() + timedelta(days=90)).strftime("%Y-%m-%d"),
    )


@patients_bp.route("/my-appointments")
@login_required
def my_appointments():
    if not current_user.is_patient():
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("auth.login"))

    # ── CHANGED: uses usp_GetPatientByUserId ──
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for("auth.logout"))

    status_filter = request.args.get("status", "") or None
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    # ── CHANGED: count and list via usp_CountAppointments and usp_ListAppointments ──
    total = db_operations.count_appointments(
        patient_id=patient.patient_id,
        status=status_filter
    )
    appts_raw = db_operations.list_appointments(
        patient_id=patient.patient_id,
        status=status_filter,
        skip=offset,
        take=per_page
    )
    appts = []
    for a in appts_raw:
        a.appointment_date = _parse_date(a.appointment_date)
        a.appointment_time = _parse_time(a.appointment_time)
        a.doctor = SimpleNamespace(
            full_name=getattr(a, "doctor_full_name", "—"),
            specialization=getattr(a, "doctor_specialization", None),
            phone=None,
            consultation_fee=None,
        )
        appts.append(a)

    return render_template(
        "patients/my_appointments.html",
        patient=patient,
        appointments=SimplePagination(appts, page, per_page, total),
        status_filter=status_filter or "",
    )


@patients_bp.route("/appointment/<int:id>/view")
@login_required
def patient_view_appointment(id):
    if not current_user.is_patient():
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("auth.login"))

    # ── CHANGED: appointment fetched via usp_GetAppointmentById (uses vw_AppointmentDetails) ──
    appt_raw = db_operations.get_appointment_by_id(id)
    if not appt_raw:
        abort(404)

    appt_raw.appointment_date = _parse_date(appt_raw.appointment_date)
    appt_raw.appointment_time = _parse_time(appt_raw.appointment_time)
    appt_raw.created_at = _parse_dt(appt_raw.created_at)
    appt_raw.doctor = SimpleNamespace(
        full_name=getattr(appt_raw, "doctor_full_name", "—"),
        specialization=getattr(appt_raw, "doctor_specialization", None),
        phone=None,
        consultation_fee=None,
    )

    # ── CHANGED: uses usp_GetPatientByUserId ──
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for("auth.logout"))

    if appt_raw.patient_id != patient.patient_id:
        flash("You do not have access to this appointment.", "danger")
        return redirect(url_for("patients.my_appointments"))

    return render_template("patients/patient_view_appointment.html", appointment=appt_raw)


@patients_bp.route("/appointment/<int:id>/cancel", methods=["POST"])
@login_required
def cancel_patient_appointment(id):
    if not current_user.is_patient():
        flash("You do not have access to this action.", "danger")
        return redirect(url_for("auth.login"))

    # ── CHANGED: appointment fetched via usp_GetAppointmentById ──
    appt = db_operations.get_appointment_by_id(id)
    if not appt:
        abort(404)

    appt.appointment_date = _parse_date(appt.appointment_date)
    appt.appointment_time = _parse_time(appt.appointment_time)

    # ── CHANGED: uses usp_GetPatientByUserId ──
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
            # ── CHANGED: status update via usp_UpdateAppointmentStatus ──
            db_operations.update_appointment_status(id, "cancelled")
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

    # ── CHANGED: uses usp_GetPatientByUserId ──
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for("auth.logout"))

    if request.method == "POST":
        try:
            email = request.form.get("email", "").strip() or None

            # ── CHANGED: update patient via usp_UpdatePatient ──
            db_operations.update_patient(
                patient_id=patient.patient_id,
                first_name=patient.first_name,   # not editable on profile page
                last_name=patient.last_name,      # not editable on profile page
                phone=request.form.get("phone", "").strip(),
                email=email,
                address=request.form.get("address", "").strip() or None,
                emergency_contact=request.form.get("emergency_contact", "").strip() or None,
                blood_group=request.form.get("blood_group", "").strip() or None,
                allergies=request.form.get("allergies", "").strip() or None,
            )

            # ── CHANGED: update user email via usp_UpdateUserProfile ──
            db_operations.update_user_profile(
                user_id=current_user.user_id,
                full_name=current_user.full_name,
                email=email,
            )
            current_user.email = email

            flash("My Profile updated successfully.", "success")
            return redirect(url_for("patients.patient_profile"))
        except Exception as e:
            flash(f"Error updating profile: {e}", "danger")

    return render_template(
        "patients/patient_profile.html",
        patient=_get_current_patient(),
        user=current_user
    )
