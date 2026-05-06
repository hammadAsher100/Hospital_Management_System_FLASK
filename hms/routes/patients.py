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


def _convert_named_params(sql, params):
    """Convert :name style parameters to ? positional style for pyodbc."""
    if params is None:
        return sql, None
    if not isinstance(params, dict):
        return sql, params
    ordered_values = []
    def _replacer(match):
        name = match.group(1)
        ordered_values.append(params.get(name))
        return "?"
    converted_sql = re.sub(r":(\w+)", _replacer, sql)
    return converted_sql, tuple(ordered_values) if ordered_values else None


def _write(sql, params):
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
    finally:
        if conn:
            conn.close()


def _insert_get_id(sql, params):
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
        # Otherwise use SCOPE_IDENTITY()
        conn.commit()
        cursor.execute("SELECT SCOPE_IDENTITY() as id")
        row = cursor.fetchone()
        cursor.close()
        return int(row[0]) if row and row[0] is not None else None
    finally:
        if conn:
            conn.close()


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


def _map_patient(row):
    p = SimpleNamespace(**dict(row))
    p.dob = _parse_date(p.dob)
    p.registration_date = _parse_dt(p.registration_date)
    p.full_name = row.get("full_name") or f"{p.first_name} {p.last_name}"
    p.age = int(row.get("age") or _age_from_dob(p.dob))
    return p


def _get_patient_by_id(patient_id):
    rows = fetch_rows(_patient_select("p.patient_id = :patient_id"), {"patient_id": patient_id})
    return _map_patient(rows[0]) if rows else None


def _get_current_patient():
    rows = fetch_rows(_patient_select("p.user_id = :user_id"), {"user_id": current_user.user_id})
    if not rows:
        flash("Patient profile not found.", "danger")
        return None
    return _map_patient(rows[0])


def _doctor_name_expr():
    return "CONCAT('Dr. ', d.first_name, ' ', d.last_name)" if is_sql_server() else "('Dr. ' || d.first_name || ' ' || d.last_name)"


def _appointment_sql(where_sql, order_sql, tail=""):
    return f"""
        SELECT a.*, {_doctor_name_expr()} AS doctor_full_name, d.specialization, d.phone AS doctor_phone, d.consultation_fee
        FROM Appointments a
        INNER JOIN Doctors d ON d.doctor_id = a.doctor_id
        WHERE {where_sql}
        ORDER BY {order_sql}
        {tail}
    """


def _map_appointment(row):
    appt = SimpleNamespace(**dict(row))
    appt.appointment_date = _parse_date(appt.appointment_date)
    appt.appointment_time = _parse_time(appt.appointment_time)
    appt.created_at = _parse_dt(appt.created_at)
    appt.doctor = SimpleNamespace(
        full_name=row["doctor_full_name"],
        specialization=row["specialization"],
        phone=row.get("doctor_phone"),
        consultation_fee=row.get("consultation_fee"),
    )
    return appt


def _fetch_active_doctors():
    if is_sql_server():
        return rows_to_objects(fetch_rows("SELECT doctor_id, full_name, specialization, consultation_fee FROM dbo.vw_ActiveDoctors ORDER BY full_name"))
    rows = fetch_rows(
        """
        SELECT d.doctor_id, d.first_name, d.last_name, d.specialization, d.consultation_fee
        FROM Doctors d
        INNER JOIN Users u ON u.user_id = d.user_id
        WHERE u.is_active = 1 AND (d.availability_status = 1 OR d.availability_status IS NULL)
        ORDER BY d.last_name, d.first_name
        """
    )
    doctors = rows_to_objects(rows)
    for d in doctors:
        d.full_name = f"Dr. {d.first_name} {d.last_name}"
    return doctors


@patients_bp.route("/")
@login_required
def list_patients():
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 15
    offset = (page - 1) * per_page

    where = ""
    count_params = None
    page_params = None
    if search:
        where = "WHERE p.first_name LIKE ? OR p.last_name LIKE ? OR p.phone LIKE ? OR p.email LIKE ?"
        search_param = f"%{search}%"
        count_params = (search_param, search_param, search_param, search_param)
        # SQL Server: OFFSET n ROWS FETCH NEXT m ROWS - offset first, then limit
        page_params = (offset, per_page) if not search else (search_param, search_param, search_param, search_param, offset, per_page)
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
        rows = fetch_rows(sql, page_params)
    else:
        sql = """
            SELECT p.*, (p.first_name || ' ' || p.last_name) AS full_name
            FROM Patients p
            {where}
            ORDER BY p.registration_date DESC
            LIMIT ? OFFSET ?
            """.format(where=where)
        rows = fetch_rows(sql, (per_page, offset))
    return render_template("patients/list.html", patients=SimplePagination([_map_patient(r) for r in rows], page, per_page, total), search=search)


@patients_bp.route("/add", methods=["GET", "POST"])
@login_required
@role_required("admin", "doctor", "nurse")
def add_patient():
    if request.method == "POST":
        try:
            payload = {
                "first_name": request.form["first_name"],
                "last_name": request.form["last_name"],
                "dob": datetime.strptime(request.form["dob"], "%Y-%m-%d").date(),
                "gender": request.form["gender"],
                "phone": request.form["phone"],
                "email": request.form.get("email"),
                "address": request.form.get("address"),
                "emergency_contact": request.form.get("emergency_contact"),
                "blood_group": request.form.get("blood_group"),
                "allergies": request.form.get("allergies"),
            }
            if is_sql_server():
                patient_id = _insert_get_id("""
                    INSERT INTO Patients (first_name,last_name,dob,gender,phone,email,address,emergency_contact,blood_group,allergies)
                    OUTPUT INSERTED.patient_id AS id
                    VALUES (:first_name,:last_name,:dob,:gender,:phone,:email,:address,:emergency_contact,:blood_group,:allergies)
                """, payload)
            else:
                patient_id = _insert_get_id("""
                    INSERT INTO Patients (first_name,last_name,dob,gender,phone,email,address,emergency_contact,blood_group,allergies)
                    VALUES (:first_name,:last_name,:dob,:gender,:phone,:email,:address,:emergency_contact,:blood_group,:allergies)
                """, payload)
            flash(f"Patient {_get_patient_by_id(patient_id).full_name} registered successfully.", "success")
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
    appts = [_map_appointment(r) for r in fetch_rows(_appointment_sql("a.patient_id = :pid", "a.appointment_date DESC, a.appointment_time DESC"), {"pid": id})]
    rx = []
    for pr in db_operations.list_prescriptions(patient_id=id, skip=0, take=500):
        x = SimpleNamespace(**pr.__dict__)
        x.prescribed_date = _parse_dt(x.prescribed_date)
        x.doctor = SimpleNamespace(full_name=getattr(x, "doctor_full_name", None) or "—")
        x.items = db_operations.get_prescription_items(x.prescription_id)
        rx.append(x)
    bills = []
    for row in fetch_rows("SELECT * FROM Billing WHERE patient_id = :pid ORDER BY bill_date DESC", {"pid": id}):
        b = SimpleNamespace(**dict(row))
        b.bill_date = _parse_dt(b.bill_date)
        b.total_amount = float(b.total_amount or 0)
        b.paid_amount = float(b.paid_amount or 0)
        b.status_badge = {"paid": "success", "partial": "warning", "pending": "secondary"}.get(b.status, "secondary")
        b.get_balance = lambda bill=b: bill.total_amount - bill.paid_amount
        bills.append(b)
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
            _write("""
                UPDATE Patients
                SET first_name=:first_name,last_name=:last_name,dob=:dob,gender=:gender,phone=:phone,email=:email,address=:address,
                    emergency_contact=:emergency_contact,blood_group=:blood_group,allergies=:allergies
                WHERE patient_id=:patient_id
            """, {
                "patient_id": id,
                "first_name": request.form["first_name"],
                "last_name": request.form["last_name"],
                "dob": datetime.strptime(request.form["dob"], "%Y-%m-%d").date(),
                "gender": request.form["gender"],
                "phone": request.form["phone"],
                "email": request.form.get("email"),
                "address": request.form.get("address"),
                "emergency_contact": request.form.get("emergency_contact"),
                "blood_group": request.form.get("blood_group"),
                "allergies": request.form.get("allergies"),
            })
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
        _write("DELETE FROM Patients WHERE patient_id = :id", {"id": id})
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
    upcoming = [_map_appointment(r) for r in fetch_rows(_appointment_sql("a.patient_id = :pid AND a.appointment_date >= :today AND a.status='scheduled'", "a.appointment_date, a.appointment_time"), {"pid": patient.patient_id, "today": today})]
    past_tail = "OFFSET 0 ROWS FETCH NEXT 5 ROWS ONLY" if is_sql_server() else "LIMIT 5"
    past = [_map_appointment(r) for r in fetch_rows(_appointment_sql("a.patient_id = :pid AND a.appointment_date < :today", "a.appointment_date DESC, a.appointment_time DESC", past_tail), {"pid": patient.patient_id, "today": today})]
    stat = fetch_rows("SELECT COUNT(*) AS total, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed FROM Appointments WHERE patient_id=:pid", {"pid": patient.patient_id})[0]

    return render_template("patients/patient_dashboard.html", patient=patient, upcoming_appointments=upcoming, past_appointments=past, total_appointments=int(stat["total"] or 0), completed_appointments=int(stat["completed"] or 0))


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

            if is_sql_server():
                c = exec_procedure("dbo.usp_CheckAppointmentConflict", {"doctor_id": doctor_id, "appointment_date": appt_date, "appointment_time": appt_time, "exclude_id": None})
                has_conflict = bool(c and c[0]["has_conflict"])
            else:
                has_conflict = int(fetch_rows("SELECT COUNT(*) AS c FROM Appointments WHERE doctor_id=:d AND appointment_date=:ad AND appointment_time=:at AND status='scheduled'", {"d": doctor_id, "ad": appt_date, "at": appt_time})[0]["c"]) > 0

            if has_conflict:
                flash("This time slot is already booked. Please choose another.", "danger")
            else:
                params = {"patient_id": patient.patient_id, "doctor_id": doctor_id, "appointment_date": appt_date, "appointment_time": appt_time, "reason": reason}
                if is_sql_server():
                    appt_id = _insert_get_id("""
                        INSERT INTO Appointments (patient_id,doctor_id,appointment_date,appointment_time,reason,status)
                        OUTPUT INSERTED.appointment_id AS id
                        VALUES (:patient_id,:doctor_id,:appointment_date,:appointment_time,:reason,'scheduled')
                    """, params)
                else:
                    appt_id = _insert_get_id("INSERT INTO Appointments (patient_id,doctor_id,appointment_date,appointment_time,reason,status) VALUES (:patient_id,:doctor_id,:appointment_date,:appointment_time,:reason,'scheduled')", params)
                flash("Appointment booked successfully!", "success")
                return redirect(url_for("patients.patient_view_appointment", id=appt_id))
        except ValueError:
            flash("Invalid date or time format.", "danger")
        except Exception as e:
            flash(f"Error booking appointment: {e}", "danger")

    return render_template("patients/book_appointment.html", patient=patient, doctors=_fetch_active_doctors(), min_booking_date=(date.today() + timedelta(days=1)).strftime("%Y-%m-%d"), max_booking_date=(date.today() + timedelta(days=90)).strftime("%Y-%m-%d"))


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
    offset = (page - 1) * per_page
    status_clause = "AND a.status = :status" if status_filter else ""
    count_params = {"pid": patient.patient_id, "status": status_filter} if status_filter else {"pid": patient.patient_id}
    total = int(fetch_rows(f"SELECT COUNT(*) AS total FROM Appointments a WHERE a.patient_id=:pid {status_clause}", count_params)[0]["total"])
    tail = "OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY" if is_sql_server() else "LIMIT :limit OFFSET :offset"
    rows = fetch_rows(_appointment_sql(f"a.patient_id=:pid {status_clause}", "a.appointment_date DESC, a.appointment_time DESC", tail), {"pid": patient.patient_id, "status": status_filter, "offset": offset, "limit": per_page} if status_filter else {"pid": patient.patient_id, "offset": offset, "limit": per_page})
    return render_template("patients/my_appointments.html", patient=patient, appointments=SimplePagination([_map_appointment(r) for r in rows], page, per_page, total), status_filter=status_filter)


@patients_bp.route("/appointment/<int:id>/view")
@login_required
def patient_view_appointment(id):
    if not current_user.is_patient():
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("auth.login"))
    rows = fetch_rows(_appointment_sql("a.appointment_id=:id", "a.appointment_date DESC"), {"id": id})
    if not rows:
        abort(404)
    appt = _map_appointment(rows[0])
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
    rows = fetch_rows(_appointment_sql("a.appointment_id=:id", "a.appointment_date DESC"), {"id": id})
    if not rows:
        abort(404)
    appt = _map_appointment(rows[0])
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
            _write("UPDATE Appointments SET status='cancelled' WHERE appointment_id=:id", {"id": id})
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
            _write("""
                UPDATE Patients SET email=:email, phone=:phone, address=:address, emergency_contact=:emergency_contact,
                    blood_group=:blood_group, allergies=:allergies
                WHERE patient_id=:id
            """, {
                "id": patient.patient_id,
                "email": email,
                "phone": request.form.get("phone", "").strip(),
                "address": request.form.get("address", "").strip() or None,
                "emergency_contact": request.form.get("emergency_contact", "").strip() or None,
                "blood_group": request.form.get("blood_group", "").strip() or None,
                "allergies": request.form.get("allergies", "").strip() or None,
            })
            _write("UPDATE Users SET email=:email WHERE user_id=:uid", {"email": email, "uid": current_user.user_id})
            current_user.email = email
            flash("My Profile updated successfully.", "success")
            return redirect(url_for("patients.patient_profile"))
        except Exception as e:
            flash(f"Error updating profile: {e}", "danger")

    return render_template("patients/patient_profile.html", patient=_get_current_patient(), user=current_user)
