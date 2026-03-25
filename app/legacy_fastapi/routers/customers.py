"""
Customers Router
All customer-related endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.database import app_context
from app.schemas.customer import (
    CustomerResponse,
    AcceptPurchaseRequest,
    AcceptPurchaseResponse,
    RejectPurchaseRequest,
    UpdateLimitRequest,
    UpdateLimitResponse,
    SelectRepaymentPlanRequest,
    SelectRepaymentPlanResponse,
    PaymentScheduleItem,
    MakePaymentRequest,
    MakePaymentResponse
)
from app.schemas.common import APIResponse
from app.services.auth_service import AuthService
from app.services.customer_service import CustomerService
from app.services.payment_service import PaymentService
from app.utils.auth import require_role
from app.utils.response import success_response

router = APIRouter(prefix="/customers", tags=["Customers"])

# Dependency for customer-only access
get_customer = require_role("customer")


@router.get(
    "/me",
    response_model=APIResponse[CustomerResponse],
    summary="Get Customer Profile",
    description="Get the current customer's profile and balance information."
)
async def get_customer_profile(current_user: dict = Depends(get_customer)):
    """Get customer profile with credit and balance information"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            return success_response(
                data=customer.to_dict(),
                message="Customer profile retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/accept-purchase",
    response_model=APIResponse[AcceptPurchaseResponse],
    summary="Accept Purchase Request",
    description="Accept a pending purchase request from a merchant."
)
async def accept_purchase(
    request: AcceptPurchaseRequest,
    current_user: dict = Depends(get_customer)
):
    """Accept a purchase request"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            transaction, repayment_plan = CustomerService.accept_purchase(
                customer_id=customer.id,
                request_id=request.request_id,
                installment_months=request.installment_months
            )
            
            response = AcceptPurchaseResponse(
                transaction_id=transaction.id,
                transaction_number=transaction.transaction_number,
                remaining_balance=customer.available_balance,
                due_date=transaction.due_date,
                total_amount=transaction.total_amount,
                installment_months=repayment_plan.plan_type,
                installment_amount=repayment_plan.installment_amount,
                message="Purchase accepted successfully"
            )
            
            return success_response(
                data=response.model_dump(),
                message="Purchase accepted successfully"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch(
    "/update-limit",
    response_model=APIResponse[UpdateLimitResponse],
    summary="Update Credit Limit",
    description="Request a credit limit increase. Auto-approved up to 5,000 SAR."
)
async def update_limit(
    request: UpdateLimitRequest,
    current_user: dict = Depends(get_customer)
):
    """Request credit limit update"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            updated_customer, history = CustomerService.update_credit_limit(
                customer_id=customer.id,
                new_limit=request.new_limit,
                reason=request.reason
            )
            
            response = UpdateLimitResponse(
                previous_limit=history.previous_limit,
                new_limit=history.new_limit,
                available_balance=updated_customer.available_balance,
                status=history.status,
                message=f"Credit limit {'updated' if history.status == 'approved' else 'pending approval'}"
            )
            
            return success_response(
                data=response.model_dump(),
                message="Credit limit updated successfully"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/select-repayment-plan",
    response_model=APIResponse[SelectRepaymentPlanResponse],
    summary="Select Repayment Plan",
    description="Select a repayment plan for a transaction (1, 3, 6, 12, 18, or 24 months)."
)
async def select_repayment_plan(
    request: SelectRepaymentPlanRequest,
    current_user: dict = Depends(get_customer)
):
    """Select a repayment plan"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            plan = CustomerService.select_repayment_plan(
                customer_id=customer.id,
                transaction_id=request.transaction_id,
                plan_type=request.plan_type
            )
            
            schedule_items = []
            for schedule in plan.schedules.order_by("installment_number"):
                schedule_items.append(PaymentScheduleItem(
                    installment_number=schedule.installment_number,
                    amount=schedule.amount,
                    due_date=schedule.due_date,
                    status=schedule.status
                ))
            
            response = SelectRepaymentPlanResponse(
                plan_id=plan.id,
                plan_reference=plan.plan_reference,
                plan_type=plan.plan_type,
                total_amount=plan.total_amount,
                installment_amount=plan.installment_amount,
                number_of_installments=plan.number_of_installments,
                payment_schedule=schedule_items,
                next_payment_date=plan.next_payment_date,
                next_payment_amount=plan.next_payment_amount,
                message="Repayment plan created successfully"
            )
            
            return success_response(
                data=response.model_dump(),
                message="Repayment plan created successfully"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/make-payment",
    response_model=APIResponse[MakePaymentResponse],
    summary="Make Payment",
    description="Make a payment against a transaction or repayment plan."
)
async def make_payment(
    request: MakePaymentRequest,
    current_user: dict = Depends(get_customer)
):
    """Make a payment"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            payment, transaction, settlement_triggered = CustomerService.make_payment(
                customer_id=customer.id,
                amount=request.amount,
                transaction_id=request.transaction_id,
                plan_id=request.plan_id,
                payment_method=request.payment_method or "wallet"
            )
            
            response = MakePaymentResponse(
                receipt_id=payment.payment_reference,
                payment_id=payment.id,
                amount_paid=payment.amount,
                new_balance=transaction.remaining_amount,
                transaction_status=transaction.status,
                settlement_triggered=settlement_triggered,
                message="Payment processed successfully"
            )
            
            return success_response(
                data=response.model_dump(),
                message="Payment processed successfully"
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
    description="Get customer's transaction history."
)
async def get_transactions(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_customer)
):
    """Get customer transactions"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            transactions = CustomerService.get_customer_transactions(
                customer_id=customer.id,
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
    "/pending-requests",
    response_model=APIResponse,
    summary="Get Pending Requests",
    description="Get pending purchase requests awaiting your action."
)
async def get_pending_requests(current_user: dict = Depends(get_customer)):
    """Get pending purchase requests"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            requests = CustomerService.get_customer_pending_requests(customer.id)
            return success_response(
                data=[r.to_dict(include_merchant=True) for r in requests],
                message="Pending requests retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/repayment-plans",
    response_model=APIResponse,
    summary="Get Repayment Plans",
    description="Get customer's repayment plans."
)
async def get_repayment_plans(
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_customer)
):
    """Get repayment plans"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            plans = CustomerService.get_customer_repayment_plans(
                customer_id=customer.id,
                status=status
            )
            return success_response(
                data=[p.to_dict(include_schedule=True) for p in plans],
                message="Repayment plans retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/upcoming-payments",
    response_model=APIResponse,
    summary="Get Upcoming Payments",
    description="Get upcoming scheduled payments."
)
async def get_upcoming_payments(
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_customer)
):
    """Get upcoming payments"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            upcoming = PaymentService.get_upcoming_payments(
                customer_id=customer.id,
                days=days
            )
            return success_response(
                data=upcoming,
                message="Upcoming payments retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/limits",
    response_model=APIResponse,
    summary="Get Credit Limits",
    description="Get customer's credit limit information."
)
async def get_limits(current_user: dict = Depends(get_customer)):
    """Get customer credit limits"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            return success_response(
                data={
                    "total_limit": customer.credit_limit,
                    "available_limit": customer.available_balance,
                    "used_limit": customer.outstanding_balance
                },
                message="Credit limits retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/requests",
    response_model=APIResponse,
    summary="Get All Requests",
    description="Get all purchase requests with pagination."
)
async def get_all_requests(
    status: Optional[str] = Query("all", description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_customer)
):
    """Get all customer purchase requests"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            requests, total = CustomerService.get_customer_all_requests(
                customer_id=customer.id,
                status=status,
                page=page,
                page_size=page_size
            )
            return success_response(
                data={
                    "items": [r.to_dict(include_merchant=True) for r in requests],
                    "total": total,
                    "page": page,
                    "page_size": page_size
                },
                message="Requests retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/schedules",
    response_model=APIResponse,
    summary="Get Repayment Schedules",
    description="Get customer's repayment schedules with pagination."
)
async def get_schedules(
    status: Optional[str] = Query("pending", description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_customer)
):
    """Get customer repayment schedules"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            schedules, total = CustomerService.get_customer_schedules(
                customer_id=customer.id,
                status=status,
                page=page,
                page_size=page_size
            )
            return success_response(
                data={
                    "items": [s.to_dict() for s in schedules],
                    "total": total,
                    "page": page,
                    "page_size": page_size
                },
                message="Schedules retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/my-transactions",
    response_model=APIResponse,
    summary="Get My Transactions",
    description="Get all accepted purchase transactions with installment details."
)
async def get_my_transactions(
    status_filter: Optional[str] = Query(None, description="Filter by status: active, completed"),
    current_user: dict = Depends(get_customer)
):
    """Get customer's transactions with repayment details"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            from app.models import Transaction, RepaymentPlan, RepaymentSchedule, Merchant
            
            query = Transaction.query.filter_by(customer_id=customer.id)
            if status_filter:
                query = query.filter_by(status=status_filter)
            
            transactions = query.order_by(Transaction.created_at.desc()).all()
            
            result = []
            for t in transactions:
                # Get repayment plan
                plan = RepaymentPlan.query.filter_by(transaction_id=t.id).first()
                
                # Get merchant info
                merchant = Merchant.query.get(t.merchant_id)
                
                # Get remaining schedules
                remaining_schedules = []
                if plan:
                    schedules = RepaymentSchedule.query.filter_by(
                        plan_id=plan.id, 
                        status="pending"
                    ).order_by(RepaymentSchedule.installment_number).all()
                    remaining_schedules = [s.to_dict() for s in schedules]
                
                result.append({
                    "transaction_id": t.id,
                    "transaction_number": t.transaction_number,
                    "merchant_name": merchant.shop_name if merchant else None,
                    "total_amount": t.total_amount,
                    "paid_amount": t.paid_amount,
                    "remaining_amount": t.remaining_amount,
                    "status": t.status,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                    "installment_months": plan.plan_type if plan else 1,
                    "installment_amount": plan.installment_amount if plan else t.total_amount,
                    "paid_installments": plan.paid_installments if plan else 0,
                    "remaining_installments": (plan.number_of_installments - plan.paid_installments) if plan else 0,
                    "next_payment_date": plan.next_payment_date.isoformat() if plan and plan.next_payment_date else None,
                    "remaining_schedules": remaining_schedules
                })
            
            return success_response(
                data=result,
                message="Transactions retrieved"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/reject-purchase",
    response_model=APIResponse,
    summary="Reject Purchase Request",
    description="Reject a pending purchase request."
)
async def reject_purchase(
    request: RejectPurchaseRequest,
    current_user: dict = Depends(get_customer)
):
    """Reject a purchase request"""
    try:
        with app_context():
            customer = AuthService.get_customer_by_user_id(current_user["user_id"])
            purchase_request = CustomerService.reject_purchase(
                customer_id=customer.id,
                request_id=request.request_id,
                reason=request.rejection_reason
            )
            return success_response(
                data=purchase_request.to_dict(),
                message="Purchase request rejected"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
