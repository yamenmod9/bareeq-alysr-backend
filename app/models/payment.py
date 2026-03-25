"""
Payment Model - Customer payments against transactions
"""
from datetime import datetime
from app.database import db


class Payment(db.Model):
    """
    Payment records for customer repayments
    """
    __tablename__ = "payments"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    repayment_schedule_id = db.Column(db.Integer, db.ForeignKey("repayment_schedules.id"), nullable=True)
    
    # Payment Details
    amount = db.Column(db.Float, nullable=False)
    
    # Payment Method (for future expansion)
    payment_method = db.Column(db.String(50), default="wallet")  # wallet, card, bank_transfer
    
    # Status: pending, completed, failed, refunded
    status = db.Column(db.String(20), default="completed", index=True)
    
    # Reference
    payment_reference = db.Column(db.String(50), unique=True, nullable=False)
    external_reference = db.Column(db.String(100), nullable=True)  # Payment gateway reference
    
    # Timestamps
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Notes
    notes = db.Column(db.Text, nullable=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.payment_reference:
            self.payment_reference = self._generate_reference()
    
    def _generate_reference(self):
        """Generate unique payment reference"""
        import uuid
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique = uuid.uuid4().hex[:6].upper()
        return f"PAY-{timestamp}-{unique}"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "payment_reference": self.payment_reference,
            "transaction_id": self.transaction_id,
            "customer_id": self.customer_id,
            "repayment_schedule_id": self.repayment_schedule_id,
            "amount": self.amount,
            "payment_method": self.payment_method,
            "status": self.status,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f"<Payment {self.payment_reference} - {self.amount} SAR>"
