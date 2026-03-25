"""
Settlement Model - Merchant settlements (payments to merchants)
"""
from datetime import datetime
from app.database import db
from app.config import Config


class Settlement(db.Model):
    """
    Settlement records for merchant payouts
    Platform deducts 0.5% commission before settling
    """
    __tablename__ = "settlements"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchants.id"), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    
    # Settlement Type: 'income' (from customer purchase), 'withdrawal' (merchant withdrawal)
    settlement_type = db.Column(db.String(20), default="income", index=True)
    
    # Financial Details
    gross_amount = db.Column(db.Float, nullable=False)  # Original transaction amount
    commission_rate = db.Column(db.Float, default=Config.PLATFORM_COMMISSION_RATE)
    commission_amount = db.Column(db.Float, nullable=False)  # Platform commission
    net_amount = db.Column(db.Float, nullable=False)  # Amount merchant receives
    
    # Status: pending, processing, completed, failed
    status = db.Column(db.String(20), default="pending", index=True)
    
    # Reference
    settlement_reference = db.Column(db.String(50), unique=True, nullable=False)
    bank_reference = db.Column(db.String(100), nullable=True)  # Bank transfer reference
    
    # Bank Details (snapshot at time of settlement)
    bank_name = db.Column(db.String(100), nullable=True)
    bank_account = db.Column(db.String(50), nullable=True)
    iban = db.Column(db.String(34), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Notes
    notes = db.Column(db.Text, nullable=True)
    failure_reason = db.Column(db.String(255), nullable=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.commission_amount and self.gross_amount:
            self.commission_amount = self.gross_amount * self.commission_rate
        if not self.net_amount and self.gross_amount:
            self.net_amount = self.gross_amount - self.commission_amount
        if not self.settlement_reference:
            self.settlement_reference = self._generate_reference()
    
    def _generate_reference(self):
        """Generate unique settlement reference"""
        import uuid
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique = uuid.uuid4().hex[:6].upper()
        return f"STL-{timestamp}-{unique}"
    
    def mark_processing(self):
        """Mark settlement as processing"""
        self.status = "processing"
        self.processed_at = datetime.utcnow()
    
    def mark_completed(self, bank_reference: str = None):
        """Mark settlement as completed"""
        self.status = "completed"
        self.completed_at = datetime.utcnow()
        if bank_reference:
            self.bank_reference = bank_reference
    
    def mark_failed(self, reason: str):
        """Mark settlement as failed"""
        self.status = "failed"
        self.failure_reason = reason
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "settlement_reference": self.settlement_reference,
            "settlement_type": self.settlement_type,
            "merchant_id": self.merchant_id,
            "transaction_id": self.transaction_id,
            "gross_amount": self.gross_amount,
            "commission_rate": self.commission_rate,
            "commission_amount": self.commission_amount,
            "net_amount": self.net_amount,
            "status": self.status,
            "bank_name": self.bank_name,
            "bank_account": self.bank_account,
            "iban": self.iban,
            "bank_reference": self.bank_reference,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    def __repr__(self):
        return f"<Settlement {self.settlement_reference} - {self.net_amount} SAR>"
