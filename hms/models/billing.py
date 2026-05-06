from datetime import datetime
from hms import db_operations


class Bill:
    """Bill model - replaced SQLAlchemy ORM with database operations"""
    
    def __init__(self, bill_id: int, patient_id: int, appointment_id: int = None,
                 admission_id: int = None, bill_date: datetime = None, total_amount: float = 0,
                 paid_amount: float = 0, status: str = 'pending', payment_method: str = None):
        self.bill_id = bill_id
        self.patient_id = patient_id
        self.appointment_id = appointment_id
        self.admission_id = admission_id
        self.bill_date = bill_date or datetime.utcnow()
        self.total_amount = float(total_amount)
        self.paid_amount = float(paid_amount)
        self.status = status
        self.payment_method = payment_method
        self.items = []

    def calculate_total(self):
        self.total_amount = sum(float(item.total_price) for item in self.items)
        self.update_status()

    def get_balance(self):
        return self.total_amount - self.paid_amount

    def record_payment(self, amount: float, method: str):
        db_operations.record_payment(self.bill_id, amount, method)
        self.paid_amount += float(amount)
        self.payment_method = method
        self.update_status()

    def update_status(self):
        balance = self.get_balance()
        if balance <= 0:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        else:
            self.status = 'pending'

    @property
    def status_badge(self):
        badges = {'paid': 'success', 'pending': 'danger', 'partial': 'warning'}
        return badges.get(self.status, 'secondary')

    def __repr__(self):
        return f'<Bill {self.bill_id} - {self.status}>'
    
    @staticmethod
    def get_by_id(bill_id: int) -> 'Bill':
        """Get bill by ID"""
        bill_data = db_operations.get_bill_by_id(bill_id)
        if not bill_data:
            return None
        return Bill(
            bill_id=bill_data.bill_id,
            patient_id=bill_data.patient_id,
            appointment_id=bill_data.appointment_id,
            admission_id=bill_data.admission_id,
            bill_date=bill_data.bill_date,
            total_amount=bill_data.total_amount,
            paid_amount=bill_data.paid_amount,
            status=bill_data.status,
            payment_method=bill_data.payment_method
        )
    
    @staticmethod
    def list_all(patient_id: int = None, status: str = None, skip: int = 0, take: int = 50):
        """List bills"""
        bills_data = db_operations.list_bills(patient_id, status, skip, take)
        return [
            Bill(
                bill_id=b.bill_id,
                patient_id=b.patient_id,
                appointment_id=b.appointment_id,
                admission_id=b.admission_id,
                bill_date=b.bill_date,
                total_amount=b.total_amount,
                paid_amount=b.paid_amount,
                status=b.status,
                payment_method=b.payment_method
            ) for b in bills_data
        ]


class BillItem:
    """Bill Item model - replaced SQLAlchemy ORM with database operations"""
    
    def __init__(self, item_id: int, bill_id: int, description: str, quantity: int,
                 unit_price: float, total_price: float):
        self.item_id = item_id
        self.bill_id = bill_id
        self.description = description
        self.quantity = quantity
        self.unit_price = float(unit_price)
        self.total_price = float(total_price)

    def __repr__(self):
        return f'<BillItem {self.description}>'
