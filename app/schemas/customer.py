"""
Customer Schemas - Customer-related request/response models
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class CustomerResponse(BaseModel):
    """Customer information response"""
    id: int
    user_id: int
    customer_code: str
    credit_limit: float
    available_balance: float
    outstanding_balance: float
    status: str
    risk_score: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# === Accept Purchase Request ===

class AcceptPurchaseRequest(BaseModel):
    """Request to accept a purchase request"""
    request_id: int = Field(..., description="Purchase request ID to accept")
    installment_months: int = Field(default=1, description="Number of months for installment (1, 3, 6, 12)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": 1,
                "installment_months": 3
            }
        }


# === Reject Purchase Request ===

class RejectPurchaseRequest(BaseModel):
    """Request to reject a purchase request"""
    request_id: int = Field(..., description="Purchase request ID to reject")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection")
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": 1,
                "rejection_reason": "Cannot afford at this time"
            }
        }


class AcceptPurchaseResponse(BaseModel):
    """Response after accepting purchase"""
    transaction_id: int = Field(..., description="Created transaction ID")
    transaction_number: str = Field(..., description="Transaction reference number")
    remaining_balance: float = Field(..., description="Customer's remaining available balance")
    due_date: datetime = Field(..., description="Payment due date")
    total_amount: float = Field(..., description="Total amount to repay")
    installment_months: int = Field(..., description="Number of installment months")
    installment_amount: float = Field(..., description="Amount per installment")
    message: str = Field(default="Purchase accepted successfully")
    
    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": 1,
                "transaction_number": "TXN-20260112-ABC123",
                "remaining_balance": 1500.0,
                "due_date": "2026-01-22T12:00:00",
                "total_amount": 500.0,
                "installment_months": 3,
                "installment_amount": 166.67,
                "message": "Purchase accepted successfully"
            }
        }


# === Update Credit Limit ===

class UpdateLimitRequest(BaseModel):
    """Request to update credit limit"""
    new_limit: float = Field(
        ..., 
        gt=0, 
        description="Requested new credit limit in SAR"
    )
    reason: Optional[str] = Field(
        default=None, 
        max_length=255,
        description="Reason for limit increase request"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "new_limit": 5000.0,
                "reason": "Need higher limit for home appliances"
            }
        }


class UpdateLimitResponse(BaseModel):
    """Response after limit update request"""
    previous_limit: float = Field(..., description="Previous credit limit")
    new_limit: float = Field(..., description="New credit limit")
    available_balance: float = Field(..., description="Updated available balance")
    status: str = Field(..., description="Request status (approved/pending)")
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "previous_limit": 2000.0,
                "new_limit": 5000.0,
                "available_balance": 5000.0,
                "status": "approved",
                "message": "Credit limit updated successfully"
            }
        }


# === Select Repayment Plan ===

class SelectRepaymentPlanRequest(BaseModel):
    """Request to select a repayment plan"""
    transaction_id: int = Field(..., description="Transaction ID")
    plan_type: Literal[1, 3, 6, 12, 18, 24] = Field(
        ..., 
        description="Repayment plan in months (1, 3, 6, 12, 18, or 24)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": 1,
                "plan_type": 3
            }
        }


class PaymentScheduleItem(BaseModel):
    """Single payment schedule entry"""
    installment_number: int
    amount: float
    due_date: datetime
    status: str = "pending"


class SelectRepaymentPlanResponse(BaseModel):
    """Response after selecting repayment plan"""
    plan_id: int = Field(..., description="Repayment plan ID")
    plan_reference: str = Field(..., description="Plan reference number")
    plan_type: int = Field(..., description="Plan type in months")
    total_amount: float = Field(..., description="Total amount to pay")
    installment_amount: float = Field(..., description="Amount per installment")
    number_of_installments: int = Field(..., description="Number of installments")
    payment_schedule: List[PaymentScheduleItem] = Field(..., description="Payment schedule")
    next_payment_date: datetime = Field(..., description="Next payment due date")
    next_payment_amount: float = Field(..., description="Next payment amount")
    message: str = Field(default="Repayment plan created successfully")
    
    class Config:
        json_schema_extra = {
            "example": {
                "plan_id": 1,
                "plan_reference": "PLAN-20260112-ABC123",
                "plan_type": 3,
                "total_amount": 3000.0,
                "installment_amount": 1000.0,
                "number_of_installments": 3,
                "payment_schedule": [
                    {"installment_number": 1, "amount": 1000.0, "due_date": "2026-02-12T12:00:00", "status": "pending"},
                    {"installment_number": 2, "amount": 1000.0, "due_date": "2026-03-12T12:00:00", "status": "pending"},
                    {"installment_number": 3, "amount": 1000.0, "due_date": "2026-04-12T12:00:00", "status": "pending"}
                ],
                "next_payment_date": "2026-02-12T12:00:00",
                "next_payment_amount": 1000.0,
                "message": "Repayment plan created successfully"
            }
        }


# === Make Payment ===

class MakePaymentRequest(BaseModel):
    """Request to make a payment"""
    transaction_id: Optional[int] = Field(
        default=None, 
        description="Transaction ID (use this OR plan_id)"
    )
    plan_id: Optional[int] = Field(
        default=None, 
        description="Repayment plan ID (use this OR transaction_id)"
    )
    amount: float = Field(..., gt=0, description="Payment amount in SAR")
    payment_method: Optional[str] = Field(
        default="wallet", 
        description="Payment method (wallet, card, bank_transfer)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": 1,
                "amount": 500.0,
                "payment_method": "wallet"
            }
        }


class MakePaymentResponse(BaseModel):
    """Response after making payment"""
    receipt_id: str = Field(..., description="Payment receipt ID")
    payment_id: int = Field(..., description="Payment record ID")
    amount_paid: float = Field(..., description="Amount paid")
    new_balance: float = Field(..., description="New remaining balance")
    transaction_status: str = Field(..., description="Transaction status")
    settlement_triggered: bool = Field(
        default=False, 
        description="Whether merchant settlement was triggered"
    )
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "receipt_id": "PAY-20260112-ABC123",
                "payment_id": 1,
                "amount_paid": 500.0,
                "new_balance": 0.0,
                "transaction_status": "completed",
                "settlement_triggered": True,
                "message": "Payment processed successfully"
            }
        }


# === Customer Dashboard ===

class CustomerDashboardResponse(BaseModel):
    """Customer dashboard overview"""
    customer: CustomerResponse
    active_transactions: int
    pending_requests: int
    total_outstanding: float
    next_payment_due: Optional[datetime]
    next_payment_amount: Optional[float]
