from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.doctor import Doctor, DoctorSchedule
from app.models.user import User
from app.utils import role_required
from datetime import datetime, date, timedelta
from sqlalchemy import or_

appointments_bp = Blueprint('appointments', __name__)


@appointments_bp.route('/')
@login_required
def list_appointments():
    status_filter = request.args.get('status', '')
    date_filter = request.args.get('date', '')
    page = request.args.get('page', 1, type=int)

    query = Appointment.query.join(Patient).join(Doctor)

    if current_user.is_doctor() and current_user.doctor_profile:
        query = query.filter(Appointment.doctor_id == current_user.doctor_profile.doctor_id)

    if status_filter:
        query = query.filter(Appointment.status == status_filter)

    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(Appointment.appointment_date == filter_date)
        except ValueError:
            pass

    appointments = query.order_by(
        Appointment.appointment_date.desc(),
        Appointment.appointment_time.desc()
    ).paginate(page=page, per_page=15, error_out=False)

    return render_template('appointments/list.html',
                           appointments=appointments,
                           status_filter=status_filter,
                           date_filter=date_filter)


@appointments_bp.route('/book', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'nurse')
def book_appointment():
    if request.method == 'POST':
        patient_id = request.form.get('patient_id', type=int)
        doctor_id = request.form.get('doctor_id', type=int)
        appt_date_str = request.form.get('appointment_date')
        appt_time_str = request.form.get('appointment_time')
        reason = request.form.get('reason', '')

        try:
            appt_date = datetime.strptime(appt_date_str, '%Y-%m-%d').date()
            appt_time = datetime.strptime(appt_time_str, '%H:%M').time()

            if Appointment.has_conflict(doctor_id, appt_date, appt_time):
                flash('This time slot is already booked. Please choose another.', 'danger')
            else:
                appt = Appointment(
                    patient_id=patient_id,
                    doctor_id=doctor_id,
                    appointment_date=appt_date,
                    appointment_time=appt_time,
                    reason=reason,
                    status='scheduled'
                )
                db.session.add(appt)
                db.session.commit()
                flash('Appointment booked successfully!', 'success')
                return redirect(url_for('appointments.view_appointment', id=appt.appointment_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error booking appointment: {str(e)}', 'danger')

    patients = Patient.query.order_by(Patient.last_name).all()
    doctors = (
        Doctor.query.join(User, Doctor.user_id == User.user_id)
        .filter(User.is_active == True)
        .filter(or_(Doctor.availability_status == True, Doctor.availability_status.is_(None)))
        .order_by(Doctor.last_name)
        .all()
    )
    preselect_patient = request.args.get('patient_id', type=int)
    return render_template('appointments/book.html', patients=patients, doctors=doctors,
                           preselect_patient=preselect_patient)


@appointments_bp.route('/<int:id>')
@login_required
def view_appointment(id):
    appt = Appointment.query.get_or_404(id)
    return render_template('appointments/view.html', appointment=appt)


@appointments_bp.route('/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_appointment(id):
    appt = Appointment.query.get_or_404(id)
    if appt.status == 'scheduled':
        appt.cancel()
        flash('Appointment cancelled.', 'warning')
    else:
        flash('Only scheduled appointments can be cancelled.', 'danger')
    return redirect(url_for('appointments.list_appointments'))


@appointments_bp.route('/<int:id>/complete', methods=['POST'])
@login_required
@role_required('admin', 'doctor')
def complete_appointment(id):
    appt = Appointment.query.get_or_404(id)
    notes = request.form.get('notes', '')
    if appt.status == 'scheduled':
        appt.notes = notes
        appt.complete()
        flash('Appointment marked as completed.', 'success')
    else:
        flash('Only scheduled appointments can be completed.', 'danger')
    return redirect(url_for('appointments.view_appointment', id=id))


@appointments_bp.route('/<int:id>/reschedule', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'doctor', 'nurse')
def reschedule_appointment(id):
    appt = Appointment.query.get_or_404(id)
    if request.method == 'POST':
        try:
            new_date = datetime.strptime(request.form['appointment_date'], '%Y-%m-%d').date()
            new_time = datetime.strptime(request.form['appointment_time'], '%H:%M').time()

            if Appointment.has_conflict(appt.doctor_id, new_date, new_time, exclude_id=id):
                flash('That time slot is already taken.', 'danger')
            else:
                appt.appointment_date = new_date
                appt.appointment_time = new_time
                db.session.commit()
                flash('Appointment rescheduled.', 'success')
                return redirect(url_for('appointments.view_appointment', id=id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error rescheduling: {str(e)}', 'danger')

    return render_template('appointments/reschedule.html', appointment=appt)


@appointments_bp.route('/api/available-slots')
@login_required
def available_slots():
    doctor_id = request.args.get('doctor_id', type=int)
    date_str = request.args.get('date')

    if not doctor_id or not date_str:
        return jsonify({'slots': []})

    try:
        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        day_of_week = appt_date.weekday()

        schedule = DoctorSchedule.query.filter_by(
            doctor_id=doctor_id, day_of_week=day_of_week
        ).first()

        if not schedule:
            return jsonify({'slots': [], 'message': 'Doctor not available on this day'})

        booked_times = {
            str(a.appointment_time)[:5]
            for a in Appointment.query.filter_by(
                doctor_id=doctor_id,
                appointment_date=appt_date,
                status='scheduled'
            ).all()
        }

        # Generate 30-min slots
        slots = []
        current = datetime.combine(appt_date, schedule.start_time)
        end = datetime.combine(appt_date, schedule.end_time)
        while current < end:
            t_str = current.strftime('%H:%M')
            slots.append({'time': t_str, 'available': t_str not in booked_times})
            current += timedelta(minutes=30)

        return jsonify({'slots': slots})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
