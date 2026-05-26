from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from hms import db_operations
from hms.models.user import User
from hms.utils import admin_required, role_required
from config import DEMO_USERNAMES

staff_bp = Blueprint('staff', __name__)


def _map_doctor(d):
    doctor = SimpleNamespace(**d.__dict__)
    doctor.full_name = getattr(d, 'full_name', f"Dr. {d.first_name} {d.last_name}")
    doctor.consultation_fee = float(getattr(d, 'consultation_fee', 0) or 0)
    total = int(getattr(d, 'total_appointments', 0) or 0)
    doctor.appointments = SimpleNamespace(count=lambda t=total: t)
    return doctor


def _map_nurse(n):
    nurse = SimpleNamespace(**n.__dict__)
    nurse.full_name = getattr(n, 'full_name', f"{n.first_name} {n.last_name}")
    active = int(getattr(n, 'active_admissions_count', 0) or 0)
    nurse.admissions = SimpleNamespace(filter_by=lambda **kwargs: SimpleNamespace(count=lambda a=active: a))
    return nurse


def _map_appt(a):
    appt = SimpleNamespace(**a.__dict__)
    appt.patient = SimpleNamespace(
        patient_id=appt.patient_id,
        full_name=getattr(appt, 'patient_full_name', ''),
        phone=getattr(appt, 'patient_phone', ''),
    )
    appt.doctor = SimpleNamespace(
        first_name=getattr(appt, 'doctor_first_name', ''),
        last_name=getattr(appt, 'doctor_last_name', ''),
        full_name=getattr(appt, 'doctor_full_name', ''),
    )
    return appt


@staff_bp.route('/')
@login_required
def list_staff():
    doctors = [_map_doctor(d) for d in db_operations.list_doctors()]
    nurses = [_map_nurse(n) for n in db_operations.list_nurses()]
    return render_template('staff/list.html', doctors=doctors, nurses=nurses)


@staff_bp.route('/doctors')
@login_required
def list_doctors():
    doctors = [_map_doctor(d) for d in db_operations.list_doctors()]
    return render_template('staff/doctors.html', doctors=doctors)


@staff_bp.route('/doctors/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_doctor():
    if request.method == 'POST':
        try:
            first_name = request.form['first_name'].strip()
            last_name = request.form['last_name'].strip()
            username = request.form['username'].strip()
            email = request.form['email'].strip()
            specialization = request.form['specialization'].strip()
            phone = (request.form.get('phone') or '').strip() or None
            consultation_fee = Decimal((request.form.get('consultation_fee') or '0').strip() or '0')

            if not username or not email or not first_name or not last_name or not specialization:
                flash('Please fill in all required fields.', 'danger')
                return render_template('staff/doctor_form.html', doctor=None)

            user = User(user_id=0, username=username, email=email, full_name=f"{first_name} {last_name}", role='doctor', password_hash='')
            user.set_password(request.form['password'])
            doctor_id = db_operations.create_doctor_with_user(
                username=username,
                password_hash=user.password_hash,
                email=email,
                first_name=first_name,
                last_name=last_name,
                specialization=specialization,
                phone=phone,
                consultation_fee=float(consultation_fee),
            )
            if not doctor_id:
                flash('Failed to add doctor.', 'danger')
                return render_template('staff/doctor_form.html', doctor=None)
            flash(f'Dr. {first_name} {last_name} added successfully.', 'success')
            return redirect(url_for('staff.list_doctors'))
        except InvalidOperation:
            flash('Invalid consultation fee. Please enter a valid number.', 'danger')
        except Exception as e:
            msg = str(e).lower()
            if 'username' in msg:
                flash('Username already exists.', 'danger')
            elif 'email' in msg:
                flash('Email already exists.', 'danger')
            else:
                flash(f'Error adding doctor: {str(e)}', 'danger')

    return render_template('staff/doctor_form.html', doctor=None)


@staff_bp.route('/doctors/<int:id>/schedule', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'doctor')
def manage_schedule(id):
    doctor_raw = next((d for d in db_operations.list_doctors() if int(d.doctor_id) == id), None)
    if not doctor_raw:
        flash('Doctor not found.', 'danger')
        return redirect(url_for('staff.list_doctors'))
    doctor = _map_doctor(doctor_raw)

    if request.method == 'POST':
        try:
            db_operations.clear_doctor_schedules(id)
            days = request.form.getlist('day_of_week')
            starts = request.form.getlist('start_time')
            ends = request.form.getlist('end_time')
            maxes = request.form.getlist('max_appointments')

            for day, start, end, mx in zip(days, starts, ends, maxes):
                if start and end:
                    db_operations.add_doctor_schedule(
                        doctor_id=id,
                        day_of_week=int(day),
                        start_time=datetime.strptime(start, '%H:%M').time(),
                        end_time=datetime.strptime(end, '%H:%M').time(),
                        max_appointments=int(mx) if mx else 10,
                    )
            flash('Schedule updated successfully.', 'success')
        except Exception as e:
            flash(f'Error updating schedule: {str(e)}', 'danger')

    schedules = {int(s.day_of_week): s for s in db_operations.list_doctor_schedules(id)}
    return render_template('staff/manage_schedule.html', doctor=doctor, schedules=schedules)


@staff_bp.route('/nurses')
@login_required
def list_nurses():
    nurses = [_map_nurse(n) for n in db_operations.list_nurses()]
    return render_template('staff/nurses.html', nurses=nurses)


@staff_bp.route('/nurses/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_nurse():
    if request.method == 'POST':
        try:
            first_name = request.form['first_name'].strip()
            last_name = request.form['last_name'].strip()
            username = request.form['username'].strip()
            email = request.form['email'].strip()

            user = User(user_id=0, username=username, email=email, full_name=f"{first_name} {last_name}", role='nurse', password_hash='')
            user.set_password(request.form['password'])
            nurse_id = db_operations.create_nurse_with_user(
                username=username,
                password_hash=user.password_hash,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=request.form.get('phone'),
                assigned_ward=request.form.get('assigned_ward'),
            )
            if not nurse_id:
                flash('Failed to add nurse.', 'danger')
                return render_template('staff/nurse_form.html')
            flash(f'{first_name} {last_name} added successfully.', 'success')
            return redirect(url_for('staff.list_nurses'))
        except Exception as e:
            flash(f'Error adding nurse: {str(e)}', 'danger')

    return render_template('staff/nurse_form.html')


@staff_bp.route('/users')
@login_required
@admin_required
def list_users():
    users = db_operations.list_users()
    return render_template('staff/users.html', users=users)


@staff_bp.route('/users/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(id):
    if current_user.username in DEMO_USERNAMES:
        flash("This action is disabled in the live demo.", "warning")
        return redirect(request.referrer or url_for("staff.list_users"))
    user = db_operations.toggle_user_active(id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('staff.list_users'))
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.username} {status}.', 'success')
    return redirect(url_for('staff.list_users'))


@staff_bp.route('/doctor-dashboard')
@login_required
def doctor_dashboard():
    if not current_user.is_doctor():
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('auth.login'))

    doctor = db_operations.get_doctor_by_user_id(current_user.user_id)
    if not doctor:
        flash('Doctor profile not found.', 'danger')
        return redirect(url_for('auth.logout'))
    doctor = _map_doctor(doctor)

    today = date.today()
    week_later = today + timedelta(days=7)
    today_appointments = [_map_appt(a) for a in db_operations.list_appointments(status='scheduled', doctor_id=doctor.doctor_id, appointment_date=today, skip=0, take=500)]
    upcoming_all = db_operations.list_appointments(status='scheduled', doctor_id=doctor.doctor_id, skip=0, take=1000)
    upcoming_appointments = [_map_appt(a) for a in upcoming_all if a.appointment_date > today and a.appointment_date <= week_later]

    total_appointments = db_operations.count_appointments(doctor_id=doctor.doctor_id)
    completed_appointments = db_operations.count_appointments(doctor_id=doctor.doctor_id, status='completed')
    pending_appointments = db_operations.count_appointments(doctor_id=doctor.doctor_id, status='scheduled')
    completion_rate_percent = int((completed_appointments / total_appointments) * 100) if total_appointments > 0 else 0

    return render_template(
        'staff/doctor_dashboard.html',
        doctor=doctor,
        today_appointments=today_appointments,
        upcoming_appointments=upcoming_appointments,
        total_appointments=total_appointments,
        completed_appointments=completed_appointments,
        pending_appointments=pending_appointments,
        completion_rate_percent=completion_rate_percent,
    )


@staff_bp.route('/doctor/appointments')
@login_required
def doctor_appointments():
    return redirect(url_for('appointments.list_appointments'))


@staff_bp.route('/nurse-dashboard')
@login_required
def nurse_dashboard():
    if not current_user.is_nurse():
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('auth.login'))

    nurse = db_operations.get_nurse_by_user_id(current_user.user_id)
    if not nurse:
        flash('Nurse profile not found.', 'danger')
        return redirect(url_for('auth.logout'))
    nurse = _map_nurse(nurse)

    today_appointments = [_map_appt(a) for a in db_operations.list_appointments(status='scheduled', appointment_date=date.today(), skip=0, take=500)]
    total_patients = db_operations.count_recent_unique_patients(days=30)

    return render_template('staff/nurse_dashboard.html', nurse=nurse, today_appointments=today_appointments, total_patients=total_patients)


@staff_bp.route('/nurse/schedule')
@login_required
def nurse_schedule():
    if not current_user.is_nurse():
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('auth.login'))

    nurse = db_operations.get_nurse_by_user_id(current_user.user_id)
    if not nurse:
        flash('Nurse profile not found.', 'danger')
        return redirect(url_for('auth.logout'))

    return render_template('staff/nurse_schedule.html', nurse=_map_nurse(nurse))
