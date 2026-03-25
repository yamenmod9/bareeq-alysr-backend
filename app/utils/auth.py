"""
JWT Authentication Utilities
Handles token creation and verification for Flask API runtime
"""
from datetime import datetime, timedelta
from typing import Optional, Callable
from functools import wraps
from inspect import iscoroutinefunction

import jwt

from app.config import Config


class AuthError(Exception):
    """Framework-agnostic auth exception."""

    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def create_access_token(
    user_id: int,
    email: Optional[str] = None,
    role: Optional[str] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token
    
    Args:
        user_id: User's database ID
        email: User's email (optional)
        role: User's role (customer/merchant/admin, optional)
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
        "iat": now,
        "exp": expire,
        "type": "access"
    }

    if email is not None:
        payload["email"] = email
    if role is not None:
        payload["role"] = role
    
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
        AuthError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            Config.JWT_SECRET_KEY,
            algorithms=[Config.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired", status_code=401)
    except jwt.InvalidTokenError as e:
        raise AuthError(f"Invalid token: {str(e)}", status_code=401)


def get_current_user(token: str) -> dict:
    """
    Resolve current user payload from a bearer token string.
    
    Args:
        token: Encoded JWT token
    
    Returns:
        User data from token payload
    """
    payload = verify_token(token)
    
    return {
        "user_id": int(payload["sub"]),
        "email": payload.get("email"),
        "role": payload.get("role")
    }


def require_role(*allowed_roles: str) -> Callable:
    """
    Decorator factory for role-based access control.
    
    Args:
        *allowed_roles: Roles allowed to access the endpoint
    
    The decorated callable must receive `token_payload` in kwargs.
    """
    def decorator(func):
        if iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                payload = kwargs.get("token_payload")
                if not payload:
                    raise AuthError("Authentication required", status_code=401)
                role = payload.get("role")
                if role not in allowed_roles:
                    raise AuthError(
                        f"Access denied. Required role: {', '.join(allowed_roles)}",
                        status_code=403,
                    )
                return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            payload = kwargs.get("token_payload")
            if not payload:
                raise AuthError("Authentication required", status_code=401)
            role = payload.get("role")
            if role not in allowed_roles:
                raise AuthError(
                    f"Access denied. Required role: {', '.join(allowed_roles)}",
                    status_code=403,
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


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
        if iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # TODO: Implement audit logging
                # Log: timestamp, user_id, action, details
                return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            # TODO: Implement audit logging
            # Log: timestamp, user_id, action, details
            return func(*args, **kwargs)

        return wrapper

    return decorator
