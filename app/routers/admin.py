"""
Admin Router - Dashboard and Management Endpoints
Provides comprehensive admin functionality for platform management
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import func, desc
from pydantic import BaseModel

from app.flask_app import flask_app
from app.database import db
from app.models import User, Customer, Merchant, Transaction, PurchaseRequest, Settlement, Payment
from app.utils.auth import get_admin
from app.utils.response import success_response, error_response
from app.schemas.common import APIResponse


router = APIRouter(prefix="/admin", tags=["Admin"])


def app_context():
    """Context manager for Flask app context"""
    return flask_app.app_context()


# ==================== Schemas ====================

class DashboardStats(BaseModel):
    total_users: int
    total_customers: int
    total_merchants: int
    total_transactions: int
    active_transactions: int
    completed_transactions: int
    pending_purchase_requests: int
    total_volume: float
    platform_commission: float
    pending_settlements: int
    new_users_today: int
    new_users_this_week: int


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    phone: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]


class CustomerDetailResponse(BaseModel):
    id: int
    user_id: int
    email: str
    full_name: Optional[str]
    phone: Optional[str]
    customer_code: str
    credit_limit: float
    available_balance: float
    outstanding_balance: float
    status: str
    risk_score: int
    created_at: datetime
    total_transactions: int
    total_spent: float


class MerchantDetailResponse(BaseModel):
    id: int
    user_id: int
    email: str
    full_name: Optional[str]
    shop_name: str
    status: str
    is_verified: bool
    total_transactions: int
    total_volume: float
    created_at: datetime


class TransactionDetailResponse(BaseModel):
    id: int
    transaction_number: str
    customer_email: str
    merchant_shop: str
    total_amount: float
    paid_amount: float
    remaining_amount: float
    status: str
    created_at: datetime
    due_date: datetime


class UpdateUserStatusRequest(BaseModel):
    is_active: bool


class UpdateCustomerLimitRequest(BaseModel):
    new_limit: float


class UpdateMerchantStatusRequest(BaseModel):
    status: str  # active, suspended, blocked
    is_verified: Optional[bool] = None


# ==================== Dashboard ====================

@router.get(
    "/dashboard",
    response_model=APIResponse[DashboardStats],
    summary="Get Admin Dashboard Stats"
)
async def get_dashboard_stats(current_user: dict = Depends(get_admin)):
    """Get comprehensive dashboard statistics"""
    try:
        with app_context():
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = today - timedelta(days=7)
            
            # Basic counts
            total_users = User.query.count()
            total_customers = Customer.query.count()
            total_merchants = Merchant.query.count()
            
            # Transaction stats
            total_transactions = Transaction.query.count()
            active_transactions = Transaction.query.filter_by(status="active").count()
            completed_transactions = Transaction.query.filter_by(status="completed").count()
            
            # Purchase requests
            pending_purchase_requests = PurchaseRequest.query.filter_by(status="pending").count()
            
            # Financial stats
            total_volume = db.session.query(
                func.coalesce(func.sum(Transaction.total_amount), 0)
            ).scalar() or 0
            
            platform_commission = db.session.query(
                func.coalesce(func.sum(Transaction.commission_amount), 0)
            ).scalar() or 0
            
            # Settlements
            pending_settlements = Settlement.query.filter_by(status="pending").count()
            
            # New users
            new_users_today = User.query.filter(User.created_at >= today).count()
            new_users_this_week = User.query.filter(User.created_at >= week_ago).count()
            
            stats = DashboardStats(
                total_users=total_users,
                total_customers=total_customers,
                total_merchants=total_merchants,
                total_transactions=total_transactions,
                active_transactions=active_transactions,
                completed_transactions=completed_transactions,
                pending_purchase_requests=pending_purchase_requests,
                total_volume=float(total_volume),
                platform_commission=float(platform_commission),
                pending_settlements=pending_settlements,
                new_users_today=new_users_today,
                new_users_this_week=new_users_this_week
            )
            
            return success_response(
                data=stats.model_dump(),
                message="Dashboard stats retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== Users Management ====================

@router.get(
    "/users",
    response_model=APIResponse[List[UserResponse]],
    summary="Get All Users"
)
async def get_all_users(
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by email or name"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_admin)
):
    """Get all users with optional filters"""
    try:
        with app_context():
            query = User.query
            
            if role:
                query = query.filter_by(role=role)
            if is_active is not None:
                query = query.filter_by(is_active=is_active)
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    (User.email.ilike(search_term)) | 
                    (User.full_name.ilike(search_term))
                )
            
            users = query.order_by(desc(User.created_at)).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            user_list = [
                UserResponse(
                    id=u.id,
                    email=u.email,
                    full_name=u.full_name,
                    phone=u.phone,
                    role=u.role,
                    is_active=u.is_active,
                    is_verified=u.is_verified,
                    created_at=u.created_at,
                    last_login=u.last_login
                ).model_dump()
                for u in users.items
            ]
            
            return success_response(
                data=user_list,
                message=f"Retrieved {len(user_list)} users (page {page})"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put(
    "/users/{user_id}/status",
    response_model=APIResponse,
    summary="Update User Status"
)
async def update_user_status(
    user_id: int,
    request: UpdateUserStatusRequest,
    current_user: dict = Depends(get_admin)
):
    """Activate or deactivate a user"""
    try:
        with app_context():
            user = User.query.get(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Prevent admin from deactivating themselves
            if user.id == current_user["user_id"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot modify your own status"
                )
            
            user.is_active = request.is_active
            db.session.commit()
            
            return success_response(
                message=f"User {'activated' if request.is_active else 'deactivated'} successfully"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== Customers Management ====================

@router.get(
    "/customers",
    response_model=APIResponse[List[CustomerDetailResponse]],
    summary="Get All Customers"
)
async def get_all_customers(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_admin)
):
    """Get all customers with details"""
    try:
        with app_context():
            query = Customer.query.join(User)
            
            if status_filter:
                query = query.filter(Customer.status == status_filter)
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    (User.email.ilike(search_term)) | 
                    (User.full_name.ilike(search_term)) |
                    (Customer.customer_code.ilike(search_term))
                )
            
            customers = query.order_by(desc(Customer.created_at)).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            customer_list = []
            for c in customers.items:
                user = User.query.get(c.user_id)
                total_txns = Transaction.query.filter_by(customer_id=c.id).count()
                total_spent = db.session.query(
                    func.coalesce(func.sum(Transaction.total_amount), 0)
                ).filter(Transaction.customer_id == c.id).scalar() or 0
                
                customer_list.append(
                    CustomerDetailResponse(
                        id=c.id,
                        user_id=c.user_id,
                        email=user.email,
                        full_name=user.full_name,
                        phone=user.phone,
                        customer_code=c.customer_code,
                        credit_limit=c.credit_limit,
                        available_balance=c.available_balance,
                        outstanding_balance=c.outstanding_balance,
                        status=c.status,
                        risk_score=c.risk_score or 50,
                        created_at=c.created_at,
                        total_transactions=total_txns,
                        total_spent=float(total_spent)
                    ).model_dump()
                )
            
            return success_response(
                data=customer_list,
                message=f"Retrieved {len(customer_list)} customers"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put(
    "/customers/{customer_id}/limit",
    response_model=APIResponse,
    summary="Update Customer Credit Limit"
)
async def update_customer_limit(
    customer_id: int,
    request: UpdateCustomerLimitRequest,
    current_user: dict = Depends(get_admin)
):
    """Update a customer's credit limit"""
    try:
        with app_context():
            customer = Customer.query.get(customer_id)
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            old_limit = customer.credit_limit
            if not customer.update_credit_limit(request.new_limit):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot reduce limit below outstanding balance"
                )
            
            db.session.commit()
            
            return success_response(
                message=f"Credit limit updated from {old_limit} to {request.new_limit} SAR"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put(
    "/customers/{customer_id}/status",
    response_model=APIResponse,
    summary="Update Customer Status"
)
async def update_customer_status(
    customer_id: int,
    status_value: str = Query(..., alias="status"),
    current_user: dict = Depends(get_admin)
):
    """Update customer status (active, suspended, blocked)"""
    try:
        with app_context():
            customer = Customer.query.get(customer_id)
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            if status_value not in ["active", "suspended", "blocked"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid status. Must be: active, suspended, or blocked"
                )
            
            customer.status = status_value
            db.session.commit()
            
            return success_response(
                message=f"Customer status updated to {status_value}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== Merchants Management ====================

@router.get(
    "/merchants",
    response_model=APIResponse[List[MerchantDetailResponse]],
    summary="Get All Merchants"
)
async def get_all_merchants(
    status_filter: Optional[str] = Query(None, alias="status"),
    is_verified: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_admin)
):
    """Get all merchants with details"""
    try:
        with app_context():
            query = Merchant.query.join(User)
            
            if status_filter:
                query = query.filter(Merchant.status == status_filter)
            if is_verified is not None:
                query = query.filter(Merchant.is_verified == is_verified)
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    (User.email.ilike(search_term)) | 
                    (Merchant.shop_name.ilike(search_term))
                )
            
            merchants = query.order_by(desc(Merchant.created_at)).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            merchant_list = []
            for m in merchants.items:
                user = User.query.get(m.user_id)
                merchant_list.append(
                    MerchantDetailResponse(
                        id=m.id,
                        user_id=m.user_id,
                        email=user.email,
                        full_name=user.full_name,
                        shop_name=m.shop_name,
                        status=m.status,
                        is_verified=m.is_verified,
                        total_transactions=m.total_transactions or 0,
                        total_volume=m.total_volume or 0,
                        created_at=m.created_at
                    ).model_dump()
                )
            
            return success_response(
                data=merchant_list,
                message=f"Retrieved {len(merchant_list)} merchants"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put(
    "/merchants/{merchant_id}/status",
    response_model=APIResponse,
    summary="Update Merchant Status"
)
async def update_merchant_status(
    merchant_id: int,
    request: UpdateMerchantStatusRequest,
    current_user: dict = Depends(get_admin)
):
    """Update merchant status and verification"""
    try:
        with app_context():
            merchant = Merchant.query.get(merchant_id)
            if not merchant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Merchant not found"
                )
            
            if request.status not in ["active", "suspended", "blocked"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid status"
                )
            
            merchant.status = request.status
            if request.is_verified is not None:
                merchant.is_verified = request.is_verified
            
            db.session.commit()
            
            return success_response(
                message=f"Merchant status updated to {request.status}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== Transactions Management ====================

@router.get(
    "/transactions",
    response_model=APIResponse[List[TransactionDetailResponse]],
    summary="Get All Transactions"
)
async def get_all_transactions(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_admin)
):
    """Get all transactions with details"""
    try:
        with app_context():
            query = Transaction.query
            
            if status_filter:
                query = query.filter(Transaction.status == status_filter)
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    Transaction.transaction_number.ilike(search_term)
                )
            
            transactions = query.order_by(desc(Transaction.created_at)).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            txn_list = []
            for t in transactions.items:
                customer = Customer.query.get(t.customer_id)
                customer_user = User.query.get(customer.user_id) if customer else None
                merchant = Merchant.query.get(t.merchant_id)
                
                txn_list.append(
                    TransactionDetailResponse(
                        id=t.id,
                        transaction_number=t.transaction_number,
                        customer_email=customer_user.email if customer_user else "N/A",
                        merchant_shop=merchant.shop_name if merchant else "N/A",
                        total_amount=t.total_amount,
                        paid_amount=t.paid_amount,
                        remaining_amount=t.remaining_amount,
                        status=t.status,
                        created_at=t.created_at,
                        due_date=t.due_date
                    ).model_dump()
                )
            
            return success_response(
                data=txn_list,
                message=f"Retrieved {len(txn_list)} transactions"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== Purchase Requests ====================

@router.get(
    "/purchase-requests",
    response_model=APIResponse,
    summary="Get All Purchase Requests"
)
async def get_all_purchase_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_admin)
):
    """Get all purchase requests"""
    try:
        with app_context():
            query = PurchaseRequest.query
            
            if status_filter:
                query = query.filter(PurchaseRequest.status == status_filter)
            
            requests = query.order_by(desc(PurchaseRequest.created_at)).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            request_list = []
            for r in requests.items:
                customer = Customer.query.get(r.customer_id)
                customer_user = User.query.get(customer.user_id) if customer else None
                merchant = Merchant.query.get(r.merchant_id)
                
                request_list.append({
                    "id": r.id,
                    "reference_number": r.reference_number,
                    "customer_email": customer_user.email if customer_user else "N/A",
                    "merchant_shop": merchant.shop_name if merchant else "N/A",
                    "product_name": r.product_name,
                    "total_amount": r.total_amount,
                    "status": r.status,
                    "created_at": r.created_at.isoformat(),
                    "expires_at": r.expires_at.isoformat()
                })
            
            return success_response(
                data=request_list,
                message=f"Retrieved {len(request_list)} purchase requests"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== Settlements ====================

@router.get(
    "/settlements",
    response_model=APIResponse,
    summary="Get All Settlements"
)
async def get_all_settlements(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_admin)
):
    """Get all settlements"""
    try:
        with app_context():
            query = Settlement.query
            
            if status_filter:
                query = query.filter(Settlement.status == status_filter)
            
            settlements = query.order_by(desc(Settlement.created_at)).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            settlement_list = []
            for s in settlements.items:
                merchant = Merchant.query.get(s.merchant_id)
                
                settlement_list.append({
                    "id": s.id,
                    "settlement_reference": s.settlement_reference,
                    "merchant_shop": merchant.shop_name if merchant else "N/A",
                    "gross_amount": s.gross_amount,
                    "commission_amount": s.commission_amount,
                    "net_amount": s.net_amount,
                    "status": s.status,
                    "created_at": s.created_at.isoformat()
                })
            
            return success_response(
                data=settlement_list,
                message=f"Retrieved {len(settlement_list)} settlements"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put(
    "/settlements/{settlement_id}/approve",
    response_model=APIResponse,
    summary="Approve Settlement"
)
async def approve_settlement(
    settlement_id: int,
    current_user: dict = Depends(get_admin)
):
    """Approve a pending settlement for payout"""
    try:
        with app_context():
            settlement = Settlement.query.get(settlement_id)
            if not settlement:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Settlement not found"
                )
            
            if settlement.status != "pending":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Settlement is not pending"
                )
            
            settlement.status = "processing"
            settlement.processed_at = datetime.utcnow()
            db.session.commit()
            
            return success_response(
                message="Settlement approved for processing"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
