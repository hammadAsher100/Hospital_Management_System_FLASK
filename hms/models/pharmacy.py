from datetime import datetime, date
from hms import db_operations


class Medicine:
    """Medicine model - replaced SQLAlchemy ORM with database operations"""
    
    def __init__(self, medicine_id: int, name: str, unit_price: float, category: str = None,
                 manufacturer: str = None, stock_quantity: int = 0, reorder_level: int = 10,
                 expiry_date: date = None):
        self.medicine_id = medicine_id
        self.name = name
        self.category = category
        self.manufacturer = manufacturer
        self.unit_price = float(unit_price)
        self.stock_quantity = stock_quantity
        self.reorder_level = reorder_level
        self.expiry_date = expiry_date

    def reduce_stock(self, quantity: int) -> bool:
        if self.stock_quantity >= quantity:
            db_operations.update_medicine_stock(self.medicine_id, -quantity)
            self.stock_quantity -= quantity
            return True
        return False

    def add_stock(self, quantity: int):
        db_operations.update_medicine_stock(self.medicine_id, quantity)
        self.stock_quantity += quantity

    def is_low_stock(self) -> bool:
        return self.stock_quantity <= self.reorder_level

    def needs_reorder(self) -> bool:
        return self.stock_quantity < self.reorder_level

    def __repr__(self):
        return f'<Medicine {self.name}>'
    
    @staticmethod
    def get_by_id(medicine_id: int) -> 'Medicine':
        """Get medicine by ID"""
        med_data = db_operations.get_medicine_by_id(medicine_id)
        if not med_data:
            return None
        return Medicine(
            medicine_id=med_data.medicine_id,
            name=med_data.name,
            category=med_data.category,
            manufacturer=med_data.manufacturer,
            unit_price=med_data.unit_price,
            stock_quantity=med_data.stock_quantity,
            reorder_level=med_data.reorder_level,
            expiry_date=med_data.expiry_date
        )
    
    @staticmethod
    def list_all(search: str = None, category: str = None, skip: int = 0, take: int = 50):
        """List medicines"""
        meds_data = db_operations.list_medicines(search, category, skip, take)
        return [
            Medicine(
                medicine_id=m.medicine_id,
                name=m.name,
                category=m.category,
                manufacturer=m.manufacturer,
                unit_price=m.unit_price,
                stock_quantity=m.stock_quantity,
                reorder_level=m.reorder_level,
                expiry_date=m.expiry_date
            ) for m in meds_data
        ]
    
    @staticmethod
    def get_low_stock():
        """Get medicines with low stock"""
        meds_data = db_operations.get_low_stock_medicines()
        return [
            Medicine(
                medicine_id=m.medicine_id,
                name=m.name,
                category=m.category,
                manufacturer=m.manufacturer,
                unit_price=m.unit_price,
                stock_quantity=m.stock_quantity,
                reorder_level=m.reorder_level,
                expiry_date=m.expiry_date
            ) for m in meds_data
        ]


class Prescription:
    """Prescription model - replaced SQLAlchemy ORM with database operations"""
    
    def __init__(self, prescription_id: int, patient_id: int, doctor_id: int,
                 appointment_id: int = None, prescribed_date: datetime = None,
                 notes: str = None, is_dispensed: bool = False):
        self.prescription_id = prescription_id
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.appointment_id = appointment_id
        self.prescribed_date = prescribed_date or datetime.utcnow()
        self.notes = notes
        self.is_dispensed = is_dispensed
        self.items = []

    def __repr__(self):
        return f'<Prescription {self.prescription_id}>'
    
    @staticmethod
    def get_by_id(prescription_id: int) -> 'Prescription':
        """Get prescription by ID"""
        presc_data = db_operations.get_prescription_by_id(prescription_id)
        if not presc_data:
            return None
        return Prescription(
            prescription_id=presc_data.prescription_id,
            patient_id=presc_data.patient_id,
            doctor_id=presc_data.doctor_id,
            appointment_id=presc_data.appointment_id,
            prescribed_date=presc_data.prescribed_date,
            notes=presc_data.notes,
            is_dispensed=presc_data.is_dispensed
        )
    
    @staticmethod
    def list_all(patient_id: int = None, doctor_id: int = None, is_dispensed: bool = None,
                skip: int = 0, take: int = 50):
        """List prescriptions"""
        presc_data = db_operations.list_prescriptions(patient_id, doctor_id, is_dispensed, skip, take)
        return [
            Prescription(
                prescription_id=p.prescription_id,
                patient_id=p.patient_id,
                doctor_id=p.doctor_id,
                appointment_id=p.appointment_id,
                prescribed_date=p.prescribed_date,
                notes=p.notes,
                is_dispensed=p.is_dispensed
            ) for p in presc_data
        ]


class PrescriptionItem:
    """Prescription Item model - replaced SQLAlchemy ORM with database operations"""
    
    def __init__(self, pres_item_id: int, prescription_id: int, medicine_id: int,
                 dosage: str, frequency: str, duration: str, quantity: int = 1):
        self.pres_item_id = pres_item_id
        self.prescription_id = prescription_id
        self.medicine_id = medicine_id
        self.dosage = dosage
        self.frequency = frequency
        self.duration = duration
        self.quantity = quantity

    def __repr__(self):
        return f'<PrescriptionItem {self.pres_item_id}>'
