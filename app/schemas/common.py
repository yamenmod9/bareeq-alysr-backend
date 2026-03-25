"""
Common Schemas - Shared across all endpoints
"""
from datetime import datetime
from typing import Any, Optional, Generic, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar('T')


class APIResponse(BaseModel, Generic[T]):
    """
    Standardized API Response Format
    All endpoints return this structure
    """
    success: bool = Field(default=True, description="Whether the request was successful")
    data: Optional[T] = Field(default=None, description="Response data")
    message: str = Field(default="Success", description="Human-readable message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ErrorResponse(BaseModel):
    """Error response format"""
    success: bool = False
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[dict] = Field(default=None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response format"""
    items: List[T]
    total: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    version: str
    database: str = "connected"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
