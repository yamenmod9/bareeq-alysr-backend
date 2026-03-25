"""
JWT Authentication Utilities
Handles token creation, verification, and FastAPI dependencies
"""
from datetime import datetime, timedelta
from typing import Optional, Callable
from functools import wraps

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import Config

# Security scheme for FastAPI
security = HTTPBearer()


def create_access_token(
    user_id: int,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token
    
    Args:
        user_id: User's database ID
        email: User's email
        role: User's role (customer/merchant/admin)
        expires_delta: Custom expiration time (optional)
    
    Returns:
        Encoded JWT token string
    """
    if expires_delta is None:
        expires_delta = Config.JWT_ACCESS_TOKEN_EXPIRE
    
    now = datetime.utcnow()
    expire = now + expires_delta
    
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": expire,
        "type": "access"
    }
    
    token = jwt.encode(
        payload,
        Config.JWT_SECRET_KEY,
        algorithm=Config.JWT_ALGORITHM
    )
    
    return token


def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT token
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload
    
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            Config.JWT_SECRET_KEY,
            algorithms=[Config.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    FastAPI dependency to get current authenticated user
    
    Args:
        credentials: Bearer token from request header
    
    Returns:
        User data from token payload
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    return {
        "user_id": int(payload["sub"]),
        "email": payload["email"],
        "role": payload["role"]
    }


def require_role(*allowed_roles: str) -> Callable:
    """
    Decorator/dependency factory for role-based access control
    
    Args:
        *allowed_roles: Roles allowed to access the endpoint
    
    Returns:
        FastAPI dependency function
    
    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user = Depends(require_role("admin"))):
            pass
    """
    async def role_checker(
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> dict:
        token = credentials.credentials
        payload = verify_token(token)
        user_role = payload.get("role")
        
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}"
            )
        
        return {
            "user_id": int(payload["sub"]),
            "email": payload["email"],
            "role": user_role
        }
    
    return role_checker


# Convenience dependencies for common role checks
get_customer = require_role("customer")
get_merchant = require_role("merchant")
get_admin = require_role("admin")
get_customer_or_merchant = require_role("customer", "merchant")


class TokenInfo:
    """Token information helper class"""
    
    @staticmethod
    def get_expiry_seconds() -> int:
        """Get token expiry in seconds"""
        return int(Config.JWT_ACCESS_TOKEN_EXPIRE.total_seconds())
    
    @staticmethod
    def decode_without_verification(token: str) -> dict:
        """
        Decode token without verification (for debugging)
        WARNING: Do not use for authentication!
        """
        return jwt.decode(
            token,
            options={"verify_signature": False}
        )


def audit_log(action: str):
    """
    Decorator for audit logging (for future expansion)
    
    Args:
        action: Action being performed
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # TODO: Implement audit logging
            # Log: timestamp, user_id, action, details
            result = await func(*args, **kwargs)
            return result
        return wrapper
    return decorator
