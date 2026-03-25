"""
Merchant Model - Shop owners using BNPL platform
"""
from datetime import datetime
from app.database import db


class Merchant(db.Model):
    """
    Merchant model for shop owners
    Merchants send purchase requests to customers
    """
    __tablename__ = "merchants"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    
    # Business Info
    shop_name = db.Column(db.String(255), nullable=False)
    shop_name_ar = db.Column(db.String(255), nullable=True)  # Arabic name
    commercial_registration = db.Column(db.String(50), unique=True, nullable=True)  # CR Number
    vat_number = db.Column(db.String(20), nullable=True)
    
    # Bank Details for Settlement
    bank_name = db.Column(db.String(100), nullable=True)
    bank_account = db.Column(db.String(50), nullable=True)
    iban = db.Column(db.String(34), nullable=True)
    
    # Contact
    business_phone = db.Column(db.String(20), nullable=True)
    business_email = db.Column(db.String(255), nullable=True)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=True)
    
    # Status
    status = db.Column(db.String(20), default="active")  # active, suspended, pending_approval
    is_verified = db.Column(db.Boolean, default=False)
    
    # Statistics
    total_transactions = db.Column(db.Integer, default=0)
    total_volume = db.Column(db.Float, default=0.0)  # Total transaction volume
    
    # Balance (net amount after commission deductions)
    balance = db.Column(db.Float, default=0.0, nullable=False)
    total_commission_paid = db.Column(db.Float, default=0.0, nullable=False)  # Track total commission paid to platform
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    branches = db.relationship("Branch", backref="merchant", lazy="dynamic", cascade="all, delete-orphan")
    purchase_requests = db.relationship("PurchaseRequest", backref="merchant", lazy="dynamic")
    transactions = db.relationship("Transaction", backref="merchant", lazy="dynamic")
    settlements = db.relationship("Settlement", backref="merchant", lazy="dynamic")
    
    def increment_stats(self, amount: float):
        """Update transaction statistics"""
        self.total_transactions += 1
        self.total_volume += amount
    
    def add_to_balance(self, net_amount: float, commission_amount: float):
        """Add settlement amount to merchant balance (after commission)"""
        self.balance += net_amount
        self.total_commission_paid += commission_amount
    
    def withdraw_balance(self, amount: float) -> bool:
        """Withdraw from merchant balance"""
        if amount > self.balance:
            return False
        self.balance -= amount
        return True
    
    def to_dict(self, include_branches=False):
        """Convert to dictionary"""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "shop_name": self.shop_name,
            "shop_name_ar": self.shop_name_ar,
            "commercial_registration": self.commercial_registration,
            "status": self.status,
            "is_verified": self.is_verified,
            "total_transactions": self.total_transactions,
            "total_volume": self.total_volume,
            "balance": self.balance,
            "total_commission_paid": self.total_commission_paid,
            "city": self.city,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        if include_branches:
            data["branches"] = [b.to_dict() for b in self.branches]
        return data
    
    def __repr__(self):
        return f"<Merchant {self.shop_name}>"


class Branch(db.Model):
    """
    Merchant branch locations
    """
    __tablename__ = "branches"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchants.id"), nullable=False)
    
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    purchase_requests = db.relationship("PurchaseRequest", backref="branch", lazy="dynamic")
    
    def to_dict(self):
        return {
            "id": self.id,
            "merchant_id": self.merchant_id,
            "name": self.name,
            "address": self.address,
            "city": self.city,
            "phone": self.phone,
            "is_active": self.is_active
        }
    
    def __repr__(self):
        return f"<Branch {self.name}>"
