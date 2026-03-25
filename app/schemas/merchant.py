"""
Merchant Schemas - Merchant-related request/response models
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


class BranchResponse(BaseModel):
    """Branch information"""
    id: int
    name: str
    address: Optional[str]
    city: Optional[str]
    phone: Optional[str]
    is_active: bool
    
    class Config:
        from_attributes = True


class MerchantResponse(BaseModel):
    """Merchant information response"""
    id: int
    user_id: int
    shop_name: str
    shop_name_ar: Optional[str]
    commercial_registration: Optional[str]
    status: str
    is_verified: bool
    total_transactions: int
    total_volume: float
    city: Optional[str]
    created_at: datetime
    branches: Optional[List[BranchResponse]] = None
    
    class Config:
        from_attributes = True


# === Send Purchase Request ===

class SendPurchaseRequest(BaseModel):
    """Request to send a purchase request to customer"""
    customer_id: int = Field(..., description="Customer ID")
    product_name: str = Field(..., min_length=1, max_length=255, description="Product name")
    product_description: Optional[str] = Field(
        default=None, 
        max_length=1000,
        description="Product description"
    )
    price: float = Field(..., gt=0, description="Unit price in SAR")
    quantity: int = Field(default=1, ge=1, description="Quantity")
    branch_id: Optional[int] = Field(default=None, description="Branch ID (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": 1,
                "product_name": "Samsung Galaxy S24",
                "product_description": "Smartphone - 256GB - Black",
                "price": 3999.0,
                "quantity": 1,
                "branch_id": 1
            }
        }


class SendPurchaseResponse(BaseModel):
    """Response after sending purchase request"""
    request_id: int = Field(..., description="Purchase request ID")
    reference_number: str = Field(..., description="Reference number")
    status: str = Field(default="pending", description="Request status")
    total_amount: float = Field(..., description="Total amount")
    expires_at: datetime = Field(..., description="Request expiry time")
    customer_available_balance: float = Field(..., description="Customer's available balance")
    message: str = Field(default="Purchase request sent successfully")
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": 1,
                "reference_number": "PR-20260112-ABC123",
                "status": "pending",
                "total_amount": 3999.0,
                "expires_at": "2026-01-13T12:00:00",
                "customer_available_balance": 5000.0,
                "message": "Purchase request sent successfully"
            }
        }


# === Receive Settlement ===

class ReceiveSettlementRequest(BaseModel):
    """Request to receive settlement (usually triggered by payment)"""
    transaction_id: int = Field(..., description="Transaction ID to settle")
    
    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": 1
            }
        }


class ReceiveSettlementResponse(BaseModel):
    """Response with settlement details"""
    settlement_id: int = Field(..., description="Settlement ID")
    settlement_reference: str = Field(..., description="Settlement reference number")
    gross_amount: float = Field(..., description="Gross transaction amount")
    commission_rate: float = Field(..., description="Platform commission rate")
    commission_amount: float = Field(..., description="Commission deducted")
    net_amount: float = Field(..., description="Net amount to receive")
    status: str = Field(..., description="Settlement status")
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "settlement_id": 1,
                "settlement_reference": "STL-20260112-ABC123",
                "gross_amount": 1000.0,
                "commission_rate": 0.005,
                "commission_amount": 5.0,
                "net_amount": 995.0,
                "status": "pending",
                "message": "Settlement created successfully"
            }
        }


# === Merchant Dashboard ===

class MerchantDashboardResponse(BaseModel):
    """Merchant dashboard overview"""
    merchant: MerchantResponse
    pending_requests: int
    active_transactions: int
    pending_settlements: float
    total_settled: float
    today_volume: float


# === Merchant Registration ===

class MerchantRegistrationRequest(BaseModel):
    """Merchant registration request"""
    email: EmailStr = Field(..., description="Business email")
    password: str = Field(..., min_length=6, description="Password")
    full_name: str = Field(..., min_length=2, description="Owner full name")
    phone: Optional[str] = Field(default=None, description="Phone number")
    national_id: Optional[str] = Field(default=None, description="National ID")
    
    # Business Info
    shop_name: str = Field(..., min_length=2, max_length=255, description="Shop name")
    shop_name_ar: Optional[str] = Field(default=None, description="Shop name in Arabic")
    commercial_registration: Optional[str] = Field(default=None, description="CR Number")
    vat_number: Optional[str] = Field(default=None, description="VAT Number")
    
    # Bank Details
    bank_name: Optional[str] = Field(default=None, description="Bank name")
    bank_account: Optional[str] = Field(default=None, description="Bank account number")
    iban: Optional[str] = Field(default=None, description="IBAN")
    
    # Location
    city: Optional[str] = Field(default=None, description="City")
    address: Optional[str] = Field(default=None, description="Business address")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "merchant@shop.com",
                "password": "securepass123",
                "full_name": "Mohammed Ali",
                "phone": "+966501234567",
                "shop_name": "Al-Yusr Electronics",
                "shop_name_ar": "الكترونيات اليسر",
                "commercial_registration": "1234567890",
                "city": "Riyadh"
            }
        }


# === Create Branch ===

class CreateBranchRequest(BaseModel):
    """Request to create a new branch"""
    name: str = Field(..., min_length=1, max_length=255, description="Branch name")
    address: Optional[str] = Field(default=None, description="Branch address")
    city: Optional[str] = Field(default=None, description="City")
    phone: Optional[str] = Field(default=None, description="Branch phone")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Main Branch - Olaya",
                "address": "Olaya Street, Building 123",
                "city": "Riyadh",
                "phone": "+966112345678"
            }
        }
