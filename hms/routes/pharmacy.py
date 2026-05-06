from datetime import datetime
from math import ceil
from types import SimpleNamespace

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from hms import db_operations
from hms.utils import role_required

pharmacy_bp = Blueprint('pharmacy', __name__)


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


def _map_medicine(m):
    med = SimpleNamespace(**m.__dict__)
    med.unit_price = float(med.unit_price or 0)
    med.stock_quantity = int(med.stock_quantity or 0)
    med.reorder_level = int(med.reorder_level or 0)
    med.is_low_stock = lambda x=med: x.stock_quantity <= x.reorder_level
    if getattr(med, 'expiry_date', None):
        try:
            med.expiry_date = datetime.strptime(str(med.expiry_date)[:10], '%Y-%m-%d').date()
        except Exception:
            pass
    return med


def _map_prescription(rx):
    p = SimpleNamespace(**rx.__dict__)
    p.prescribed_date = datetime.strptime(str(p.prescribed_date)[:19], '%Y-%m-%d %H:%M:%S')
    p.patient = SimpleNamespace(full_name=getattr(p, 'patient_full_name', ''))
    p.doctor = SimpleNamespace(full_name=getattr(p, 'doctor_full_name', ''))
    items = db_operations.get_prescription_items(p.prescription_id)
    p.items = [
        SimpleNamespace(
            medicine=SimpleNamespace(name=getattr(i, 'medicine_name', '')),
            quantity=int(getattr(i, 'quantity', 1) or 1),
            medicine_id=i.medicine_id,
            dosage=getattr(i, 'dosage', None),
            frequency=getattr(i, 'frequency', None),
            duration=getattr(i, 'duration', None),
        )
        for i in items
    ]
    return p


@pharmacy_bp.route('/')
@login_required
def dashboard():
    low_stock = [_map_medicine(m) for m in db_operations.get_low_stock_medicines()]
    total_medicines = db_operations.count_medicines()
    total_prescriptions = db_operations.count_prescriptions()
    pending_dispense = db_operations.count_prescriptions(is_dispensed=False)
    return render_template(
        'pharmacy/dashboard.html',
        low_stock=low_stock,
        total_medicines=total_medicines,
        total_prescriptions=total_prescriptions,
        pending_dispense=pending_dispense,
    )


@pharmacy_bp.route('/medicines')
@login_required
def list_medicines():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    focus_med_id = request.args.get('focus', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 20
    skip = (page - 1) * per_page

    total = db_operations.count_medicines(search=search or None, category=category or None)
    meds = db_operations.list_medicines(search=search or None, category=category or None, skip=skip, take=per_page)
    medicines = SimplePagination([_map_medicine(m) for m in meds], page, per_page, total)
    categories = db_operations.list_medicine_categories()
    return render_template(
        'pharmacy/medicines.html',
        medicines=medicines,
        categories=categories,
        search=search,
        category=category,
        focus_med_id=focus_med_id,
    )


@pharmacy_bp.route('/medicines/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'billing')
def add_medicine():
    if request.method == 'POST':
        try:
            med_id = db_operations.create_medicine(
                name=request.form['name'],
                category=request.form.get('category'),
                manufacturer=request.form.get('manufacturer'),
                unit_price=float(request.form['unit_price']),
                stock_quantity=int(request.form.get('stock_quantity', 0)),
                reorder_level=int(request.form.get('reorder_level', 10)),
                expiry_date=datetime.strptime(request.form['expiry_date'], '%Y-%m-%d').date() if request.form.get('expiry_date') else None,
            )
            if not med_id:
                flash('Could not save medicine — no row id returned from the database.', 'danger')
                return render_template('pharmacy/medicine_form.html', medicine=None)
            med = db_operations.get_medicine_by_id(med_id)
            if not med:
                flash('Medicine may have been saved but could not be reloaded.', 'warning')
                return redirect(url_for('pharmacy.list_medicines'))
            flash(f'{med.name} added to inventory.', 'success')
            return redirect(url_for('pharmacy.list_medicines'))
        except Exception as e:
            flash(f'Error adding medicine: {str(e)}', 'danger')

    return render_template('pharmacy/medicine_form.html', medicine=None)


@pharmacy_bp.route('/medicines/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'billing')
def edit_medicine(id):
    med = db_operations.get_medicine_by_id(id)
    if not med:
        flash('Medicine not found.', 'danger')
        return redirect(url_for('pharmacy.list_medicines'))
    med = _map_medicine(med)

    if request.method == 'POST':
        try:
            db_operations.update_medicine(
                medicine_id=id,
                name=request.form['name'],
                category=request.form.get('category'),
                manufacturer=request.form.get('manufacturer'),
                unit_price=float(request.form['unit_price']),
                reorder_level=int(request.form.get('reorder_level', 10)),
                expiry_date=datetime.strptime(request.form['expiry_date'], '%Y-%m-%d').date() if request.form.get('expiry_date') else None,
            )
            flash(f'{request.form["name"]} updated.', 'success')
            return redirect(url_for('pharmacy.list_medicines'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')

    return render_template('pharmacy/medicine_form.html', medicine=med)


@pharmacy_bp.route('/medicines/restock', methods=['POST'])
@login_required
@role_required('admin', 'billing')
def restock_medicine():
    """Add/remove stock via form body (avoids brittle URL rewriting in JS)."""
    try:
        med_id = int(request.form['medicine_id'])
    except (KeyError, TypeError, ValueError):
        flash('Invalid medicine.', 'danger')
        return redirect(url_for('pharmacy.list_medicines'))

    med = db_operations.get_medicine_by_id(med_id)
    if not med:
        flash('Medicine not found.', 'danger')
        return redirect(url_for('pharmacy.list_medicines'))

    qty = int(request.form.get('quantity', 0))
    action = request.form.get('action', 'add')

    if qty <= 0:
        flash('Quantity must be at least 1.', 'danger')
        return redirect(url_for('pharmacy.list_medicines'))

    if action == 'add':
        db_operations.update_medicine_stock(med_id, qty)
        flash(f'Added {qty} units to {med.name}.', 'success')
    elif action == 'remove':
        if int(med.stock_quantity or 0) >= qty:
            db_operations.update_medicine_stock(med_id, -qty)
            flash(f'Removed {qty} units from {med.name}.', 'warning')
        else:
            flash('Insufficient stock.', 'danger')
    else:
        flash('Invalid stock action.', 'danger')

    return redirect(url_for('pharmacy.list_medicines'))


@pharmacy_bp.route('/medicines/<int:id>/stock', methods=['POST'])
@login_required
@role_required('admin', 'billing')
def update_stock(id):
    med = db_operations.get_medicine_by_id(id)
    if not med:
        flash('Medicine not found.', 'danger')
        return redirect(url_for('pharmacy.list_medicines'))
    qty = int(request.form.get('quantity', 0))
    action = request.form.get('action', 'add')

    if action == 'add':
        db_operations.update_medicine_stock(id, qty)
        flash(f'Added {qty} units to {med.name}.', 'success')
    elif action == 'remove':
        if int(med.stock_quantity or 0) >= qty:
            db_operations.update_medicine_stock(id, -qty)
            flash(f'Removed {qty} units from {med.name}.', 'warning')
        else:
            flash('Insufficient stock.', 'danger')

    return redirect(url_for('pharmacy.list_medicines'))


@pharmacy_bp.route('/prescriptions')
@login_required
def list_prescriptions():
    page = request.args.get('page', 1, type=int)
    dispensed = request.args.get('dispensed', '')
    per_page = 15
    skip = (page - 1) * per_page

    is_dispensed = True if dispensed == 'yes' else False if dispensed == 'no' else None
    doctor_id = None
    if current_user.is_doctor():
        doctor = db_operations.get_doctor_by_user_id(current_user.user_id)
        doctor_id = doctor.doctor_id if doctor else None

    total = db_operations.count_prescriptions(doctor_id=doctor_id, is_dispensed=is_dispensed)
    prescriptions = db_operations.list_prescriptions(doctor_id=doctor_id, is_dispensed=is_dispensed, skip=skip, take=per_page)
    prescriptions_paginated = SimplePagination([_map_prescription(r) for r in prescriptions], page, per_page, total)

    return render_template('pharmacy/prescriptions.html', prescriptions=prescriptions_paginated, dispensed=dispensed)


@pharmacy_bp.route('/prescriptions/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'doctor')
def add_prescription():
    if request.method == 'POST':
        try:
            prescription_id = db_operations.create_prescription(
                patient_id=int(request.form['patient_id']),
                doctor_id=int(request.form['doctor_id']),
                appointment_id=request.form.get('appointment_id') or None,
                notes=request.form.get('notes', ''),
            )

            med_ids = request.form.getlist('medicine_id[]')
            dosages = request.form.getlist('dosage[]')
            frequencies = request.form.getlist('frequency[]')
            durations = request.form.getlist('duration[]')
            quantities = request.form.getlist('quantity[]')

            for mid, dos, freq, dur, qty in zip(med_ids, dosages, frequencies, durations, quantities):
                if mid:
                    db_operations.add_prescription_item(
                        prescription_id=prescription_id,
                        medicine_id=int(mid),
                        dosage=dos,
                        frequency=freq,
                        duration=dur,
                        quantity=int(qty) if qty else 1,
                    )

            flash('Prescription created.', 'success')
            return redirect(url_for('pharmacy.list_prescriptions'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')

    patients = db_operations.list_patients(skip=0, take=10000)
    doctors = db_operations.list_active_doctors()
    medicines = [_map_medicine(m) for m in db_operations.list_medicines(skip=0, take=10000) if int(m.stock_quantity or 0) > 0]
    doctor_id = None
    if current_user.is_doctor():
        doctor = db_operations.get_doctor_by_user_id(current_user.user_id)
        doctor_id = doctor.doctor_id if doctor else None
    return render_template('pharmacy/prescription_form.html', patients=patients, doctors=doctors, medicines=medicines, current_doctor_id=doctor_id)


@pharmacy_bp.route('/prescriptions/<int:id>/dispense', methods=['POST'])
@login_required
@role_required('admin', 'billing')
def dispense_prescription(id):
    prescription = db_operations.get_prescription_by_id(id)
    if not prescription:
        flash('Prescription not found.', 'danger')
        return redirect(url_for('pharmacy.list_prescriptions'))

    if prescription.is_dispensed:
        flash('This prescription has already been dispensed.', 'warning')
        return redirect(url_for('pharmacy.list_prescriptions'))

    try:
        errors = []
        items = db_operations.get_prescription_items(id)
        for item in items:
            med = db_operations.get_medicine_by_id(item.medicine_id)
            if int(med.stock_quantity or 0) < int(item.quantity or 0):
                errors.append(f'Insufficient stock for {med.name}')

        if errors:
            for e in errors:
                flash(e, 'danger')
        else:
            for item in items:
                db_operations.update_medicine_stock(item.medicine_id, -int(item.quantity or 0))
            db_operations.mark_prescription_dispensed(id)
            flash('Medicines dispensed and stock updated.', 'success')
    except Exception as e:
        flash(f'Error dispensing: {str(e)}', 'danger')

    return redirect(url_for('pharmacy.list_prescriptions'))
