"""
Customer Service
Handles customer operations: accept purchases, update limits, select plans, make payments
"""
from datetime import datetime
from typing import List, Optional, Tuple

from app.database import db
from app.models import (
    Customer, 
    CustomerLimitHistory,
    PurchaseRequest, 
    Transaction,
    RepaymentPlan,
    RepaymentSchedule,
    Payment
)
from app.utils.response import (
    NotFoundError, 
    BusinessError, 
    ValidationError,
    ForbiddenError
)
from app.config import Config


class CustomerService:
    """Customer business logic service"""
    
    # === Accept Purchase ===
    
    @staticmethod
    def accept_purchase(customer_id: int, request_id: int, installment_months: int = 1) -> Transaction:
        """
        Accept a purchase request and create a transaction with repayment plan
        
        Args:
            customer_id: Customer ID (from JWT)
            request_id: Purchase request ID to accept
            installment_months: Number of months for installment (1, 3, 6, 12)
        
        Returns:
            Created Transaction
        
        Raises:
            NotFoundError: If request not found
            ForbiddenError: If request not for this customer
            BusinessError: If request expired, already processed, or insufficient balance
        """
        # Validate installment months
        valid_plans = [1, 3, 6, 12]
        if installment_months not in valid_plans:
            raise BusinessError(f"Invalid installment plan. Choose from: {valid_plans}")
        
        # Get purchase request
        purchase_request = PurchaseRequest.query.get(request_id)
        if not purchase_request:
            raise NotFoundError("Purchase request", request_id)
        
        # Verify customer owns this request
        if purchase_request.customer_id != customer_id:
            raise ForbiddenError("This purchase request is not for you")
        
        # Check status
        if purchase_request.status != "pending":
            raise BusinessError(f"Purchase request is already {purchase_request.status}")
        
        # Check expiry
        if purchase_request.is_expired:
            purchase_request.mark_expired()
            db.session.commit()
            raise BusinessError("Purchase request has expired")
        
        # Get customer
        customer = Customer.query.get(customer_id)
        if not customer:
            raise NotFoundError("Customer", customer_id)
        
        # Check customer status
        if customer.status != "active":
            raise BusinessError("Your account is not active")
        
        # Check credit limit
        if not customer.can_afford(purchase_request.total_amount):
            raise BusinessError(
                f"Insufficient balance. Required: {purchase_request.total_amount} SAR, "
                f"Available: {customer.available_balance} SAR"
            )
        
        # Deduct from customer balance
        customer.deduct_balance(purchase_request.total_amount)
        
        # Mark request as accepted
        purchase_request.accept()
        
        # Create transaction
        transaction = Transaction(
            merchant_id=purchase_request.merchant_id,
            customer_id=customer_id,
            purchase_request_id=request_id,
            total_amount=purchase_request.total_amount,
            remaining_amount=purchase_request.total_amount,
            commission_rate=Config.PLATFORM_COMMISSION_RATE
        )
        
        db.session.add(transaction)
        db.session.flush()
        
        # Link transaction to purchase request
        purchase_request.transaction_id = transaction.id
        
        # Create repayment plan with selected installment months
        repayment_plan = RepaymentPlan(
            transaction_id=transaction.id,
            customer_id=customer_id,
            plan_type=installment_months,
            total_amount=purchase_request.total_amount,
            installment_amount=RepaymentPlan.calculate_installment(purchase_request.total_amount, installment_months),
            number_of_installments=installment_months
        )
        db.session.add(repayment_plan)
        db.session.flush()
        
        # Generate payment schedule
        repayment_plan.generate_schedule()
        
        # Link repayment plan to transaction
        transaction.repayment_plan_id = repayment_plan.id
        
        # Update merchant stats
        merchant = purchase_request.merchant
        merchant.increment_stats(purchase_request.total_amount)
        
        # Create settlement immediately (merchant receives money after 0.5% commission)
        from app.services.merchant_service import MerchantService
        MerchantService.create_settlement(transaction.id)
        
        db.session.commit()
        
        return transaction, repayment_plan
    
    # === Update Credit Limit ===
    
    @staticmethod
    def update_credit_limit(
        customer_id: int, 
        new_limit: float,
        reason: str = None
    ) -> Tuple[Customer, CustomerLimitHistory]:
        """
        Request credit limit update (auto-approve in MVP)
        
        Args:
            customer_id: Customer ID
            new_limit: Requested new limit
            reason: Reason for increase
        
        Returns:
            Tuple of (Customer, LimitHistory)
        
        Raises:
            ValidationError: If limit invalid
            BusinessError: If limit too high or decrease below outstanding
        """
        customer = Customer.query.get(customer_id)
        if not customer:
            raise NotFoundError("Customer", customer_id)
        
        # Validate limit
        if new_limit <= 0:
            raise ValidationError("Credit limit must be positive")
        
        if new_limit > Config.MAX_CREDIT_LIMIT:
            raise BusinessError(
                f"Maximum credit limit is {Config.MAX_CREDIT_LIMIT} SAR"
            )
        
        if new_limit < customer.outstanding_balance:
            raise BusinessError(
                f"Cannot reduce limit below outstanding balance "
                f"({customer.outstanding_balance} SAR)"
            )
        
        previous_limit = customer.credit_limit
        
        # Determine if auto-approve or needs admin review
        if new_limit <= Config.AUTO_APPROVE_LIMIT_CEILING:
            # Auto-approve
            status = "approved"
            approved_limit = new_limit
            approved_by = "auto"
        else:
            # For MVP, still auto-approve but flag it
            status = "approved"
            approved_limit = new_limit
            approved_by = "auto_high_limit"
        
        # Create history record
        history = CustomerLimitHistory(
            customer_id=customer_id,
            previous_limit=previous_limit,
            new_limit=approved_limit,
            requested_limit=new_limit,
            status=status,
            reason=reason,
            approved_by=approved_by
        )
        
        # Update customer limit
        customer.update_credit_limit(approved_limit)
        
        db.session.add(history)
        db.session.commit()
        
        return customer, history
    
    # === Select Repayment Plan ===
    
    @staticmethod
    def select_repayment_plan(
        customer_id: int,
        transaction_id: int,
        plan_type: int
    ) -> RepaymentPlan:
        """
        Select a repayment plan for a transaction
        Plans: 1, 3, 6, 12, 18, 24 months
        
        Args:
            customer_id: Customer ID
            transaction_id: Transaction ID
            plan_type: Plan duration in months
        
        Returns:
            Created RepaymentPlan with schedule
        
        Raises:
            ValidationError: If plan type invalid
            BusinessError: If transaction not eligible
        """
        # Validate plan type
        if not RepaymentPlan.validate_plan_type(plan_type):
            raise ValidationError(
                f"Invalid plan type. Options: {Config.REPAYMENT_PLANS}"
            )
        
        # Get transaction
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            raise NotFoundError("Transaction", transaction_id)
        
        # Verify ownership
        if transaction.customer_id != customer_id:
            raise ForbiddenError("This transaction is not yours")
        
        # Check transaction status
        if transaction.status not in ["active"]:
            raise BusinessError(f"Transaction is {transaction.status}, cannot set repayment plan")
        
        # Check if plan already exists
        if transaction.repayment_plan_id:
            raise BusinessError("Transaction already has a repayment plan")
        
        # Calculate installment
        installment_amount = RepaymentPlan.calculate_installment(
            transaction.remaining_amount, 
            plan_type
        )
        
        # Create repayment plan
        plan = RepaymentPlan(
            transaction_id=transaction_id,
            customer_id=customer_id,
            plan_type=plan_type,
            total_amount=transaction.remaining_amount,
            installment_amount=installment_amount,
            number_of_installments=plan_type,
            remaining_amount=transaction.remaining_amount
        )
        
        db.session.add(plan)
        db.session.flush()
        
        # Generate payment schedule
        schedules = plan.generate_schedule()
        for schedule in schedules:
            db.session.add(schedule)
        
        # Link plan to transaction
        transaction.repayment_plan_id = plan.id
        
        # Update transaction due date to last installment
        if schedules:
            transaction.due_date = schedules[-1].due_date
        
        db.session.commit()
        
        return plan
    
    # === Make Payment ===
    
    @staticmethod
    def make_payment(
        customer_id: int,
        amount: float,
        transaction_id: int = None,
        plan_id: int = None,
        payment_method: str = "wallet"
    ) -> Tuple[Payment, Transaction, bool]:
        """
        Process a customer payment
        
        Args:
            customer_id: Customer ID
            amount: Payment amount
            transaction_id: Transaction ID (optional if plan_id provided)
            plan_id: Repayment plan ID (optional if transaction_id provided)
            payment_method: Payment method
        
        Returns:
            Tuple of (Payment, Transaction, settlement_triggered)
        
        Raises:
            ValidationError: If neither ID provided or amount invalid
            BusinessError: If payment exceeds remaining
        """
        if not transaction_id and not plan_id:
            raise ValidationError("Either transaction_id or plan_id is required")
        
        if amount <= 0:
            raise ValidationError("Payment amount must be positive")
        
        # Get transaction
        if plan_id:
            plan = RepaymentPlan.query.get(plan_id)
            if not plan:
                raise NotFoundError("Repayment plan", plan_id)
            if plan.customer_id != customer_id:
                raise ForbiddenError("This repayment plan is not yours")
            transaction = Transaction.query.get(plan.transaction_id)
        else:
            transaction = Transaction.query.get(transaction_id)
            if not transaction:
                raise NotFoundError("Transaction", transaction_id)
            if transaction.customer_id != customer_id:
                raise ForbiddenError("This transaction is not yours")
            plan = transaction.repayment_plan_ref
        
        # Validate amount
        if amount > transaction.remaining_amount:
            raise BusinessError(
                f"Payment amount ({amount} SAR) exceeds remaining balance "
                f"({transaction.remaining_amount} SAR)"
            )
        
        # Get customer
        customer = Customer.query.get(customer_id)
        
        # Create payment record
        payment = Payment(
            transaction_id=transaction.id,
            customer_id=customer_id,
            amount=amount,
            payment_method=payment_method,
            status="completed"
        )
        
        db.session.add(payment)
        db.session.flush()
        
        # Update transaction
        transaction.record_payment(amount)
        
        # Restore customer balance
        customer.restore_balance(amount)
        
        # Update repayment schedule if exists
        schedule_updated = False
        if plan:
            # Find next pending schedule
            next_schedule = RepaymentSchedule.query.filter_by(
                plan_id=plan.id,
                status="pending"
            ).order_by(RepaymentSchedule.installment_number).first()
            
            if next_schedule and amount >= next_schedule.amount:
                next_schedule.mark_paid(payment.id)
                plan.record_installment_payment(amount)
                schedule_updated = True
        
        # Settlement is now created immediately on purchase acceptance
        # No need to trigger on payment completion
        settlement_triggered = False
        
        db.session.commit()
        
        return payment, transaction, settlement_triggered
    
    # === Helper Methods ===
    
    @staticmethod
    def get_customer_transactions(
        customer_id: int,
        status: str = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Transaction]:
        """Get customer's transactions"""
        query = Transaction.query.filter_by(customer_id=customer_id)
        
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit).all()
    
    @staticmethod
    def get_customer_pending_requests(customer_id: int) -> List[PurchaseRequest]:
        """Get customer's pending purchase requests"""
        return PurchaseRequest.query.filter_by(
            customer_id=customer_id,
            status="pending"
        ).filter(
            PurchaseRequest.expires_at > datetime.utcnow()
        ).order_by(PurchaseRequest.created_at.desc()).all()
    
    @staticmethod
    def get_customer_repayment_plans(
        customer_id: int,
        status: str = None
    ) -> List[RepaymentPlan]:
        """Get customer's repayment plans"""
        query = RepaymentPlan.query.filter_by(customer_id=customer_id)
        
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(RepaymentPlan.created_at.desc()).all()
    
    @staticmethod
    def reject_purchase(customer_id: int, request_id: int, reason: str = None) -> PurchaseRequest:
        """Reject a purchase request"""
        request = PurchaseRequest.query.get(request_id)
        if not request:
            raise NotFoundError("Purchase request", request_id)
        
        if request.customer_id != customer_id:
            raise ForbiddenError("This purchase request is not for you")
        
        if request.status != "pending":
            raise BusinessError(f"Purchase request is already {request.status}")
        
        request.reject(reason)
        db.session.commit()
        
        return request
    
    @staticmethod
    def get_customer_all_requests(
        customer_id: int,
        status: str = None,
        page: int = 1,
        page_size: int = 10
    ) -> Tuple[List[PurchaseRequest], int]:
        """Get all customer's purchase requests with pagination"""
        query = PurchaseRequest.query.filter_by(customer_id=customer_id)
        
        if status and status != "all":
            query = query.filter_by(status=status)
        
        total = query.count()
        items = query.order_by(PurchaseRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return items, total
    
    @staticmethod
    def get_customer_schedules(
        customer_id: int,
        status: str = None,
        page: int = 1,
        page_size: int = 10
    ) -> Tuple[List[RepaymentSchedule], int]:
        """Get customer's repayment schedules with pagination"""
        from app.models import RepaymentPlan
        
        # Get all customer's repayment plans
        plan_ids = db.session.query(RepaymentPlan.id).filter_by(customer_id=customer_id).subquery()
        
        query = RepaymentSchedule.query.filter(RepaymentSchedule.plan_id.in_(plan_ids))
        
        if status and status != "all":
            query = query.filter_by(status=status)
        
        total = query.count()
        items = query.order_by(RepaymentSchedule.due_date.asc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return items, total
