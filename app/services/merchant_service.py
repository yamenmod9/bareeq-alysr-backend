"""
Merchant Service
Handles merchant operations: send purchase requests, receive settlements
"""
from datetime import datetime
from typing import List, Optional, Tuple

from app.database import db
from app.models import (
    Merchant,
    Branch,
    Customer,
    PurchaseRequest,
    Transaction,
    Settlement
)
from app.utils.response import (
    NotFoundError,
    BusinessError,
    ValidationError,
    ForbiddenError
)
from app.config import Config


class MerchantService:
    """Merchant business logic service"""
    
    # === Send Purchase Request ===
    
    @staticmethod
    def send_purchase_request(
        merchant_id: int,
        customer_id: int,
        product_name: str,
        price: float,
        quantity: int = 1,
        branch_id: int = None,
        product_description: str = None
    ) -> PurchaseRequest:
        """
        Send a purchase request to a customer
        
        Args:
            merchant_id: Merchant ID (from JWT)
            customer_id: Target customer ID
            product_name: Name of the product
            price: Unit price
            quantity: Quantity (default 1)
            branch_id: Optional branch ID
            product_description: Optional description
        
        Returns:
            Created PurchaseRequest
        
        Raises:
            NotFoundError: If customer or branch not found
            BusinessError: If customer cannot afford or merchant inactive
        """
        # Validate merchant
        merchant = Merchant.query.get(merchant_id)
        if not merchant:
            raise NotFoundError("Merchant", merchant_id)
        
        if merchant.status != "active":
            raise BusinessError("Your merchant account is not active")
        
        # Validate customer
        customer = Customer.query.get(customer_id)
        if not customer:
            raise NotFoundError("Customer", customer_id)
        
        if customer.status != "active":
            raise BusinessError("Customer account is not active")
        
        # Calculate total
        total_amount = price * quantity
        
        # Check customer credit limit
        if not customer.can_afford(total_amount):
            raise BusinessError(
                f"Customer does not have enough credit. "
                f"Required: {total_amount} SAR, Available: {customer.available_balance} SAR"
            )
        
        # Validate branch if provided
        if branch_id:
            branch = Branch.query.filter_by(
                id=branch_id,
                merchant_id=merchant_id,
                is_active=True
            ).first()
            if not branch:
                raise NotFoundError("Branch", branch_id)
        
        # Create purchase request
        purchase_request = PurchaseRequest(
            merchant_id=merchant_id,
            customer_id=customer_id,
            branch_id=branch_id,
            product_name=product_name,
            product_description=product_description,
            quantity=quantity,
            unit_price=price,
            total_amount=total_amount
        )
        
        db.session.add(purchase_request)
        db.session.commit()
        
        return purchase_request
    
    # === Receive Settlement ===
    
    @staticmethod
    def create_settlement(transaction_id: int) -> Settlement:
        """
        Create a settlement for a completed transaction
        Platform deducts 0.5% commission
        
        Args:
            transaction_id: Transaction ID
        
        Returns:
            Created Settlement
        
        Raises:
            NotFoundError: If transaction not found
            BusinessError: If transaction not completed or already settled
        """
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            raise NotFoundError("Transaction", transaction_id)
        
        # Check if settlement already exists
        existing = Settlement.query.filter_by(transaction_id=transaction_id).first()
        if existing:
            raise BusinessError("Settlement already exists for this transaction")
        
        # Get merchant
        merchant = Merchant.query.get(transaction.merchant_id)
        if not merchant:
            raise NotFoundError("Merchant", transaction.merchant_id)
        
        # Create settlement
        settlement = Settlement(
            merchant_id=merchant.id,
            transaction_id=transaction_id,
            gross_amount=transaction.total_amount,
            commission_rate=Config.PLATFORM_COMMISSION_RATE,
            # commission_amount and net_amount calculated in __init__
            bank_name=merchant.bank_name,
            bank_account=merchant.bank_account,
            iban=merchant.iban,
            status="completed"  # Auto-complete settlement and add to balance
        )
        
        db.session.add(settlement)
        db.session.flush()  # Get settlement values
        
        # Add net amount to merchant balance (after 0.5% commission deduction)
        merchant.add_to_balance(
            net_amount=settlement.net_amount,
            commission_amount=settlement.commission_amount
        )
        
        db.session.commit()
        
        return settlement
    
    @staticmethod
    def receive_settlement(merchant_id: int, transaction_id: int) -> Settlement:
        """
        Process merchant settlement receipt request
        
        Args:
            merchant_id: Merchant ID (from JWT)
            transaction_id: Transaction ID to settle
        
        Returns:
            Settlement record
        
        Raises:
            ForbiddenError: If transaction not for this merchant
            BusinessError: If transaction not completed
        """
        # Get transaction
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            raise NotFoundError("Transaction", transaction_id)
        
        # Verify ownership
        if transaction.merchant_id != merchant_id:
            raise ForbiddenError("This transaction is not yours")
        
        # Check if already settled
        existing = Settlement.query.filter_by(transaction_id=transaction_id).first()
        if existing:
            return existing  # Return existing settlement
        
        # Check transaction status
        if transaction.status != "completed":
            raise BusinessError(
                f"Transaction is {transaction.status}. "
                f"Only completed transactions can be settled."
            )
        
        # Create settlement
        return MerchantService.create_settlement(transaction_id)
    
    @staticmethod
    def process_settlement(settlement_id: int, bank_reference: str = None) -> Settlement:
        """
        Mark settlement as processed/completed
        In production, this would integrate with payment gateway
        
        Args:
            settlement_id: Settlement ID
            bank_reference: Bank transfer reference
        
        Returns:
            Updated Settlement
        """
        settlement = Settlement.query.get(settlement_id)
        if not settlement:
            raise NotFoundError("Settlement", settlement_id)
        
        if settlement.status == "completed":
            raise BusinessError("Settlement already completed")
        
        settlement.mark_processing()
        # Simulate instant completion for MVP
        settlement.mark_completed(bank_reference or f"BANK-{settlement.id}-AUTO")
        
        db.session.commit()
        
        return settlement
    
    # === Branch Management ===
    
    @staticmethod
    def create_branch(
        merchant_id: int,
        name: str,
        address: str = None,
        city: str = None,
        phone: str = None
    ) -> Branch:
        """Create a new branch for merchant"""
        merchant = Merchant.query.get(merchant_id)
        if not merchant:
            raise NotFoundError("Merchant", merchant_id)
        
        branch = Branch(
            merchant_id=merchant_id,
            name=name,
            address=address,
            city=city,
            phone=phone,
            is_active=True
        )
        
        db.session.add(branch)
        db.session.commit()
        
        return branch
    
    @staticmethod
    def get_merchant_branches(merchant_id: int, active_only: bool = True) -> List[Branch]:
        """Get merchant's branches"""
        query = Branch.query.filter_by(merchant_id=merchant_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.all()
    
    # === Helper Methods ===
    
    @staticmethod
    def get_merchant_transactions(
        merchant_id: int,
        status: str = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Transaction]:
        """Get merchant's transactions"""
        query = Transaction.query.filter_by(merchant_id=merchant_id)
        
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit).all()
    
    @staticmethod
    def get_merchant_settlements(
        merchant_id: int,
        status: str = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Settlement]:
        """Get merchant's settlements"""
        query = Settlement.query.filter_by(merchant_id=merchant_id)
        
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(Settlement.created_at.desc()).offset(offset).limit(limit).all()
    
    @staticmethod
    def get_merchant_pending_requests(merchant_id: int) -> List[PurchaseRequest]:
        """Get merchant's pending purchase requests"""
        return PurchaseRequest.query.filter_by(
            merchant_id=merchant_id,
            status="pending"
        ).filter(
            PurchaseRequest.expires_at > datetime.utcnow()
        ).order_by(PurchaseRequest.created_at.desc()).all()
    
    @staticmethod
    def get_merchant_all_requests(merchant_id: int, status_filter: str = None) -> List[PurchaseRequest]:
        """Get all merchant's purchase requests with optional status filter"""
        query = PurchaseRequest.query.filter_by(merchant_id=merchant_id)
        
        if status_filter:
            query = query.filter_by(status=status_filter)
        
        return query.order_by(PurchaseRequest.created_at.desc()).all()
    
    @staticmethod
    def get_merchant_stats(merchant_id: int) -> dict:
        """Get merchant statistics"""
        merchant = Merchant.query.get(merchant_id)
        if not merchant:
            raise NotFoundError("Merchant", merchant_id)
        
        # Count transactions by status
        active_count = Transaction.query.filter_by(
            merchant_id=merchant_id,
            status="active"
        ).count()
        
        completed_count = Transaction.query.filter_by(
            merchant_id=merchant_id,
            status="completed"
        ).count()
        
        # Sum settlements
        from sqlalchemy import func, extract
        from datetime import datetime
        
        # Total income from purchase settlements
        total_income = db.session.query(
            func.sum(Settlement.net_amount)
        ).filter_by(
            merchant_id=merchant_id,
            settlement_type="income",
            status="completed"
        ).scalar() or 0
        
        # Total withdrawn
        total_withdrawn = db.session.query(
            func.sum(Settlement.net_amount)
        ).filter_by(
            merchant_id=merchant_id,
            settlement_type="withdrawal",
            status="completed"
        ).scalar() or 0
        
        # This month withdrawals
        current_month = datetime.utcnow().month
        current_year = datetime.utcnow().year
        this_month_withdrawn = db.session.query(
            func.sum(Settlement.net_amount)
        ).filter(
            Settlement.merchant_id == merchant_id,
            Settlement.settlement_type == "withdrawal",
            Settlement.status == "completed",
            extract('month', Settlement.created_at) == current_month,
            extract('year', Settlement.created_at) == current_year
        ).scalar() or 0
        
        return {
            "total_transactions": merchant.total_transactions,
            "total_volume": merchant.total_volume,
            "total_sales": merchant.total_volume,  # Alias for frontend
            "active_transactions": active_count,
            "completed_transactions": completed_count,
            "total_income": total_income,
            "total_settled": total_withdrawn,  # Total withdrawn by merchant
            "this_month_settled": this_month_withdrawn,
            "balance": merchant.balance,
            "total_commission_paid": merchant.total_commission_paid
        }
    
    @staticmethod
    def cancel_purchase_request(merchant_id: int, request_id: int) -> PurchaseRequest:
        """Cancel a pending purchase request"""
        request = PurchaseRequest.query.get(request_id)
        if not request:
            raise NotFoundError("Purchase request", request_id)
        
        if request.merchant_id != merchant_id:
            raise ForbiddenError("This purchase request is not yours")
        
        if request.status != "pending":
            raise BusinessError(f"Purchase request is already {request.status}")
        
        request.status = "cancelled"
        db.session.commit()
        
        return request
    
    @staticmethod
    def request_withdrawal(
        merchant_id: int,
        amount: float,
        bank_name: str,
        bank_account: str,
        iban: str
    ) -> dict:
        """
        Request withdrawal from merchant balance
        
        Args:
            merchant_id: Merchant ID
            amount: Amount to withdraw
            bank_name: Bank name
            bank_account: Bank account number
            iban: IBAN
        
        Returns:
            Withdrawal details
        """
        merchant = Merchant.query.get(merchant_id)
        if not merchant:
            raise NotFoundError("Merchant", merchant_id)
        
        if amount <= 0:
            raise BusinessError("Withdrawal amount must be positive")
        
        if amount > merchant.balance:
            raise BusinessError(f"Insufficient balance. Available: {merchant.balance} SAR")
        
        # Update merchant bank details
        merchant.bank_name = bank_name
        merchant.bank_account = bank_account
        merchant.iban = iban
        
        # Deduct from balance
        merchant.balance -= amount
        
        # Create withdrawal settlement record
        withdrawal = Settlement(
            merchant_id=merchant_id,
            transaction_id=None,  # No transaction for direct withdrawal
            settlement_type="withdrawal",
            gross_amount=amount,
            commission_rate=0,  # No commission on withdrawals
            commission_amount=0,
            net_amount=amount,
            status="completed",
            bank_name=bank_name,
            bank_account=bank_account,
            iban=iban,
            notes=f"Withdrawal request to {bank_name}"
        )
        db.session.add(withdrawal)
        
        db.session.commit()
        
        return {
            "withdrawn_amount": amount,
            "remaining_balance": merchant.balance,
            "bank_name": bank_name,
            "iban": iban,
            "settlement_reference": withdrawal.settlement_reference,
            "message": "Withdrawal request processed successfully"
        }
