from datetime import datetime
from hms import db_operations


class Admission:
    """Admission model - replaced SQLAlchemy ORM with database operations"""
    
    def __init__(self, admission_id: int, patient_id: int, doctor_id: int,
                 nurse_id: int = None, admission_date: datetime = None,
                 discharge_date: datetime = None, room_number: str = None,
                 diagnosis: str = None):
        self.admission_id = admission_id
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.nurse_id = nurse_id
        self.admission_date = admission_date or datetime.utcnow()
        self.discharge_date = discharge_date
        self.room_number = room_number
        self.diagnosis = diagnosis

    @property
    def is_active(self):
        return self.discharge_date is None

    def discharge(self):
        db_operations.discharge_patient(self.admission_id)
        self.discharge_date = datetime.utcnow()

    def __repr__(self):
        return f'<Admission {self.admission_id}>'
    
    @staticmethod
    def get_by_id(admission_id: int) -> 'Admission':
        """Get admission by ID"""
        adm_data = db_operations.get_admission_by_id(admission_id)
        if not adm_data:
            return None
        return Admission(
            admission_id=adm_data.admission_id,
            patient_id=adm_data.patient_id,
            doctor_id=adm_data.doctor_id,
            nurse_id=adm_data.nurse_id,
            admission_date=adm_data.admission_date,
            discharge_date=adm_data.discharge_date,
            room_number=adm_data.room_number,
            diagnosis=adm_data.diagnosis
        )
    
    @staticmethod
    def list_active(skip: int = 0, take: int = 50):
        """List active admissions"""
        adm_data = db_operations.list_active_admissions(skip, take)
        return [
            Admission(
                admission_id=a.admission_id,
                patient_id=a.patient_id,
                doctor_id=a.doctor_id,
                nurse_id=a.nurse_id,
                admission_date=a.admission_date,
                discharge_date=a.discharge_date,
                room_number=a.room_number,
                diagnosis=a.diagnosis
            ) for a in adm_data
        ]
