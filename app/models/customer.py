"""
Customer Model - BNPL Customer with credit limit
"""
import secrets
from datetime import datetime
from app.database import db
from app.config import Config


def generate_customer_code() -> str:
    """Generate a unique 8-character alphanumeric customer code"""
    # Use uppercase letters and digits, excluding ambiguous characters (0, O, I, L)
    alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(8))


class Customer(db.Model):
    """
    Customer model for BNPL service
    Each customer has a credit limit and balance tracking
    """
    __tablename__ = "customers"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    
    # Unique customer code for merchants to identify customers
    customer_code = db.Column(db.String(8), unique=True, nullable=False, default=generate_customer_code)
    
    # Credit Management
    credit_limit = db.Column(db.Float, default=Config.DEFAULT_CREDIT_LIMIT, nullable=False)
    available_balance = db.Column(db.Float, default=Config.DEFAULT_CREDIT_LIMIT, nullable=False)
    outstanding_balance = db.Column(db.Float, default=0.0, nullable=False)
    
    # Customer Status
    status = db.Column(db.String(20), default="active")  # active, suspended, blocked
    risk_score = db.Column(db.Integer, default=50)  # 0-100, higher = lower risk
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    purchase_requests = db.relationship("PurchaseRequest", backref="customer", lazy="dynamic")
    transactions = db.relationship("Transaction", backref="customer", lazy="dynamic")
    payments = db.relationship("Payment", backref="customer", lazy="dynamic")
    repayment_plans = db.relationship("RepaymentPlan", backref="customer", lazy="dynamic")
    limit_history = db.relationship("CustomerLimitHistory", backref="customer", lazy="dynamic")
    
    def can_afford(self, amount: float) -> bool:
        """Check if customer has enough available balance"""
        return self.available_balance >= amount and self.status == "active"
    
    def deduct_balance(self, amount: float) -> bool:
        """Deduct amount from available balance"""
        if not self.can_afford(amount):
            return False
        self.available_balance -= amount
        self.outstanding_balance += amount
        return True
    
    def restore_balance(self, amount: float):
        """Restore balance (for cancelled transactions or payments)"""
        self.available_balance += amount
        self.outstanding_balance -= amount
        if self.outstanding_balance < 0:
            self.outstanding_balance = 0
    
    def update_credit_limit(self, new_limit: float) -> bool:
        """Update credit limit and adjust available balance"""
        if new_limit < self.outstanding_balance:
            return False  # Cannot reduce below outstanding
        
        difference = new_limit - self.credit_limit
        self.credit_limit = new_limit
        self.available_balance += difference
        return True
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "customer_code": self.customer_code,
            "credit_limit": self.credit_limit,
            "available_balance": self.available_balance,
            "outstanding_balance": self.outstanding_balance,
            "status": self.status,
            "risk_score": self.risk_score,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f"<Customer {self.id} - Limit: {self.credit_limit} SAR>"


class CustomerLimitHistory(db.Model):
    """
    Track customer credit limit changes for audit
    """
    __tablename__ = "customer_limit_history"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    
    previous_limit = db.Column(db.Float, nullable=False)
    new_limit = db.Column(db.Float, nullable=False)
    requested_limit = db.Column(db.Float, nullable=False)
    
    status = db.Column(db.String(20), default="approved")  # pending, approved, rejected
    reason = db.Column(db.String(255), nullable=True)
    approved_by = db.Column(db.String(50), default="auto")  # auto, admin_id
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "previous_limit": self.previous_limit,
            "new_limit": self.new_limit,
            "requested_limit": self.requested_limit,
            "status": self.status,
            "reason": self.reason,
            "approved_by": self.approved_by,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
