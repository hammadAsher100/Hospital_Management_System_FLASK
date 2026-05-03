from hms import db
from datetime import datetime


class Bill(db.Model):
    __tablename__ = 'Billing'

    bill_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('Patients.patient_id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('Appointments.appointment_id'), nullable=True)
    admission_id = db.Column(db.Integer, db.ForeignKey('Admissions.admission_id'), nullable=True)
    bill_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Numeric(12, 2), default=0)
    paid_amount = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(db.String(20), default='pending')  # paid, pending, partial
    payment_method = db.Column(db.String(50))

    # Relationships
    patient = db.relationship('Patient', back_populates='bills')
    appointment = db.relationship('Appointment', back_populates='bills')
    admission = db.relationship('Admission', back_populates='bills')
    items = db.relationship('BillItem', back_populates='bill', cascade='all, delete-orphan')

    def calculate_total(self):
        self.total_amount = sum(item.total_price for item in self.items)
        self.update_status()
        db.session.commit()

    def get_balance(self):
        return float(self.total_amount) - float(self.paid_amount)

    def record_payment(self, amount, method):
        self.paid_amount = float(self.paid_amount) + float(amount)
        self.payment_method = method
        self.update_status()
        db.session.commit()

    def update_status(self):
        balance = self.get_balance()
        if balance <= 0:
            self.status = 'paid'
        elif float(self.paid_amount) > 0:
            self.status = 'partial'
        else:
            self.status = 'pending'

    @property
    def status_badge(self):
        badges = {'paid': 'success', 'pending': 'danger', 'partial': 'warning'}
        return badges.get(self.status, 'secondary')

    def __repr__(self):
        return f'<Bill {self.bill_id} - {self.status}>'


class BillItem(db.Model):
    __tablename__ = 'Bill_Items'

    item_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('Billing.bill_id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)

    bill = db.relationship('Bill', back_populates='items')

    def __repr__(self):
        return f'<BillItem {self.description}>'
