from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from app import db
from app.models.billing import Bill, BillItem
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.utils import role_required
from datetime import datetime
import csv
import io

billing_bp = Blueprint('billing', __name__)


def _get_current_patient():
    return Patient.query.filter_by(user_id=current_user.user_id).first()


def _can_access_bill(bill):
    if current_user.is_admin() or current_user.is_billing():
        return True
    if current_user.is_patient():
        patient = _get_current_patient()
        return bool(patient and bill.patient_id == patient.patient_id)
    return False


@billing_bp.route('/')
@login_required
def list_bills():
    status_filter = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)

    query = Bill.query.join(Patient)
    if current_user.is_patient():
        patient = _get_current_patient()
        if not patient:
            flash('Patient profile not found.', 'danger')
            return redirect(url_for('auth.logout'))
        query = query.filter(Bill.patient_id == patient.patient_id)
    if status_filter:
        query = query.filter(Bill.status == status_filter)

    bills = query.order_by(Bill.bill_date.desc()).paginate(page=page, per_page=15, error_out=False)
    return render_template('billing/list.html', bills=bills, status_filter=status_filter)


@billing_bp.route('/generate', methods=['GET', 'POST'])
@login_required
def generate_bill():
    patient_user = current_user.is_patient()
    staff_user = current_user.is_admin() or current_user.is_billing()
    if not patient_user and not staff_user:
        flash('You do not have permission to access billing.', 'danger')
        return redirect(url_for('auth.login'))

    current_patient = _get_current_patient() if patient_user else None
    if patient_user and not current_patient:
        flash('Patient profile not found.', 'danger')
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        try:
            patient_id = int(request.form['patient_id'])
            appointment_id = request.form.get('appointment_id') or None
            payment_method = request.form.get('payment_method', '')

            descriptions = request.form.getlist('description[]')
            quantities = request.form.getlist('quantity[]')
            unit_prices = request.form.getlist('unit_price[]')

            if patient_user and patient_id != current_patient.patient_id:
                flash('You can only generate bills for your own profile.', 'danger')
                return redirect(url_for('billing.generate_bill'))

            if appointment_id:
                appointment = Appointment.query.get(int(appointment_id))
                if not appointment:
                    flash('Selected appointment does not exist.', 'danger')
                    return redirect(url_for('billing.generate_bill'))
                if appointment.patient_id != patient_id:
                    flash('Selected appointment does not belong to this patient.', 'danger')
                    return redirect(url_for('billing.generate_bill'))
                if appointment.status != 'completed':
                    flash('Bills can only be generated for completed appointments.', 'danger')
                    return redirect(url_for('billing.generate_bill'))

                # Prevent duplicate appointment bills.
                existing_bill = Bill.query.filter_by(appointment_id=appointment.appointment_id).first()
                if existing_bill:
                    flash('A bill is already generated for this appointment.', 'warning')
                    return redirect(url_for('billing.view_bill', id=existing_bill.bill_id))
            else:
                appointment = None

            # In patient flow, allow auto item creation from completed appointment.
            if patient_user and appointment and (not descriptions or not any(d.strip() for d in descriptions)):
                descriptions = [f"Consultation Fee - {appointment.doctor.full_name}"]
                quantities = ['1']
                unit_prices = [str(float(appointment.doctor.consultation_fee or 0))]

            if not descriptions or not any(d.strip() for d in descriptions):
                flash('Please add at least one item.', 'danger')
                raise ValueError("No items")

            if patient_user:
                non_empty_descriptions = [d for d in descriptions if d and d.strip()]
                if len(non_empty_descriptions) > 1:
                    flash('Patients can only generate a bill with one item.', 'danger')
                    return redirect(url_for('billing.generate_bill'))

            bill = Bill(
                patient_id=patient_id,
                appointment_id=int(appointment_id) if appointment_id else None,
                payment_method=payment_method,
                status='pending'
            )
            db.session.add(bill)
            db.session.flush()

            total = 0
            for desc, qty, price in zip(descriptions, quantities, unit_prices):
                if desc.strip():
                    qty_int = int(qty) if qty else 1
                    price_float = float(price) if price else 0
                    item_total = qty_int * price_float
                    total += item_total
                    item = BillItem(
                        bill_id=bill.bill_id,
                        description=desc,
                        quantity=qty_int,
                        unit_price=price_float,
                        total_price=item_total
                    )
                    db.session.add(item)

            if patient_user and appointment and total <= 0:
                flash('Unable to generate bill: appointment has no valid consultation fee.', 'danger')
                db.session.rollback()
                return redirect(url_for('patients.patient_view_appointment', id=appointment.appointment_id))

            bill.total_amount = total
            bill.update_status()
            db.session.commit()
            flash('Bill generated successfully!', 'success')
            return redirect(url_for('billing.view_bill', id=bill.bill_id))

        except Exception as e:
            db.session.rollback()
            if str(e) != "No items":
                flash(f'Error generating bill: {str(e)}', 'danger')

    if patient_user:
        patients = [current_patient]
        appointments = Appointment.query.filter_by(
            status='completed',
            patient_id=current_patient.patient_id
        ).order_by(Appointment.appointment_date.desc()).all()
    else:
        patients = Patient.query.order_by(Patient.last_name).all()
        appointments = Appointment.query.filter_by(status='completed').order_by(
            Appointment.appointment_date.desc()
        ).all()
    preselect = request.args.get('patient_id', type=int)
    preselect_appointment = request.args.get('appointment_id', type=int)
    default_item_description = ''
    default_item_price = ''
    if patient_user and preselect_appointment:
        selected_appt = Appointment.query.filter_by(
            appointment_id=preselect_appointment,
            patient_id=current_patient.patient_id,
            status='completed'
        ).first()
        if selected_appt:
            default_item_description = f"Consultation Fee - {selected_appt.doctor.full_name}"
            default_item_price = f"{float(selected_appt.doctor.consultation_fee or 0):.2f}"
    if patient_user:
        preselect = current_patient.patient_id
    return render_template(
        'billing/generate.html',
        patients=patients,
        appointments=appointments,
        preselect=preselect,
        preselect_appointment=preselect_appointment,
        is_patient_user=patient_user,
        default_item_description=default_item_description,
        default_item_price=default_item_price
    )


@billing_bp.route('/<int:id>')
@login_required
def view_bill(id):
    bill = Bill.query.get_or_404(id)
    if not _can_access_bill(bill):
        flash('You do not have permission to view this bill.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('billing/view.html', bill=bill)


@billing_bp.route('/<int:id>/print')
@login_required
def print_bill(id):
    bill = Bill.query.get_or_404(id)
    if not _can_access_bill(bill):
        flash('You do not have permission to print this bill.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('billing/invoice.html', bill=bill)


@billing_bp.route('/<int:id>/payment', methods=['GET', 'POST'])
@login_required
def record_payment(id):
    bill = Bill.query.get_or_404(id)
    if not _can_access_bill(bill):
        flash('You do not have permission to pay this bill.', 'danger')
        return redirect(url_for('auth.login'))

    if current_user.is_patient():
        allowed_methods = ['Online', 'Cash', 'Card']
    else:
        allowed_methods = ['Cash', 'Card', 'Bank Transfer', 'Insurance', 'Online']

    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            method = request.form['payment_method']
            if method not in allowed_methods:
                flash('Selected payment method is not allowed.', 'danger')
                return render_template('billing/payment.html', bill=bill, allowed_methods=allowed_methods)

            if amount <= 0:
                flash('Payment amount must be positive.', 'danger')
            elif amount > bill.get_balance():
                flash(f'Amount exceeds balance of ${bill.get_balance():.2f}.', 'danger')
            else:
                bill.record_payment(amount, method)
                flash(f'Payment of ${amount:.2f} recorded.', 'success')
                return redirect(url_for('billing.view_bill', id=id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording payment: {str(e)}', 'danger')

    return render_template('billing/payment.html', bill=bill, allowed_methods=allowed_methods)


@billing_bp.route('/patient/<int:patient_id>/bills')
@login_required
def patient_bills(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if current_user.is_patient():
        own_patient = _get_current_patient()
        if not own_patient or own_patient.patient_id != patient_id:
            flash('You do not have permission to view these bills.', 'danger')
            return redirect(url_for('auth.login'))
    bills = Bill.query.filter_by(patient_id=patient_id).order_by(Bill.bill_date.desc()).all()
    return render_template('billing/patient_bills.html', patient=patient, bills=bills)


@billing_bp.route('/export')
@login_required
@role_required('admin', 'billing')
def export_bills():
    bills = Bill.query.join(Patient).order_by(Bill.bill_date.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Bill ID', 'Patient', 'Date', 'Total', 'Paid', 'Balance', 'Status'])

    for b in bills:
        writer.writerow([
            b.bill_id, b.patient.full_name,
            b.bill_date.strftime('%Y-%m-%d'),
            float(b.total_amount), float(b.paid_amount),
            b.get_balance(), b.status
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=bills_export.csv'}
    )
