"""
Merchants Router
All merchant-related endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.database import app_context
from app.schemas.merchant import (
    MerchantResponse,
    SendPurchaseRequest,
    SendPurchaseResponse,
    ReceiveSettlementRequest,
    ReceiveSettlementResponse,
    MerchantRegistrationRequest,
    CreateBranchRequest,
    BranchResponse
)
from app.schemas.common import APIResponse
from app.services.auth_service import AuthService
from app.services.merchant_service import MerchantService
from app.utils.auth import require_role
from app.utils.response import success_response

router = APIRouter(prefix="/merchants", tags=["Merchants"])

# Dependency for merchant-only access
get_merchant = require_role("merchant")


@router.get(
    "/me",
    response_model=APIResponse[MerchantResponse],
    summary="Get Merchant Profile",
    description="Get the current merchant's profile and statistics."
)
async def get_merchant_profile(current_user: dict = Depends(get_merchant)):
    """Get merchant profile with business information"""
    try:
        with app_context():
            merchant = AuthService.get_merchant_by_user_id(current_user["user_id"])
            return success_response(
                data=merchant.to_dict(include_branches=True),
                message="Merchant profile retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/send-purchase-request",
    response_model=APIResponse[SendPurchaseResponse],
    summary="Send Purchase Request",
    description="Send a BNPL purchase request to a customer."
)
async def send_purchase_request(
    request: SendPurchaseRequest,
    current_user: dict = Depends(get_merchant)
):
    """Send a purchase request to a customer"""
    try:
        with app_context():
            merchant = AuthService.get_merchant_by_user_id(current_user["user_id"])
            
            from app.models import Customer
            customer = Customer.query.get(request.customer_id)
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            purchase_request = MerchantService.send_purchase_request(
                merchant_id=merchant.id,
                customer_id=request.customer_id,
                product_name=request.product_name,
                product_description=request.product_description,
                price=request.price,
                quantity=request.quantity,
                branch_id=request.branch_id
            )
            
            response = SendPurchaseResponse(
                request_id=purchase_request.id,
                reference_number=purchase_request.reference_number,
                status=purchase_request.status,
                total_amount=purchase_request.total_amount,
                expires_at=purchase_request.expires_at,
                customer_available_balance=customer.available_balance,
                message="Purchase request sent successfully"
            )
            
            return success_response(
                data=response.model_dump(),
                message="Purchase request sent successfully"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/receive-settlement",
    response_model=APIResponse[ReceiveSettlementResponse],
    summary="Receive Settlement",
    description="Request settlement for a completed transaction. Platform deducts 0.5% commission."
)
async def receive_settlement(
    request: ReceiveSettlementRequest,
    current_user: dict = Depends(get_merchant)
):
    """Request settlement for a transaction"""
    try:
        with app_context():
            merchant = AuthService.get_merchant_by_user_id(current_user["user_id"])
            settlement = MerchantService.receive_settlement(
                merchant_id=merchant.id,
                transaction_id=request.transaction_id
            )
            
            response = ReceiveSettlementResponse(
                settlement_id=settlement.id,
                settlement_reference=settlement.settlement_reference,
                gross_amount=settlement.gross_amount,
                commission_rate=settlement.commission_rate,
                commission_amount=settlement.commission_amount,
                net_amount=settlement.net_amount,
                status=settlement.status,
                message="Settlement created successfully"
            )
            
            return success_response(
                data=response.model_dump(),
                message="Settlement created successfully"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/transactions",
    response_model=APIResponse,
    summary="Get Transactions",
    description="Get merchant's transaction history."
)
async def get_transactions(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_merchant)
):
    """Get merchant transactions"""
    try:
        with app_context():
            merchant = AuthService.get_merchant_by_user_id(current_user["user_id"])
            transactions = MerchantService.get_merchant_transactions(
                merchant_id=merchant.id,
                status=status,
                limit=limit,
                offset=offset
            )
            return success_response(
                data=[t.to_dict() for t in transactions],
                message="Transactions retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/settlements",
    response_model=APIResponse,
    summary="Get Settlements",
    description="Get merchant's settlement history."
)
async def get_settlements(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_merchant)
):
    """Get merchant settlements"""
    try:
        with app_context():
            merchant = AuthService.get_merchant_by_user_id(current_user["user_id"])
            settlements = MerchantService.get_merchant_settlements(
                merchant_id=merchant.id,
                status=status,
                limit=limit,
                offset=offset
            )
            return success_response(
                data=[s.to_dict() for s in settlements],
                message="Settlements retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


from pydantic import BaseModel, Field

class WithdrawalRequest(BaseModel):
    """Request to withdraw balance"""
    amount: float = Field(..., gt=0, description="Amount to withdraw")
    bank_name: str = Field(..., min_length=1, description="Bank name")
    bank_account: str = Field(..., min_length=1, description="Bank account number")
    iban: str = Field(..., min_length=15, description="IBAN")


@router.post(
    "/request-withdrawal",
    response_model=APIResponse,
    summary="Request Withdrawal",
    description="Request withdrawal from merchant balance. Requires bank details."
)
async def request_withdrawal(
    request: WithdrawalRequest,
    current_user: dict = Depends(get_merchant)
):
    """Request withdrawal from balance"""
    try:
        with app_context():
            merchant = AuthService.get_merchant_by_user_id(current_user["user_id"])
            result = MerchantService.request_withdrawal(
                merchant_id=merchant.id,
                amount=request.amount,
                bank_name=request.bank_name,
                bank_account=request.bank_account,
                iban=request.iban
            )
            return success_response(
                data=result,
                message="Withdrawal request processed successfully"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/pending-requests",
    response_model=APIResponse,
    summary="Get Pending Requests",
    description="Get purchase requests pending customer action."
)
async def get_pending_requests(current_user: dict = Depends(get_merchant)):
    """Get pending purchase requests"""
    try:
        with app_context():
            merchant = AuthService.get_merchant_by_user_id(current_user["user_id"])
            requests = MerchantService.get_merchant_pending_requests(merchant.id)
            return success_response(
                data=[r.to_dict() for r in requests],
                message="Pending requests retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/purchase-requests",
    response_model=APIResponse,
    summary="Get All Purchase Requests",
    description="Get all purchase requests sent by the merchant with optional status filter."
)
async def get_all_purchase_requests(
    status_filter: str = None,
    current_user: dict = Depends(get_merchant)
):
    """Get all purchase requests for merchant"""
    try:
        with app_context():
            merchant = AuthService.get_merchant_by_user_id(current_user["user_id"])
            requests = MerchantService.get_merchant_all_requests(merchant.id, status_filter)
            return success_response(
                data=[r.to_dict(include_customer=True) for r in requests],
                message="Purchase requests retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/stats",
    response_model=APIResponse,
    summary="Get Statistics",
    description="Get merchant's business statistics."
)
async def get_stats(current_user: dict = Depends(get_merchant)):
    """Get merchant statistics"""
    try:
        with app_context():
            merchant = AuthService.get_merchant_by_user_id(current_user["user_id"])
            stats = MerchantService.get_merchant_stats(merchant.id)
            return success_response(
                data=stats,
                message="Statistics retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/branches",
    response_model=APIResponse[BranchResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Branch",
    description="Create a new branch for the merchant."
)
async def create_branch(
    request: CreateBranchRequest,
    current_user: dict = Depends(get_merchant)
):
    """Create a new branch"""
    try:
        with app_context():
            merchant = AuthService.get_merchant_by_user_id(current_user["user_id"])
            branch = MerchantService.create_branch(
                merchant_id=merchant.id,
                name=request.name,
                address=request.address,
                city=request.city,
                phone=request.phone
            )
            return success_response(
                data=branch.to_dict(),
                message="Branch created successfully"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/branches",
    response_model=APIResponse,
    summary="Get Branches",
    description="Get merchant's branches."
)
async def get_branches(
    active_only: bool = Query(True, description="Show only active branches"),
    current_user: dict = Depends(get_merchant)
):
    """Get merchant branches"""
    try:
        with app_context():
            merchant = AuthService.get_merchant_by_user_id(current_user["user_id"])
            branches = MerchantService.get_merchant_branches(
                merchant_id=merchant.id,
                active_only=active_only
            )
            return success_response(
                data=[b.to_dict() for b in branches],
                message="Branches retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/cancel-request/{request_id}",
    response_model=APIResponse,
    summary="Cancel Purchase Request",
    description="Cancel a pending purchase request."
)
async def cancel_purchase_request(
    request_id: int,
    current_user: dict = Depends(get_merchant)
):
    """Cancel a purchase request"""
    try:
        with app_context():
            merchant = AuthService.get_merchant_by_user_id(current_user["user_id"])
            purchase_request = MerchantService.cancel_purchase_request(
                merchant_id=merchant.id,
                request_id=request_id
            )
            return success_response(
                data=purchase_request.to_dict(),
                message="Purchase request cancelled"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/lookup-customer/{customer_code}",
    response_model=APIResponse,
    summary="Lookup Customer by Code",
    description="Look up a customer's basic info and available balance for purchase using their unique customer code."
)
async def lookup_customer(
    customer_code: str,
    current_user: dict = Depends(get_merchant)
):
    """Look up customer for purchase by their unique code"""
    try:
        with app_context():
            from app.models import Customer, User
            customer = Customer.query.filter_by(customer_code=customer_code.upper()).first()
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found"
                )
            
            # Get user info for name
            user = User.query.get(customer.user_id)
            
            return success_response(
                data={
                    "id": customer.id,
                    "customer_id": customer.id,
                    "customer_code": customer.customer_code,
                    "full_name": user.full_name if user else None,
                    "credit_limit": customer.credit_limit,
                    "available_balance": customer.available_balance,
                    "status": customer.status,
                    "can_purchase": customer.status == "active"
                },
                message="Customer found"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
