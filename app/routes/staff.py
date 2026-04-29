from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.doctor import Doctor, Nurse, DoctorSchedule
from app.models.user import User
from app.models.appointment import Appointment
from app.utils import role_required, admin_required
from datetime import datetime, date, timedelta

staff_bp = Blueprint('staff', __name__)


@staff_bp.route('/')
@login_required
def list_staff():
    doctors = Doctor.query.order_by(Doctor.last_name).all()
    nurses = Nurse.query.order_by(Nurse.last_name).all()
    return render_template('staff/list.html', doctors=doctors, nurses=nurses)


@staff_bp.route('/doctors')
@login_required
def list_doctors():
    doctors = Doctor.query.order_by(Doctor.specialization, Doctor.last_name).all()
    return render_template('staff/doctors.html', doctors=doctors)


@staff_bp.route('/doctors/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_doctor():
    if request.method == 'POST':
        try:
            user = User(
                username=request.form['username'],
                email=request.form['email'],
                full_name=f"{request.form['first_name']} {request.form['last_name']}",
                role='doctor'
            )
            user.set_password(request.form['password'])
            db.session.add(user)
            db.session.flush()

            doctor = Doctor(
                user_id=user.user_id,
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                specialization=request.form['specialization'],
                phone=request.form.get('phone'),
                email=request.form['email'],
                consultation_fee=request.form.get('consultation_fee', 0),
                availability_status=True
            )
            db.session.add(doctor)
            db.session.commit()
            flash(f'Dr. {doctor.full_name} added successfully.', 'success')
            return redirect(url_for('staff.list_doctors'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding doctor: {str(e)}', 'danger')

    return render_template('staff/doctor_form.html', doctor=None)


@staff_bp.route('/doctors/<int:id>/schedule', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'doctor')
def manage_schedule(id):
    doctor = Doctor.query.get_or_404(id)

    if request.method == 'POST':
        try:
            # Remove old schedules and rebuild
            DoctorSchedule.query.filter_by(doctor_id=id).delete()
            days = request.form.getlist('day_of_week')
            starts = request.form.getlist('start_time')
            ends = request.form.getlist('end_time')
            maxes = request.form.getlist('max_appointments')

            for day, start, end, mx in zip(days, starts, ends, maxes):
                if start and end:
                    schedule = DoctorSchedule(
                        doctor_id=id,
                        day_of_week=int(day),
                        start_time=datetime.strptime(start, '%H:%M').time(),
                        end_time=datetime.strptime(end, '%H:%M').time(),
                        max_appointments=int(mx) if mx else 10
                    )
                    db.session.add(schedule)

            db.session.commit()
            flash('Schedule updated successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating schedule: {str(e)}', 'danger')

    schedules = {s.day_of_week: s for s in doctor.schedules.all()}
    return render_template('staff/manage_schedule.html', doctor=doctor, schedules=schedules)


@staff_bp.route('/nurses')
@login_required
def list_nurses():
    nurses = Nurse.query.order_by(Nurse.last_name).all()
    return render_template('staff/nurses.html', nurses=nurses)


@staff_bp.route('/nurses/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_nurse():
    if request.method == 'POST':
        try:
            user = User(
                username=request.form['username'],
                email=request.form['email'],
                full_name=f"{request.form['first_name']} {request.form['last_name']}",
                role='nurse'
            )
            user.set_password(request.form['password'])
            db.session.add(user)
            db.session.flush()

            nurse = Nurse(
                user_id=user.user_id,
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                phone=request.form.get('phone'),
                email=request.form['email'],
                assigned_ward=request.form.get('assigned_ward')
            )
            db.session.add(nurse)
            db.session.commit()
            flash(f'{nurse.full_name} added successfully.', 'success')
            return redirect(url_for('staff.list_nurses'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding nurse: {str(e)}', 'danger')

    return render_template('staff/nurse_form.html')


@staff_bp.route('/users')
@login_required
@admin_required
def list_users():
    users = User.query.order_by(User.role, User.full_name).all()
    return render_template('staff/users.html', users=users)


@staff_bp.route('/users/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(id):
    user = User.query.get_or_404(id)
    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.username} {status}.', 'success')
    return redirect(url_for('staff.list_users'))


# ============================================================================
# DOCTOR DASHBOARD ROUTES
# ============================================================================

@staff_bp.route('/doctor-dashboard')
@login_required
def doctor_dashboard():
    """Doctor dashboard showing today's appointments and stats"""
    if not current_user.is_doctor():
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('auth.login'))
    
    doctor = Doctor.query.filter_by(user_id=current_user.user_id).first()
    if not doctor:
        flash('Doctor profile not found.', 'danger')
        return redirect(url_for('auth.logout'))
    
    # Get today's appointments
    today_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor.doctor_id,
        Appointment.appointment_date == date.today(),
        Appointment.status == 'scheduled'
    ).order_by(Appointment.appointment_time).all()
    
    # Get upcoming appointments (next 7 days)
    week_later = date.today() + timedelta(days=7)
    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor.doctor_id,
        Appointment.appointment_date > date.today(),
        Appointment.appointment_date <= week_later,
        Appointment.status == 'scheduled'
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()
    
    # Get stats
    total_appointments = Appointment.query.filter_by(doctor_id=doctor.doctor_id).count()
    completed_appointments = Appointment.query.filter_by(
        doctor_id=doctor.doctor_id,
        status='completed'
    ).count()
    pending_appointments = Appointment.query.filter_by(
        doctor_id=doctor.doctor_id,
        status='scheduled'
    ).count()
    
    return render_template(
        'staff/doctor_dashboard.html',
        doctor=doctor,
        today_appointments=today_appointments,
        upcoming_appointments=upcoming_appointments,
        total_appointments=total_appointments,
        completed_appointments=completed_appointments,
        pending_appointments=pending_appointments
    )


@staff_bp.route('/doctor/appointments')
@login_required
def doctor_appointments():
    """Legacy endpoint retained for compatibility; use shared appointments page."""
    return redirect(url_for('appointments.list_appointments'))


# ============================================================================
# NURSE DASHBOARD ROUTES
# ============================================================================

@staff_bp.route('/nurse-dashboard')
@login_required
def nurse_dashboard():
    """Nurse dashboard showing ward information and tasks"""
    if not current_user.is_nurse():
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('auth.login'))
    
    nurse = Nurse.query.filter_by(user_id=current_user.user_id).first()
    if not nurse:
        flash('Nurse profile not found.', 'danger')
        return redirect(url_for('auth.logout'))
    
    # Get today's appointments involving patients assigned to this nurse's ward
    today_appointments = Appointment.query.filter(
        Appointment.appointment_date == date.today(),
        Appointment.status == 'scheduled'
    ).order_by(Appointment.appointment_time).all()
    
    # Get stats
    total_patients = Appointment.query.filter(
        Appointment.appointment_date >= date.today() - timedelta(days=30)
    ).distinct(Appointment.patient_id).count()
    
    return render_template(
        'staff/nurse_dashboard.html',
        nurse=nurse,
        today_appointments=today_appointments,
        total_patients=total_patients
    )


@staff_bp.route('/nurse/schedule')
@login_required
def nurse_schedule():
    """View nurse schedule"""
    if not current_user.is_nurse():
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('auth.login'))
    
    nurse = Nurse.query.filter_by(user_id=current_user.user_id).first()
    if not nurse:
        flash('Nurse profile not found.', 'danger')
        return redirect(url_for('auth.logout'))
    
    return render_template('staff/nurse_schedule.html', nurse=nurse)
