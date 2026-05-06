from datetime import datetime, timedelta
from math import ceil
from types import SimpleNamespace

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from hms import db_operations
from hms.utils import role_required

appointments_bp = Blueprint('appointments', __name__)


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


def _parse_time(value):
    raw = str(value)
    return datetime.strptime(raw[:8], '%H:%M:%S').time()


def _status_badge(status):
    return {'scheduled': 'primary', 'completed': 'success', 'cancelled': 'danger'}.get(status, 'secondary')


def _map_appointment_row(appt):
    if hasattr(appt, 'appointment_time'):
        try:
            appt.appointment_time = _parse_time(appt.appointment_time)
        except Exception:
            pass
    appt.status_badge = _status_badge(appt.status)

    appt.patient = SimpleNamespace(
        full_name=getattr(appt, 'patient_full_name', ''),
        first_name=getattr(appt, 'patient_first_name', ''),
        last_name=getattr(appt, 'patient_last_name', ''),
        age=int(getattr(appt, 'patient_age', 0) or 0),
        gender=getattr(appt, 'patient_gender', ''),
        phone=getattr(appt, 'patient_phone', ''),
        blood_group=getattr(appt, 'patient_blood_group', None),
        allergies=getattr(appt, 'patient_allergies', None),
    )
    appt.doctor = SimpleNamespace(
        full_name=getattr(appt, 'doctor_full_name', ''),
        specialization=getattr(appt, 'doctor_specialization', ''),
    )
    return appt


def _fetch_active_doctors():
    return db_operations.list_active_doctors()


def _doctor_id_for_current_user():
    if not current_user.is_doctor():
        return None
    doctor = db_operations.get_doctor_by_user_id(current_user.user_id)
    return doctor.doctor_id if doctor else None


@appointments_bp.route('/')
@login_required
def list_appointments():
    status_filter = request.args.get('status', '')
    date_filter = request.args.get('date', '')
    page = request.args.get('page', 1, type=int)
    per_page = 15
    skip = (page - 1) * per_page

    doctor_id = _doctor_id_for_current_user()
    filter_date = None
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
        except ValueError:
            filter_date = None

    total = db_operations.count_appointments(
        status=status_filter or None,
        doctor_id=doctor_id,
        appointment_date=filter_date,
    )
    rows = db_operations.list_appointments(
        status=status_filter or None,
        doctor_id=doctor_id,
        appointment_date=filter_date,
        skip=skip,
        take=per_page,
    )
    items = [_map_appointment_row(a) for a in rows]
    appointments = SimplePagination(items, page, per_page, total)

    return render_template(
        'appointments/list.html',
        appointments=appointments,
        status_filter=status_filter,
        date_filter=date_filter,
    )


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

            if db_operations.check_appointment_conflict(doctor_id, appt_date, appt_time):
                flash('This time slot is already booked. Please choose another.', 'danger')
            else:
                appt_id = db_operations.create_appointment(
                    patient_id=patient_id,
                    doctor_id=doctor_id,
                    appointment_date=appt_date,
                    appointment_time=appt_time,
                    reason=reason,
                )
                flash('Appointment booked successfully!', 'success')
                return redirect(url_for('appointments.view_appointment', id=appt_id))
        except Exception as e:
            flash(f'Error booking appointment: {str(e)}', 'danger')

    patients = db_operations.list_patients(skip=0, take=10000)
    doctors = _fetch_active_doctors()
    preselect_patient = request.args.get('patient_id', type=int)
    return render_template(
        'appointments/book.html',
        patients=patients,
        doctors=doctors,
        preselect_patient=preselect_patient,
    )


@appointments_bp.route('/<int:id>')
@login_required
def view_appointment(id):
    appt = db_operations.get_appointment_by_id(id)
    if not appt:
        flash('Appointment not found.', 'danger')
        return redirect(url_for('appointments.list_appointments'))
    return render_template('appointments/view.html', appointment=_map_appointment_row(appt))


@appointments_bp.route('/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_appointment(id):
    appt = db_operations.get_appointment_by_id(id)
    if not appt:
        flash('Appointment not found.', 'danger')
        return redirect(url_for('appointments.list_appointments'))

    if appt.status == 'scheduled':
        db_operations.update_appointment_status(id, 'cancelled')
        flash('Appointment cancelled.', 'warning')
    else:
        flash('Only scheduled appointments can be cancelled.', 'danger')
    return redirect(url_for('appointments.list_appointments'))


@appointments_bp.route('/<int:id>/complete', methods=['POST'])
@login_required
@role_required('admin', 'doctor')
def complete_appointment(id):
    appt = db_operations.get_appointment_by_id(id)
    if not appt:
        flash('Appointment not found.', 'danger')
        return redirect(url_for('appointments.list_appointments'))

    notes = request.form.get('notes', '')
    if appt.status == 'scheduled':
        db_operations.update_appointment_status(id, 'completed', notes=notes)
        flash('Appointment marked as completed.', 'success')
    else:
        flash('Only scheduled appointments can be completed.', 'danger')
    return redirect(url_for('appointments.view_appointment', id=id))


@appointments_bp.route('/<int:id>/reschedule', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'doctor', 'nurse')
def reschedule_appointment(id):
    appt = db_operations.get_appointment_by_id(id)
    if not appt:
        flash('Appointment not found.', 'danger')
        return redirect(url_for('appointments.list_appointments'))

    if request.method == 'POST':
        try:
            new_date = datetime.strptime(request.form['appointment_date'], '%Y-%m-%d').date()
            new_time = datetime.strptime(request.form['appointment_time'], '%H:%M').time()

            if db_operations.check_appointment_conflict(appt.doctor_id, new_date, new_time, exclude_id=id):
                flash('That time slot is already taken.', 'danger')
            else:
                db_operations.reschedule_appointment(id, new_date, new_time)
                flash('Appointment rescheduled.', 'success')
                return redirect(url_for('appointments.view_appointment', id=id))
        except Exception as e:
            flash(f'Error rescheduling: {str(e)}', 'danger')

    return render_template('appointments/reschedule.html', appointment=_map_appointment_row(appt))


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

        schedule = db_operations.get_doctor_schedule_by_day(doctor_id, day_of_week)
        if not schedule:
            return jsonify({'slots': [], 'message': 'Doctor not available on this day'})

        booked_times = set(db_operations.get_doctor_booked_slots(doctor_id, appt_date))

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
