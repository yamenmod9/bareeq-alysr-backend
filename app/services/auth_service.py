"""
Authentication Service
Handles user authentication, registration, and Nafath simulation
"""
from datetime import datetime
from typing import Optional, Tuple

from app.database import db
from app.models import User, Customer, Merchant
from app.utils.auth import create_access_token, TokenInfo
from app.utils.response import NotFoundError, UnauthorizedError, ConflictError, BusinessError
from app.config import Config


class AuthService:
    """Authentication and user management service"""
    
    @staticmethod
    def authenticate(email: str, password: str, national_id: str = None) -> Tuple[User, str]:
        """
        Authenticate user with email/password
        Simulates Nafath verification
        
        Args:
            email: User email
            password: User password
            national_id: Optional national ID for Nafath simulation
        
        Returns:
            Tuple of (User, access_token)
        
        Raises:
            UnauthorizedError: If credentials are invalid
        """
        # Find user by email
        user = User.query.filter_by(email=email.lower()).first()
        
        if not user:
            raise UnauthorizedError("Invalid email or password")
        
        # Verify password
        if not user.verify_password(password):
            raise UnauthorizedError("Invalid email or password")
        
        # Check if user is active
        if not user.is_active:
            raise UnauthorizedError("Account is deactivated")
        
        # Simulate Nafath verification if national_id provided
        if national_id:
            if user.national_id and user.national_id != national_id:
                raise UnauthorizedError("National ID does not match")
            # In production, this would call Nafath API
            user.nafath_verified = True
        
        # Update last login
        user.update_last_login()
        
        # Create access token
        token = create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role
        )
        
        return user, token
    
    @staticmethod
    def register_customer(
        email: str,
        password: str,
        full_name: str,
        phone: str = None,
        national_id: str = None
    ) -> Tuple[User, Customer]:
        """
        Register a new customer
        
        Args:
            email: User email
            password: User password
            full_name: Customer full name
            phone: Phone number
            national_id: Saudi National ID
        
        Returns:
            Tuple of (User, Customer)
        
        Raises:
            ConflictError: If email already exists
        """
        # Check if email exists
        if User.query.filter_by(email=email.lower()).first():
            raise ConflictError("Email already registered")
        
        # Check if national_id exists
        if national_id and User.query.filter_by(national_id=national_id).first():
            raise ConflictError("National ID already registered")
        
        # Create user
        user = User(
            email=email.lower(),
            full_name=full_name,
            phone=phone,
            national_id=national_id,
            role="customer",
            is_active=True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.flush()  # Get user.id
        
        # Create customer profile
        customer = Customer(
            user_id=user.id,
            credit_limit=Config.DEFAULT_CREDIT_LIMIT,
            available_balance=Config.DEFAULT_CREDIT_LIMIT,
            status="active"
        )
        
        db.session.add(customer)
        db.session.commit()
        
        return user, customer
    
    @staticmethod
    def register_merchant(
        email: str,
        password: str,
        full_name: str,
        shop_name: str,
        phone: str = None,
        national_id: str = None,
        **merchant_data
    ) -> Tuple[User, Merchant]:
        """
        Register a new merchant
        
        Args:
            email: User email
            password: User password
            full_name: Owner full name
            shop_name: Shop/business name
            phone: Phone number
            national_id: Saudi National ID
            **merchant_data: Additional merchant fields
        
        Returns:
            Tuple of (User, Merchant)
        
        Raises:
            ConflictError: If email already exists
        """
        # Check if email exists
        if User.query.filter_by(email=email.lower()).first():
            raise ConflictError("Email already registered")
        
        # Check if national_id exists
        if national_id and User.query.filter_by(national_id=national_id).first():
            raise ConflictError("National ID already registered")
        
        # Create user
        user = User(
            email=email.lower(),
            full_name=full_name,
            phone=phone,
            national_id=national_id,
            role="merchant",
            is_active=True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.flush()
        
        # Create merchant profile
        merchant = Merchant(
            user_id=user.id,
            shop_name=shop_name,
            shop_name_ar=merchant_data.get("shop_name_ar"),
            commercial_registration=merchant_data.get("commercial_registration"),
            vat_number=merchant_data.get("vat_number"),
            bank_name=merchant_data.get("bank_name"),
            bank_account=merchant_data.get("bank_account"),
            iban=merchant_data.get("iban"),
            city=merchant_data.get("city"),
            address=merchant_data.get("address"),
            business_phone=merchant_data.get("business_phone"),
            business_email=merchant_data.get("business_email"),
            status="active"
        )
        
        db.session.add(merchant)
        db.session.commit()
        
        return user, merchant
    
    @staticmethod
    def get_user_by_id(user_id: int) -> User:
        """Get user by ID"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user
    
    @staticmethod
    def get_user_by_email(email: str) -> Optional[User]:
        """Get user by email"""
        return User.query.filter_by(email=email.lower()).first()
    
    @staticmethod
    def get_customer_by_user_id(user_id: int) -> Customer:
        """Get customer profile by user ID"""
        customer = Customer.query.filter_by(user_id=user_id).first()
        if not customer:
            raise NotFoundError("Customer profile")
        return customer
    
    @staticmethod
    def get_merchant_by_user_id(user_id: int) -> Merchant:
        """Get merchant profile by user ID"""
        merchant = Merchant.query.filter_by(user_id=user_id).first()
        if not merchant:
            raise NotFoundError("Merchant profile")
        return merchant
    
    @staticmethod
    def simulate_nafath_verification(user_id: int, national_id: str) -> bool:
        """
        Simulate Nafath (Saudi government) verification
        In production, this would integrate with actual Nafath API
        
        Args:
            user_id: User ID
            national_id: Saudi National ID (10 digits)
        
        Returns:
            True if verification successful
        """
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        
        # Simulate verification (always successful in MVP)
        user.national_id = national_id
        user.nafath_id = f"NAFATH-{national_id}"
        user.nafath_verified = True
        user.is_verified = True
        
        db.session.commit()
        
        return True
    
    @staticmethod
    def change_password(user_id: int, old_password: str, new_password: str) -> bool:
        """
        Change user password
        
        Args:
            user_id: User ID
            old_password: Current password
            new_password: New password
        
        Returns:
            True if successful
        
        Raises:
            UnauthorizedError: If old password is incorrect
        """
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        
        if not user.verify_password(old_password):
            raise UnauthorizedError("Current password is incorrect")
        
        user.set_password(new_password)
        db.session.commit()
        
        return True
    
    @staticmethod
    def deactivate_user(user_id: int) -> bool:
        """Deactivate a user account"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        
        user.is_active = False
        db.session.commit()
        
        return True
    
    @staticmethod
    def update_profile(user_id: int, full_name: str = None, phone: str = None, email: str = None) -> User:
        """
        Update user profile
        
        Args:
            user_id: User ID
            full_name: New full name
            phone: New phone number
            email: New email (requires verification)
        
        Returns:
            Updated User
        """
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        
        if full_name is not None:
            user.full_name = full_name
        
        if phone is not None:
            user.phone = phone
        
        if email is not None and email.lower() != user.email:
            # Check if email already exists
            existing = User.query.filter_by(email=email.lower()).first()
            if existing:
                raise ConflictError("Email already in use")
            user.email = email.lower()
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return user
    
    @staticmethod
    def enable_2fa(user_id: int) -> dict:
        """
        Enable 2FA for user
        
        Args:
            user_id: User ID
        
        Returns:
            Dict with secret, qr_code, and backup_codes
        """
        import secrets
        import base64
        
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        
        # Generate a secret key (16 bytes = 32 hex chars)
        secret = secrets.token_hex(16)
        
        # Generate backup codes
        backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
        
        # Store the secret
        user.two_factor_secret = secret
        user.two_factor_enabled = True
        db.session.commit()
        
        # Generate QR code URL (otpauth format)
        # In production, you'd use pyotp and qrcode libraries
        issuer = "Bareeq Al-Yusr"
        otp_url = f"otpauth://totp/{issuer}:{user.email}?secret={secret}&issuer={issuer}"
        
        return {
            "enabled": True,
            "secret": secret,
            "qr_code": otp_url,  # Frontend can generate QR from this
            "backup_codes": backup_codes
        }
    
    @staticmethod
    def disable_2fa(user_id: int) -> dict:
        """
        Disable 2FA for user
        
        Args:
            user_id: User ID
        
        Returns:
            Dict with enabled status
        """
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        
        user.two_factor_secret = None
        user.two_factor_enabled = False
        db.session.commit()
        
        return {"enabled": False}
