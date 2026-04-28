from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.patient import Patient
from app.models.user import User
from app.models.appointment import Appointment
from app.models.doctor import Doctor, DoctorSchedule
from app.utils import role_required
from datetime import datetime, date, timedelta

patients_bp = Blueprint('patients', __name__)


def _get_current_patient():
    patient = Patient.query.filter_by(user_id=current_user.user_id).first()
    if not patient:
        flash('Patient profile not found.', 'danger')
        return None
    return patient


@patients_bp.route('/')
@login_required
def list_patients():
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    query = Patient.query
    if search:
        query = query.filter(
            db.or_(
                Patient.first_name.ilike(f'%{search}%'),
                Patient.last_name.ilike(f'%{search}%'),
                Patient.phone.ilike(f'%{search}%'),
                Patient.email.ilike(f'%{search}%')
            )
        )

    patients = query.order_by(Patient.registration_date.desc()).paginate(
        page=page, per_page=15, error_out=False
    )
    return render_template('patients/list.html', patients=patients, search=search)


@patients_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'doctor', 'nurse')
def add_patient():
    if request.method == 'POST':
        try:
            patient = Patient(
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                dob=datetime.strptime(request.form['dob'], '%Y-%m-%d').date(),
                gender=request.form['gender'],
                phone=request.form['phone'],
                email=request.form.get('email'),
                address=request.form.get('address'),
                emergency_contact=request.form.get('emergency_contact'),
                blood_group=request.form.get('blood_group'),
                allergies=request.form.get('allergies'),
            )
            db.session.add(patient)
            db.session.commit()
            flash(f'Patient {patient.full_name} registered successfully.', 'success')
            return redirect(url_for('patients.view_patient', id=patient.patient_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering patient: {str(e)}', 'danger')

    return render_template('patients/form.html', patient=None, action='Add')


@patients_bp.route('/<int:id>')
@login_required
def view_patient(id):
    patient = Patient.query.get_or_404(id)
    tab = request.args.get('tab', 'info')
    return render_template('patients/view.html', patient=patient, tab=tab)


@patients_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'doctor', 'nurse')
def edit_patient(id):
    patient = Patient.query.get_or_404(id)

    if request.method == 'POST':
        try:
            patient.first_name = request.form['first_name']
            patient.last_name = request.form['last_name']
            patient.dob = datetime.strptime(request.form['dob'], '%Y-%m-%d').date()
            patient.gender = request.form['gender']
            patient.phone = request.form['phone']
            patient.email = request.form.get('email')
            patient.address = request.form.get('address')
            patient.emergency_contact = request.form.get('emergency_contact')
            patient.blood_group = request.form.get('blood_group')
            patient.allergies = request.form.get('allergies')
            db.session.commit()
            flash('Patient information updated.', 'success')
            return redirect(url_for('patients.view_patient', id=id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating patient: {str(e)}', 'danger')

    return render_template('patients/form.html', patient=patient, action='Edit')


@patients_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_patient(id):
    patient = Patient.query.get_or_404(id)
    try:
        db.session.delete(patient)
        db.session.commit()
        flash('Patient record deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete patient: {str(e)}', 'danger')
    return redirect(url_for('patients.list_patients'))


# ============================================================================
# PATIENT PORTAL ROUTES - Self-service booking and management
# ============================================================================

@patients_bp.route('/dashboard')
@login_required
def patient_dashboard():
    """Patient dashboard showing their appointments and health info"""
    if not current_user.is_patient():
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('auth.login'))
    
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for('auth.logout'))
    
    # Get upcoming appointments
    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == patient.patient_id,
        Appointment.appointment_date >= date.today(),
        Appointment.status == 'scheduled'
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()
    
    # Get past appointments
    past_appointments = Appointment.query.filter(
        Appointment.patient_id == patient.patient_id,
        Appointment.appointment_date < date.today()
    ).order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).limit(5).all()
    
    # Calculate stats
    total_appointments = Appointment.query.filter_by(patient_id=patient.patient_id).count()
    completed_appointments = Appointment.query.filter_by(
        patient_id=patient.patient_id, 
        status='completed'
    ).count()
    
    return render_template(
        'patients/patient_dashboard.html',
        patient=patient,
        upcoming_appointments=upcoming_appointments,
        past_appointments=past_appointments,
        total_appointments=total_appointments,
        completed_appointments=completed_appointments
    )


@patients_bp.route('/book-appointment', methods=['GET', 'POST'])
@login_required
def book_appointment():
    """Self-service appointment booking for patients"""
    if not current_user.is_patient():
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('auth.login'))
    
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for('auth.logout'))
    
    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id', type=int)
        appt_date_str = request.form.get('appointment_date')
        appt_time_str = request.form.get('appointment_time')
        reason = request.form.get('reason', '')

        try:
            appt_date = datetime.strptime(appt_date_str, '%Y-%m-%d').date()
            appt_time = datetime.strptime(appt_time_str, '%H:%M').time()
            
            # Validate date is not in the past
            if appt_date < date.today():
                flash('Cannot book appointment for past dates.', 'danger')
                return redirect(url_for('patients.book_appointment'))
            
            # Validate date is not too far in future (e.g., max 90 days)
            max_future_date = date.today() + timedelta(days=90)
            if appt_date > max_future_date:
                flash('Appointments can only be booked up to 90 days in advance.', 'danger')
                return redirect(url_for('patients.book_appointment'))

            if Appointment.has_conflict(doctor_id, appt_date, appt_time):
                flash('This time slot is already booked. Please choose another.', 'danger')
            else:
                appt = Appointment(
                    patient_id=patient.patient_id,
                    doctor_id=doctor_id,
                    appointment_date=appt_date,
                    appointment_time=appt_time,
                    reason=reason,
                    status='scheduled'
                )
                db.session.add(appt)
                db.session.commit()
                flash('Appointment booked successfully!', 'success')
                return redirect(url_for('patients.patient_view_appointment', id=appt.appointment_id))
        except ValueError:
            flash('Invalid date or time format.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error booking appointment: {str(e)}', 'danger')

    # Get all available doctors
    doctors = Doctor.query.filter_by(availability_status=True).order_by(Doctor.last_name).all()
    min_booking_date = date.today() + timedelta(days=1)
    max_booking_date = date.today() + timedelta(days=90)
    
    return render_template(
        'patients/book_appointment.html',
        patient=patient,
        doctors=doctors,
        min_booking_date=min_booking_date.strftime('%Y-%m-%d'),
        max_booking_date=max_booking_date.strftime('%Y-%m-%d')
    )


@patients_bp.route('/my-appointments')
@login_required
def my_appointments():
    """View all appointments for the current patient"""
    if not current_user.is_patient():
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('auth.login'))
    
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for('auth.logout'))
    
    status_filter = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    
    query = Appointment.query.filter_by(patient_id=patient.patient_id)
    
    if status_filter:
        query = query.filter(Appointment.status == status_filter)
    
    appointments = query.order_by(
        Appointment.appointment_date.desc(),
        Appointment.appointment_time.desc()
    ).paginate(page=page, per_page=10, error_out=False)
    
    return render_template(
        'patients/my_appointments.html',
        patient=patient,
        appointments=appointments,
        status_filter=status_filter
    )


@patients_bp.route('/appointment/<int:id>/view')
@login_required
def patient_view_appointment(id):
    """View a specific appointment"""
    if not current_user.is_patient():
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('auth.login'))
    
    appt = Appointment.query.get_or_404(id)
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for('auth.logout'))
    
    # Verify patient owns this appointment
    if appt.patient_id != patient.patient_id:
        flash('You do not have access to this appointment.', 'danger')
        return redirect(url_for('patients.my_appointments'))
    
    return render_template('patients/patient_view_appointment.html', appointment=appt)


@patients_bp.route('/appointment/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_patient_appointment(id):
    """Cancel an appointment"""
    if not current_user.is_patient():
        flash('You do not have access to this action.', 'danger')
        return redirect(url_for('auth.login'))
    
    appt = Appointment.query.get_or_404(id)
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for('auth.logout'))
    
    # Verify patient owns this appointment
    if appt.patient_id != patient.patient_id:
        flash('You do not have access to this appointment.', 'danger')
        return redirect(url_for('patients.my_appointments'))
    
    if appt.status == 'scheduled':
        # Check if appointment is at least 24 hours away
        appt_datetime = datetime.combine(appt.appointment_date, appt.appointment_time)
        if appt_datetime < datetime.utcnow() + timedelta(hours=24):
            flash('Cannot cancel appointments within 24 hours of scheduled time.', 'danger')
        else:
            appt.cancel()
            flash('Appointment cancelled successfully.', 'warning')
    else:
        flash('Only scheduled appointments can be cancelled.', 'danger')
    
    return redirect(url_for('patients.my_appointments'))


@patients_bp.route('/profile')
@login_required
def patient_profile():
    """View patient profile"""
    if not current_user.is_patient():
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('auth.login'))
    
    patient = _get_current_patient()
    if not patient:
        return redirect(url_for('auth.logout'))
    
    return render_template('patients/patient_profile.html', patient=patient, user=current_user)
