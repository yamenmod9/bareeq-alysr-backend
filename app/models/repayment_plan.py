"""
Repayment Plan Model - Customer payment schedules
Plans: 1, 3, 6, 12, 18, 24 months
"""
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from app.database import db
from app.config import Config


class RepaymentPlan(db.Model):
    """
    Repayment plan selected by customer
    Options: 1, 3, 6, 12, 18, 24 months
    """
    __tablename__ = "repayment_plans"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    
    # Plan Details
    plan_type = db.Column(db.Integer, nullable=False)  # 1, 3, 6, 12, 18, 24 (months)
    total_amount = db.Column(db.Float, nullable=False)
    installment_amount = db.Column(db.Float, nullable=False)  # Amount per installment
    number_of_installments = db.Column(db.Integer, nullable=False)
    
    # Status: active, completed, defaulted
    status = db.Column(db.String(20), default="active", index=True)
    
    # Progress
    paid_installments = db.Column(db.Integer, default=0)
    paid_amount = db.Column(db.Float, default=0.0)
    remaining_amount = db.Column(db.Float, nullable=False)
    
    # Reference
    plan_reference = db.Column(db.String(50), unique=True, nullable=False)
    
    # Next Payment Info
    next_payment_date = db.Column(db.DateTime, nullable=True)
    next_payment_amount = db.Column(db.Float, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    schedules = db.relationship("RepaymentSchedule", backref="plan", lazy="dynamic",
                               cascade="all, delete-orphan")
    transaction_ref = db.relationship("Transaction", foreign_keys=[transaction_id],
                                      backref=db.backref("repayment_plan_ref", uselist=False))
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.remaining_amount:
            self.remaining_amount = self.total_amount
        if not self.plan_reference:
            self.plan_reference = self._generate_reference()
    
    def _generate_reference(self):
        """Generate unique plan reference"""
        import uuid
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique = uuid.uuid4().hex[:6].upper()
        return f"PLAN-{timestamp}-{unique}"
    
    @staticmethod
    def calculate_installment(total_amount: float, plan_type: int) -> float:
        """Calculate installment amount"""
        return round(total_amount / plan_type, 2)
    
    @staticmethod
    def validate_plan_type(plan_type: int) -> bool:
        """Validate plan type"""
        return plan_type in Config.REPAYMENT_PLANS
    
    def generate_schedule(self):
        """Generate payment schedule based on plan type"""
        schedules = []
        installment = self.calculate_installment(self.total_amount, self.plan_type)
        remaining = self.total_amount
        
        for i in range(self.plan_type):
            # Calculate due date (monthly intervals)
            due_date = datetime.utcnow() + relativedelta(months=i+1)
            
            # Last installment gets remainder to handle rounding
            if i == self.plan_type - 1:
                amount = remaining
            else:
                amount = installment
                remaining -= installment
            
            schedule = RepaymentSchedule(
                plan_id=self.id,
                installment_number=i + 1,
                amount=round(amount, 2),
                due_date=due_date,
                status="pending"
            )
            schedules.append(schedule)
        
        # Set next payment info
        if schedules:
            self.next_payment_date = schedules[0].due_date
            self.next_payment_amount = schedules[0].amount
        
        return schedules
    
    def record_installment_payment(self, amount: float):
        """Record an installment payment"""
        self.paid_installments += 1
        self.paid_amount += amount
        self.remaining_amount -= amount
        
        if self.remaining_amount <= 0:
            self.remaining_amount = 0
            self.status = "completed"
            self.completed_at = datetime.utcnow()
            self.next_payment_date = None
            self.next_payment_amount = None
        else:
            # Update next payment from remaining schedules
            next_schedule = RepaymentSchedule.query.filter_by(
                plan_id=self.id,
                status="pending"
            ).order_by(RepaymentSchedule.installment_number).first()
            
            if next_schedule:
                self.next_payment_date = next_schedule.due_date
                self.next_payment_amount = next_schedule.amount
    
    def to_dict(self, include_schedule=False):
        """Convert to dictionary"""
        data = {
            "id": self.id,
            "plan_reference": self.plan_reference,
            "transaction_id": self.transaction_id,
            "customer_id": self.customer_id,
            "plan_type": self.plan_type,
            "plan_name": f"{self.plan_type} month{'s' if self.plan_type > 1 else ''}",
            "total_amount": self.total_amount,
            "installment_amount": self.installment_amount,
            "number_of_installments": self.number_of_installments,
            "status": self.status,
            "paid_installments": self.paid_installments,
            "paid_amount": self.paid_amount,
            "remaining_amount": self.remaining_amount,
            "next_payment_date": self.next_payment_date.isoformat() if self.next_payment_date else None,
            "next_payment_amount": self.next_payment_amount,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
        if include_schedule:
            data["payment_schedule"] = [s.to_dict() for s in self.schedules.order_by(
                RepaymentSchedule.installment_number)]
        return data
    
    def __repr__(self):
        return f"<RepaymentPlan {self.plan_reference} - {self.plan_type} months>"


class RepaymentSchedule(db.Model):
    """
    Individual installment schedule entries
    """
    __tablename__ = "repayment_schedules"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys
    plan_id = db.Column(db.Integer, db.ForeignKey("repayment_plans.id"), nullable=False)
    
    # Installment Details
    installment_number = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    
    # Status: pending, paid, overdue, partial
    status = db.Column(db.String(20), default="pending", index=True)
    
    # Payment Info
    paid_amount = db.Column(db.Float, default=0.0)
    paid_date = db.Column(db.DateTime, nullable=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def is_overdue(self) -> bool:
        """Check if installment is overdue"""
        return datetime.utcnow() > self.due_date and self.status == "pending"
    
    def mark_paid(self, payment_id: int):
        """Mark installment as paid"""
        self.status = "paid"
        self.paid_amount = self.amount
        self.paid_date = datetime.utcnow()
        self.payment_id = payment_id
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "installment_number": self.installment_number,
            "amount": self.amount,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "paid_amount": self.paid_amount,
            "paid_date": self.paid_date.isoformat() if self.paid_date else None,
            "is_overdue": self.is_overdue
        }
    
    def __repr__(self):
        return f"<RepaymentSchedule #{self.installment_number} - {self.amount} SAR>"
