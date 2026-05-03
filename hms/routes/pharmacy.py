from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from hms import db
from hms.models.pharmacy import Medicine, Prescription, PrescriptionItem
from hms.models.patient import Patient
from hms.models.doctor import Doctor
from hms.models.appointment import Appointment
from hms.utils import role_required
from datetime import datetime

pharmacy_bp = Blueprint('pharmacy', __name__)


@pharmacy_bp.route('/')
@login_required
def dashboard():
    low_stock = Medicine.query.filter(
        Medicine.stock_quantity <= Medicine.reorder_level
    ).order_by(Medicine.stock_quantity).all()
    total_medicines = Medicine.query.count()
    total_prescriptions = Prescription.query.count()
    pending_dispense = Prescription.query.filter_by(is_dispensed=False).count()
    return render_template('pharmacy/dashboard.html',
                           low_stock=low_stock,
                           total_medicines=total_medicines,
                           total_prescriptions=total_prescriptions,
                           pending_dispense=pending_dispense)


@pharmacy_bp.route('/medicines')
@login_required
def list_medicines():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    page = request.args.get('page', 1, type=int)

    query = Medicine.query
    if search:
        query = query.filter(Medicine.name.ilike(f'%{search}%'))
    if category:
        query = query.filter(Medicine.category == category)

    medicines = query.order_by(Medicine.name).paginate(page=page, per_page=20, error_out=False)
    categories = db.session.query(Medicine.category).distinct().all()
    return render_template('pharmacy/medicines.html', medicines=medicines,
                           categories=[c[0] for c in categories],
                           search=search, category=category)


@pharmacy_bp.route('/medicines/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'billing')
def add_medicine():
    if request.method == 'POST':
        try:
            med = Medicine(
                name=request.form['name'],
                category=request.form.get('category'),
                manufacturer=request.form.get('manufacturer'),
                unit_price=float(request.form['unit_price']),
                stock_quantity=int(request.form.get('stock_quantity', 0)),
                reorder_level=int(request.form.get('reorder_level', 10)),
                expiry_date=datetime.strptime(request.form['expiry_date'], '%Y-%m-%d').date()
                    if request.form.get('expiry_date') else None
            )
            db.session.add(med)
            db.session.commit()
            flash(f'{med.name} added to inventory.', 'success')
            return redirect(url_for('pharmacy.list_medicines'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding medicine: {str(e)}', 'danger')

    return render_template('pharmacy/medicine_form.html', medicine=None)


@pharmacy_bp.route('/medicines/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'billing')
def edit_medicine(id):
    med = Medicine.query.get_or_404(id)

    if request.method == 'POST':
        try:
            med.name = request.form['name']
            med.category = request.form.get('category')
            med.manufacturer = request.form.get('manufacturer')
            med.unit_price = float(request.form['unit_price'])
            med.reorder_level = int(request.form.get('reorder_level', 10))
            if request.form.get('expiry_date'):
                med.expiry_date = datetime.strptime(request.form['expiry_date'], '%Y-%m-%d').date()
            db.session.commit()
            flash(f'{med.name} updated.', 'success')
            return redirect(url_for('pharmacy.list_medicines'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    return render_template('pharmacy/medicine_form.html', medicine=med)


@pharmacy_bp.route('/medicines/<int:id>/stock', methods=['POST'])
@login_required
@role_required('admin', 'billing')
def update_stock(id):
    med = Medicine.query.get_or_404(id)
    qty = int(request.form.get('quantity', 0))
    action = request.form.get('action', 'add')

    if action == 'add':
        med.add_stock(qty)
        flash(f'Added {qty} units to {med.name}.', 'success')
    elif action == 'remove':
        if med.reduce_stock(qty):
            flash(f'Removed {qty} units from {med.name}.', 'warning')
        else:
            flash('Insufficient stock.', 'danger')

    return redirect(url_for('pharmacy.list_medicines'))


@pharmacy_bp.route('/prescriptions')
@login_required
def list_prescriptions():
    page = request.args.get('page', 1, type=int)
    dispensed = request.args.get('dispensed', '')

    query = Prescription.query
    if dispensed == 'yes':
        query = query.filter_by(is_dispensed=True)
    elif dispensed == 'no':
        query = query.filter_by(is_dispensed=False)

    if current_user.is_doctor() and current_user.doctor_profile:
        query = query.filter_by(doctor_id=current_user.doctor_profile.doctor_id)

    prescriptions = query.order_by(Prescription.prescribed_date.desc()).paginate(
        page=page, per_page=15, error_out=False
    )
    return render_template('pharmacy/prescriptions.html', prescriptions=prescriptions, dispensed=dispensed)


@pharmacy_bp.route('/prescriptions/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'doctor')
def add_prescription():
    if request.method == 'POST':
        try:
            prescription = Prescription(
                patient_id=int(request.form['patient_id']),
                doctor_id=int(request.form['doctor_id']),
                appointment_id=request.form.get('appointment_id') or None,
                notes=request.form.get('notes', '')
            )
            db.session.add(prescription)
            db.session.flush()

            med_ids = request.form.getlist('medicine_id[]')
            dosages = request.form.getlist('dosage[]')
            frequencies = request.form.getlist('frequency[]')
            durations = request.form.getlist('duration[]')
            quantities = request.form.getlist('quantity[]')

            for mid, dos, freq, dur, qty in zip(med_ids, dosages, frequencies, durations, quantities):
                if mid:
                    item = PrescriptionItem(
                        prescription_id=prescription.prescription_id,
                        medicine_id=int(mid),
                        dosage=dos,
                        frequency=freq,
                        duration=dur,
                        quantity=int(qty) if qty else 1
                    )
                    db.session.add(item)

            db.session.commit()
            flash('Prescription created.', 'success')
            return redirect(url_for('pharmacy.list_prescriptions'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    patients = Patient.query.order_by(Patient.last_name).all()
    doctors = Doctor.query.all()
    medicines = Medicine.query.filter(Medicine.stock_quantity > 0).order_by(Medicine.name).all()
    doctor_id = current_user.doctor_profile.doctor_id if current_user.is_doctor() and current_user.doctor_profile else None
    return render_template('pharmacy/prescription_form.html',
                           patients=patients, doctors=doctors,
                           medicines=medicines, current_doctor_id=doctor_id)


@pharmacy_bp.route('/prescriptions/<int:id>/dispense', methods=['POST'])
@login_required
@role_required('admin', 'billing')
def dispense_prescription(id):
    prescription = Prescription.query.get_or_404(id)

    if prescription.is_dispensed:
        flash('This prescription has already been dispensed.', 'warning')
        return redirect(url_for('pharmacy.list_prescriptions'))

    try:
        errors = []
        for item in prescription.items:
            if not item.medicine.reduce_stock(item.quantity):
                errors.append(f'Insufficient stock for {item.medicine.name}')

        if errors:
            db.session.rollback()
            for e in errors:
                flash(e, 'danger')
        else:
            prescription.is_dispensed = True
            db.session.commit()
            flash('Medicines dispensed and stock updated.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error dispensing: {str(e)}', 'danger')

    return redirect(url_for('pharmacy.list_prescriptions'))
