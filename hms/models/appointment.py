from hms import db
from datetime import datetime


class Appointment(db.Model):
    __tablename__ = 'Appointments'

    appointment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('Patients.patient_id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('Doctors.doctor_id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, completed, cancelled
    reason = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', back_populates='appointments')
    doctor = db.relationship('Doctor', back_populates='appointments')
    bills = db.relationship('Bill', back_populates='appointment', lazy='dynamic')
    prescriptions = db.relationship('Prescription', back_populates='appointment', lazy='dynamic')

    def cancel(self):
        self.status = 'cancelled'
        db.session.commit()

    def complete(self):
        self.status = 'completed'
        db.session.commit()

    @staticmethod
    def has_conflict(doctor_id, appointment_date, appointment_time, exclude_id=None):
        query = Appointment.query.filter_by(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status='scheduled'
        )
        if exclude_id:
            query = query.filter(Appointment.appointment_id != exclude_id)
        return query.first() is not None

    @property
    def status_badge(self):
        badges = {
            'scheduled': 'primary',
            'completed': 'success',
            'cancelled': 'danger'
        }
        return badges.get(self.status, 'secondary')

    def __repr__(self):
        return f'<Appointment {self.appointment_id} - {self.status}>'
