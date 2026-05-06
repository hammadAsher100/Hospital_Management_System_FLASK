import csv
import io
from datetime import datetime
from math import ceil
from types import SimpleNamespace

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from hms import db_operations
from hms.utils import role_required

billing_bp = Blueprint('billing', __name__)


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


def _status_badge(status):
    return {'paid': 'success', 'pending': 'danger', 'partial': 'warning'}.get(status, 'secondary')


def _to_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.strptime(str(value)[:19], '%Y-%m-%d %H:%M:%S')


def _map_patient(p):
    return SimpleNamespace(
        patient_id=p.patient_id,
        full_name=getattr(p, 'full_name', f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip()),
        phone=getattr(p, 'phone', ''),
        email=getattr(p, 'email', None),
        address=getattr(p, 'address', None),
        blood_group=getattr(p, 'blood_group', None),
    )


def _map_bill(b):
    bill = SimpleNamespace(**b.__dict__)
    bill.bill_date = _to_datetime(b.bill_date)
    bill.total_amount = float(b.total_amount or 0)
    bill.paid_amount = float(b.paid_amount or 0)
    bill.get_balance = lambda x=bill: x.total_amount - x.paid_amount
    bill.status_badge = _status_badge(b.status)
    bill.patient = SimpleNamespace(
        full_name=getattr(b, 'patient_full_name', ''),
        phone=getattr(b, 'patient_phone', ''),
        email=getattr(b, 'patient_email', None),
        address=getattr(b, 'patient_address', None),
        blood_group=getattr(b, 'patient_blood_group', None),
    )
    items = db_operations.get_bill_items(b.bill_id)
    bill.items = [
        SimpleNamespace(
            item_id=i.item_id,
            bill_id=i.bill_id,
            description=i.description,
            quantity=int(i.quantity),
            unit_price=float(i.unit_price or 0),
            total_price=float(i.total_price or 0),
        )
        for i in items
    ]
    return bill


def _get_current_patient():
    patient = db_operations.get_patient_by_user_id(current_user.user_id)
    return _map_patient(patient) if patient else None


def _get_bill_or_none(bill_id):
    b = db_operations.get_bill_by_id(bill_id)
    return _map_bill(b) if b else None


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
    per_page = 15
    skip = (page - 1) * per_page

    patient_id = None
    if current_user.is_patient():
        patient = _get_current_patient()
        if not patient:
            flash('Patient profile not found.', 'danger')
            return redirect(url_for('auth.logout'))
        patient_id = patient.patient_id

    total = db_operations.count_bills(patient_id=patient_id, status=status_filter or None)
    raw_bills = db_operations.list_bills(
        patient_id=patient_id,
        status=status_filter or None,
        skip=skip,
        take=per_page,
    )
    bills = SimplePagination([_map_bill(b) for b in raw_bills], page, per_page, total)
    return render_template('billing/list.html', bills=bills, status_filter=status_filter)


@billing_bp.route('/generate', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'billing', 'patient')
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

            appointment = None
            if appointment_id:
                appointment = db_operations.get_appointment_by_id(int(appointment_id))
                if not appointment:
                    flash('Selected appointment does not exist.', 'danger')
                    return redirect(url_for('billing.generate_bill'))
                if appointment.patient_id != patient_id:
                    flash('Selected appointment does not belong to this patient.', 'danger')
                    return redirect(url_for('billing.generate_bill'))
                if appointment.status != 'completed':
                    flash('Bills can only be generated for completed appointments.', 'danger')
                    return redirect(url_for('billing.generate_bill'))

                existing_bill = db_operations.get_bill_by_appointment_id(appointment.appointment_id)
                if existing_bill:
                    flash('A bill is already generated for this appointment.', 'warning')
                    return redirect(url_for('billing.view_bill', id=existing_bill.bill_id))

            if patient_user and appointment and (not descriptions or not any(d.strip() for d in descriptions)):
                descriptions = [f"Consultation Fee - {appointment.doctor_full_name}"]
                quantities = ['1']
                unit_prices = [str(float(getattr(appointment, 'consultation_fee', 0) or 0))]

            if not descriptions or not any(d.strip() for d in descriptions):
                flash('Please add at least one item.', 'danger')
                raise ValueError('No items')

            if patient_user and len([d for d in descriptions if d and d.strip()]) > 1:
                flash('Patients can only generate a bill with one item.', 'danger')
                return redirect(url_for('billing.generate_bill'))

            bill_id = db_operations.create_bill(
                patient_id=patient_id,
                appointment_id=int(appointment_id) if appointment_id else None,
                payment_method=payment_method,
                total_amount=0,
            )

            total = 0
            for desc, qty, price in zip(descriptions, quantities, unit_prices):
                if desc.strip():
                    qty_int = int(qty) if qty else 1
                    price_float = float(price) if price else 0
                    total += qty_int * price_float
                    db_operations.add_bill_item(
                        bill_id=bill_id,
                        description=desc,
                        quantity=qty_int,
                        unit_price=price_float,
                    )

            if patient_user and appointment and total <= 0:
                flash('Unable to generate bill: appointment has no valid consultation fee.', 'danger')
                return redirect(url_for('patients.patient_view_appointment', id=appointment.appointment_id))

            db_operations.refresh_bill_totals(bill_id)
            flash('Bill generated successfully!', 'success')
            return redirect(url_for('billing.view_bill', id=bill_id))

        except Exception as e:
            if str(e) != 'No items':
                flash(f'Error generating bill: {str(e)}', 'danger')

    if patient_user:
        patients = [current_patient]
        appointments = db_operations.list_completed_appointments(patient_id=current_patient.patient_id, skip=0, take=500)
    else:
        patients = [_map_patient(p) for p in db_operations.list_patients(skip=0, take=10000)]
        appointments = db_operations.list_completed_appointments(skip=0, take=10000)

    preselect = request.args.get('patient_id', type=int)
    preselect_appointment = request.args.get('appointment_id', type=int)
    default_item_description = ''
    default_item_price = ''
    if patient_user and preselect_appointment:
        selected_appt = next((a for a in appointments if a.appointment_id == preselect_appointment), None)
        if selected_appt:
            default_item_description = f"Consultation Fee - {selected_appt.doctor_full_name}"
            default_item_price = f"{float(getattr(selected_appt, 'consultation_fee', 0) or 0):.2f}"
    if patient_user:
        preselect = current_patient.patient_id

    for appt in appointments:
        if not hasattr(appt, 'patient'):
            appt.patient = SimpleNamespace(full_name=getattr(appt, 'patient_full_name', ''))

    return render_template(
        'billing/generate.html',
        patients=patients,
        appointments=appointments,
        preselect=preselect,
        preselect_appointment=preselect_appointment,
        is_patient_user=patient_user,
        default_item_description=default_item_description,
        default_item_price=default_item_price,
    )


@billing_bp.route('/<int:id>')
@login_required
def view_bill(id):
    bill = _get_bill_or_none(id)
    if not bill:
        flash('Bill not found.', 'danger')
        return redirect(url_for('billing.list_bills'))
    if not _can_access_bill(bill):
        flash('You do not have permission to view this bill.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('billing/view.html', bill=bill)


@billing_bp.route('/<int:id>/print')
@login_required
def print_bill(id):
    bill = _get_bill_or_none(id)
    if not bill:
        flash('Bill not found.', 'danger')
        return redirect(url_for('billing.list_bills'))
    if not _can_access_bill(bill):
        flash('You do not have permission to print this bill.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('billing/invoice.html', bill=bill)


@billing_bp.route('/<int:id>/payment', methods=['GET', 'POST'])
@login_required
def record_payment(id):
    bill = _get_bill_or_none(id)
    if not bill:
        flash('Bill not found.', 'danger')
        return redirect(url_for('billing.list_bills'))
    if not _can_access_bill(bill):
        flash('You do not have permission to pay this bill.', 'danger')
        return redirect(url_for('auth.login'))

    allowed_methods = ['Online', 'Cash', 'Card'] if current_user.is_patient() else ['Cash', 'Card', 'Bank Transfer', 'Insurance', 'Online']

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
                db_operations.record_payment(id, amount, method)
                flash(f'Payment of ${amount:.2f} recorded.', 'success')
                return redirect(url_for('billing.view_bill', id=id))
        except Exception as e:
            flash(f'Error recording payment: {str(e)}', 'danger')

    bill = _get_bill_or_none(id)
    return render_template('billing/payment.html', bill=bill, allowed_methods=allowed_methods)


@billing_bp.route('/patient/<int:patient_id>/bills')
@login_required
def patient_bills(patient_id):
    patient_raw = db_operations.get_patient_by_id(patient_id)
    if not patient_raw:
        flash('Patient not found.', 'danger')
        return redirect(url_for('billing.list_bills'))
    patient = _map_patient(patient_raw)

    if current_user.is_patient():
        own_patient = _get_current_patient()
        if not own_patient or own_patient.patient_id != patient_id:
            flash('You do not have permission to view these bills.', 'danger')
            return redirect(url_for('auth.login'))

    bills = [_map_bill(b) for b in db_operations.list_bills(patient_id=patient_id, skip=0, take=10000)]
    return render_template('billing/patient_bills.html', patient=patient, bills=bills)


@billing_bp.route('/export')
@login_required
@role_required('admin', 'billing')
def export_bills():
    bills = [_map_bill(b) for b in db_operations.list_bills(skip=0, take=10000)]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Bill ID', 'Patient', 'Date', 'Total', 'Paid', 'Balance', 'Status'])

    for b in bills:
        writer.writerow([
            b.bill_id,
            b.patient.full_name,
            b.bill_date.strftime('%Y-%m-%d'),
            float(b.total_amount),
            float(b.paid_amount),
            b.get_balance(),
            b.status,
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=bills_export.csv'},
    )
