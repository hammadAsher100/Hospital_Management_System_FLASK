from hms import db
from datetime import datetime


class Doctor(db.Model):
    __tablename__ = 'Doctors'

    doctor_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.user_id'), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    consultation_fee = db.Column(db.Numeric(10, 2), default=0)
    availability_status = db.Column(db.Boolean, default=True)

    # Relationships
    user = db.relationship('User', back_populates='doctor_profile')
    appointments = db.relationship('Appointment', back_populates='doctor', lazy='dynamic')
    admissions = db.relationship('Admission', back_populates='doctor', lazy='dynamic')
    schedules = db.relationship('DoctorSchedule', back_populates='doctor', lazy='dynamic')
    prescriptions = db.relationship('Prescription', back_populates='doctor', lazy='dynamic')

    @property
    def full_name(self):
        return f"Dr. {self.first_name} {self.last_name}"

    def is_available(self):
        return self.availability_status

    def __repr__(self):
        return f'<Doctor {self.full_name}>'


class Nurse(db.Model):
    __tablename__ = 'Nurses'

    nurse_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.user_id'), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    assigned_ward = db.Column(db.String(50))

    # Relationships
    user = db.relationship('User', back_populates='nurse_profile')
    admissions = db.relationship('Admission', back_populates='nurse', lazy='dynamic')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f'<Nurse {self.full_name}>'


class DoctorSchedule(db.Model):
    __tablename__ = 'Doctor_Schedules'

    schedule_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('Doctors.doctor_id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Mon ... 6=Sun
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    max_appointments = db.Column(db.Integer, default=10)

    doctor = db.relationship('Doctor', back_populates='schedules')

    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    @property
    def day_name(self):
        return self.DAY_NAMES[self.day_of_week]

    def __repr__(self):
        return f'<Schedule {self.day_name} {self.start_time}-{self.end_time}>'
