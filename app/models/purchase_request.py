"""
Purchase Request Model - Merchant initiates, customer accepts
"""
from datetime import datetime, timedelta
from app.database import db
from app.config import Config


class PurchaseRequest(db.Model):
    """
    Purchase Request from merchant to customer
    Expires after 24 hours if not accepted
    """
    __tablename__ = "purchase_requests"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchants.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=True)
    
    # Product Details
    product_name = db.Column(db.String(255), nullable=False)
    product_description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    
    # Status: pending, accepted, rejected, expired, cancelled
    status = db.Column(db.String(20), default="pending", index=True)
    
    # Expiry
    expires_at = db.Column(db.DateTime, nullable=False)
    
    # Reference
    reference_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    accepted_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    
    # Rejection reason if rejected
    rejection_reason = db.Column(db.String(255), nullable=True)
    
    # Resulting transaction (if accepted)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(hours=Config.PURCHASE_REQUEST_EXPIRY_HOURS)
        if not self.total_amount:
            self.total_amount = self.unit_price * self.quantity
        if not self.reference_number:
            self.reference_number = self._generate_reference()
    
    def _generate_reference(self):
        """Generate unique reference number"""
        import uuid
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique = uuid.uuid4().hex[:6].upper()
        return f"PR-{timestamp}-{unique}"
    
    @property
    def is_expired(self) -> bool:
        """Check if request has expired"""
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_pending(self) -> bool:
        """Check if request is still pending"""
        return self.status == "pending" and not self.is_expired
    
    def accept(self):
        """Mark request as accepted"""
        self.status = "accepted"
        self.accepted_at = datetime.utcnow()
    
    def reject(self, reason: str = None):
        """Mark request as rejected"""
        self.status = "rejected"
        self.rejected_at = datetime.utcnow()
        self.rejection_reason = reason
    
    def mark_expired(self):
        """Mark request as expired"""
        self.status = "expired"
    
    def to_dict(self, include_merchant=False, include_customer=False):
        """Convert to dictionary"""
        result = {
            "id": self.id,
            "request_id": self.id,  # Alias for frontend compatibility
            "reference_number": self.reference_number,
            "merchant_id": self.merchant_id,
            "customer_id": self.customer_id,
            "branch_id": self.branch_id,
            "product_name": self.product_name,
            "product_description": self.product_description,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "price": self.unit_price,  # Alias for frontend compatibility
            "total_amount": self.total_amount,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "is_expired": self.is_expired
        }
        
        if include_merchant and self.merchant:
            result["merchant"] = {
                "id": self.merchant.id,
                "shop_name": self.merchant.shop_name,
                "shop_name_ar": self.merchant.shop_name_ar
            }
        
        if include_customer and self.customer:
            result["customer"] = {
                "id": self.customer.id,
                "customer_code": self.customer.customer_code,
                "credit_limit": self.customer.credit_limit,
                "available_balance": self.customer.available_balance
            }
        
        return result
    
    def __repr__(self):
        return f"<PurchaseRequest {self.reference_number} - {self.status}>"
