from hms import db
from datetime import datetime


class Admission(db.Model):
    __tablename__ = 'Admissions'

    admission_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('Patients.patient_id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('Doctors.doctor_id'), nullable=False)
    nurse_id = db.Column(db.Integer, db.ForeignKey('Nurses.nurse_id'), nullable=True)
    admission_date = db.Column(db.DateTime, default=datetime.utcnow)
    discharge_date = db.Column(db.DateTime, nullable=True)
    room_number = db.Column(db.String(20))
    diagnosis = db.Column(db.Text)

    patient = db.relationship('Patient', back_populates='admissions')
    doctor = db.relationship('Doctor', back_populates='admissions')
    nurse = db.relationship('Nurse', back_populates='admissions')
    bills = db.relationship('Bill', back_populates='admission', lazy='dynamic')

    @property
    def is_active(self):
        return self.discharge_date is None

    def discharge(self):
        self.discharge_date = datetime.utcnow()
        db.session.commit()

    def __repr__(self):
        return f'<Admission {self.admission_id}>'
