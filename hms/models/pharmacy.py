from hms import db
from datetime import datetime


class Medicine(db.Model):
    __tablename__ = 'Medicines'

    medicine_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    manufacturer = db.Column(db.String(100))
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    stock_quantity = db.Column(db.Integer, default=0)
    reorder_level = db.Column(db.Integer, default=10)
    expiry_date = db.Column(db.Date)

    prescription_items = db.relationship('PrescriptionItem', back_populates='medicine', lazy='dynamic')

    def reduce_stock(self, quantity):
        if self.stock_quantity >= quantity:
            self.stock_quantity -= quantity
            db.session.commit()
            return True
        return False

    def add_stock(self, quantity):
        self.stock_quantity += quantity
        db.session.commit()

    def is_low_stock(self):
        return self.stock_quantity <= self.reorder_level

    def needs_reorder(self):
        return self.stock_quantity < self.reorder_level

    def __repr__(self):
        return f'<Medicine {self.name}>'


class Prescription(db.Model):
    __tablename__ = 'Prescriptions'

    prescription_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('Patients.patient_id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('Doctors.doctor_id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('Appointments.appointment_id'), nullable=True)
    prescribed_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    is_dispensed = db.Column(db.Boolean, default=False)

    patient = db.relationship('Patient', back_populates='prescriptions')
    doctor = db.relationship('Doctor', back_populates='prescriptions')
    appointment = db.relationship('Appointment', back_populates='prescriptions')
    items = db.relationship('PrescriptionItem', back_populates='prescription', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Prescription {self.prescription_id}>'


class PrescriptionItem(db.Model):
    __tablename__ = 'Prescription_Items'

    pres_item_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('Prescriptions.prescription_id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('Medicines.medicine_id'), nullable=False)
    dosage = db.Column(db.String(50))
    frequency = db.Column(db.String(50))
    duration = db.Column(db.String(50))
    quantity = db.Column(db.Integer, default=1)

    prescription = db.relationship('Prescription', back_populates='items')
    medicine = db.relationship('Medicine', back_populates='prescription_items')

    def __repr__(self):
        return f'<PrescriptionItem {self.pres_item_id}>'
