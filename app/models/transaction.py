"""
Transaction Model - Created when purchase request is accepted
"""
from datetime import datetime, timedelta
from app.database import db
from app.config import Config


class Transaction(db.Model):
    """
    Transaction created after customer accepts a purchase request
    Tracks the BNPL transaction lifecycle
    """
    __tablename__ = "transactions"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchants.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey("purchase_requests.id"), nullable=False)
    
    # Financial Details
    total_amount = db.Column(db.Float, nullable=False)
    paid_amount = db.Column(db.Float, default=0.0, nullable=False)
    remaining_amount = db.Column(db.Float, nullable=False)
    
    # Commission (Platform takes from merchant)
    commission_rate = db.Column(db.Float, default=Config.PLATFORM_COMMISSION_RATE)
    commission_amount = db.Column(db.Float, nullable=False)  # total_amount * commission_rate
    merchant_net_amount = db.Column(db.Float, nullable=False)  # total_amount - commission
    
    # Status: active, completed, overdue, defaulted, cancelled
    status = db.Column(db.String(20), default="active", index=True)
    
    # Due Date
    due_date = db.Column(db.DateTime, nullable=False)
    
    # Reference
    transaction_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Repayment Plan (if selected)
    repayment_plan_id = db.Column(db.Integer, db.ForeignKey("repayment_plans.id"), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    payments = db.relationship("Payment", backref="transaction", lazy="dynamic")
    purchase_request = db.relationship("PurchaseRequest", foreign_keys=[purchase_request_id],
                                       backref=db.backref("transaction_ref", uselist=False))
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.remaining_amount:
            self.remaining_amount = self.total_amount
        if not self.commission_amount:
            self.commission_amount = self.total_amount * self.commission_rate
        if not self.merchant_net_amount:
            self.merchant_net_amount = self.total_amount - self.commission_amount
        if not self.due_date:
            self.due_date = datetime.utcnow() + timedelta(days=Config.DEFAULT_REPAYMENT_DAYS)
        if not self.transaction_number:
            self.transaction_number = self._generate_transaction_number()
    
    def _generate_transaction_number(self):
        """Generate unique transaction number"""
        import uuid
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique = uuid.uuid4().hex[:6].upper()
        return f"TXN-{timestamp}-{unique}"
    
    @property
    def is_overdue(self) -> bool:
        """Check if transaction is overdue"""
        return datetime.utcnow() > self.due_date and self.remaining_amount > 0
    
    @property
    def is_completed(self) -> bool:
        """Check if transaction is fully paid"""
        return self.remaining_amount <= 0
    
    def record_payment(self, amount: float):
        """Record a payment against this transaction"""
        self.paid_amount += amount
        self.remaining_amount -= amount
        if self.remaining_amount <= 0:
            self.remaining_amount = 0
            self.status = "completed"
            self.completed_at = datetime.utcnow()
    
    def check_and_update_status(self):
        """Check and update transaction status"""
        if self.is_completed:
            self.status = "completed"
            self.completed_at = datetime.utcnow()
        elif self.is_overdue:
            self.status = "overdue"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "transaction_number": self.transaction_number,
            "merchant_id": self.merchant_id,
            "customer_id": self.customer_id,
            "purchase_request_id": self.purchase_request_id,
            "total_amount": self.total_amount,
            "paid_amount": self.paid_amount,
            "remaining_amount": self.remaining_amount,
            "commission_rate": self.commission_rate,
            "commission_amount": self.commission_amount,
            "merchant_net_amount": self.merchant_net_amount,
            "status": self.status,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "repayment_plan_id": self.repayment_plan_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "is_overdue": self.is_overdue
        }
    
    def __repr__(self):
        return f"<Transaction {self.transaction_number} - {self.status}>"
