"""
Authentication Schemas
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr


class LoginRequest(BaseModel):
    """
    Login request schema
    Simulates Nafath authentication with email/national_id
    """
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")
    national_id: Optional[str] = Field(
        default=None,
        pattern=r"^\d{10}$",
        description="Saudi National ID (10 digits) - optional for Nafath simulation"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "customer@example.com",
                "password": "password123",
                "national_id": "1234567890"
            }
        }


class TokenData(BaseModel):
    """JWT Token payload data"""
    user_id: int
    email: str
    role: Literal["customer", "merchant", "admin"]
    exp: datetime
    iat: datetime


class UserResponse(BaseModel):
    """User information response"""
    id: int
    email: str
    role: str
    full_name: Optional[str]
    phone: Optional[str]
    is_active: bool
    is_verified: bool
    nafath_verified: bool
    created_at: datetime
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Login response with JWT token"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiry in seconds")
    user: UserResponse = Field(..., description="User information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400,
                "user": {
                    "id": 1,
                    "email": "customer@example.com",
                    "role": "customer",
                    "full_name": "Ahmed Mohammed",
                    "is_active": True
                }
            }
        }


class RegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=6, description="Password (min 6 chars)")
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name")
    phone_number: Optional[str] = Field(
        default=None,
        pattern=r"^\+?[0-9]{10,15}$",
        description="Phone number"
    )
    role: Literal["customer", "merchant"] = Field(default="customer", description="User role")
    national_id: Optional[str] = Field(
        default=None,
        pattern=r"^\d{10}$",
        description="Saudi National ID (10 digits)"
    )
    
    # Merchant-specific fields
    shop_name: Optional[str] = Field(default=None, description="Shop name (for merchants)")
    shop_name_ar: Optional[str] = Field(default=None, description="Shop name in Arabic")
    commercial_registration: Optional[str] = Field(default=None, description="Commercial registration number")
    vat_number: Optional[str] = Field(default=None, description="VAT number")
    business_phone: Optional[str] = Field(default=None, description="Business phone number")
    business_email: Optional[EmailStr] = Field(default=None, description="Business email")
    address: Optional[str] = Field(default=None, description="Business address")
    city: Optional[str] = Field(default=None, description="City")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "newuser@example.com",
                "password": "securepass123",
                "full_name": "Ahmed Mohammed",
                "phone_number": "+966501234567",
                "role": "customer",
                "national_id": "1234567890"
            }
        }


class RegisterResponse(BaseModel):
    """Registration response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiry in seconds")
    user: UserResponse = Field(..., description="User information")
    message: str = Field(default="Registration successful", description="Success message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400,
                "user": {
                    "id": 1,
                    "email": "newuser@example.com",
                    "role": "customer",
                    "full_name": "Ahmed Mohammed",
                    "is_active": True
                },
                "message": "Registration successful"
            }
        }


class UpdateProfileRequest(BaseModel):
    """Update user profile request"""
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255, description="Full name")
    phone: Optional[str] = Field(
        default=None,
        pattern=r"^\+?[0-9]{10,15}$",
        description="Phone number"
    )
    email: Optional[EmailStr] = Field(default=None, description="Email address")


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=6, description="New password (min 6 chars)")
    confirm_password: str = Field(..., min_length=6, description="Confirm new password")


class Enable2FARequest(BaseModel):
    """Enable 2FA request"""
    enabled: bool = Field(..., description="Enable or disable 2FA")


class TwoFactorResponse(BaseModel):
    """2FA setup response"""
    enabled: bool = Field(..., description="Whether 2FA is enabled")
    secret: Optional[str] = Field(default=None, description="TOTP secret (only on enable)")
    qr_code: Optional[str] = Field(default=None, description="QR code data URL (only on enable)")
    backup_codes: Optional[list[str]] = Field(default=None, description="Backup codes (only on enable)")
