"""
User Model - Base user for both customers and merchants
"""
from datetime import datetime

import bcrypt as _bcrypt

from app.database import db


def _bcrypt_secret_bytes(secret: str) -> bytes:
    """Return UTF-8 bytes truncated to bcrypt's 72-byte input limit."""
    if secret is None:
        secret = ""
    return secret.encode("utf-8")[:72]


class User(db.Model):
    """
    Base User model for authentication
    Both customers and merchants are users with different roles
    """
    __tablename__ = "users"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Nafath Integration (Saudi Government Login)
    nafath_id = db.Column(db.String(20), unique=True, nullable=True, index=True)
    national_id = db.Column(db.String(10), unique=True, nullable=True)  # Saudi National ID
    nafath_verified = db.Column(db.Boolean, default=False)
    
    # Role: 'customer' or 'merchant'
    role = db.Column(db.String(20), nullable=False, default="customer")
    
    # User Status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    
    # Two-Factor Authentication
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(32), nullable=True)
    
    # Personal Info
    full_name = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    customer = db.relationship("Customer", backref="user", uselist=False, lazy=True)
    merchant = db.relationship("Merchant", backref="user", uselist=False, lazy=True)
    
    def set_password(self, password: str):
        """Hash and set the password."""
        password_bytes = _bcrypt_secret_bytes(password)
        self.password_hash = _bcrypt.hashpw(password_bytes, _bcrypt.gensalt()).decode("utf-8")
    
    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        try:
            return _bcrypt.checkpw(
                _bcrypt_secret_bytes(password),
                (self.password_hash or "").encode("utf-8"),
            )
        except ValueError:
            return False
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "full_name": self.full_name,
            "phone": self.phone,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "nafath_verified": self.nafath_verified,
            "two_factor_enabled": self.two_factor_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None
        }
    
    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
