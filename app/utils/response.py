"""
Response Utilities
Standardized API response helpers
"""
from datetime import datetime
from typing import Any, Optional, List, TypeVar, Generic
from math import ceil

from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar('T')


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200
) -> dict:
    """
    Create a standardized success response
    
    Args:
        data: Response data (any serializable type)
        message: Human-readable message
        status_code: HTTP status code
    
    Returns:
        Standardized response dictionary
    """
    return {
        "success": True,
        "data": data,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }


def error_response(
    message: str,
    error: str = "Error",
    details: Optional[dict] = None,
    status_code: int = 400
) -> JSONResponse:
    """
    Create a standardized error response
    
    Args:
        message: Error message
        error: Error type/code
        details: Additional error details
        status_code: HTTP status code
    
    Returns:
        JSONResponse with error data
    """
    content = {
        "success": False,
        "error": error,
        "message": message,
        "details": details,
        "timestamp": datetime.utcnow().isoformat()
    }
    return JSONResponse(
        status_code=status_code,
        content=content
    )


def paginate(
    items: List[Any],
    total: int,
    page: int = 1,
    per_page: int = 20
) -> dict:
    """
    Create paginated response data
    
    Args:
        items: List of items for current page
        total: Total number of items
        page: Current page number
        per_page: Items per page
    
    Returns:
        Pagination metadata with items
    """
    pages = ceil(total / per_page) if per_page > 0 else 0
    
    return {
        "items": items,
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1
        }
    }


class APIException(Exception):
    """Custom API exception for consistent error handling"""
    
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "API_ERROR",
        details: Optional[dict] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details
        super().__init__(self.message)
    
    def to_response(self) -> JSONResponse:
        """Convert to JSONResponse"""
        return error_response(
            message=self.message,
            error=self.error_code,
            details=self.details,
            status_code=self.status_code
        )


# Common exceptions
class NotFoundError(APIException):
    """Resource not found"""
    def __init__(self, resource: str, identifier: Any = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with ID {identifier} not found"
        super().__init__(message, 404, "NOT_FOUND")


class UnauthorizedError(APIException):
    """Authentication required"""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, 401, "UNAUTHORIZED")


class ForbiddenError(APIException):
    """Access denied"""
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, 403, "FORBIDDEN")


class ValidationError(APIException):
    """Validation failed"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, 422, "VALIDATION_ERROR", details)


class BusinessError(APIException):
    """Business logic error"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, 400, "BUSINESS_ERROR", details)


class ConflictError(APIException):
    """Resource conflict"""
    def __init__(self, message: str):
        super().__init__(message, 409, "CONFLICT")
