"""
Payment Service
Handles payment processing and related operations
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import func

from app.database import db
from app.models import (
    Payment,
    Transaction,
    Settlement,
    RepaymentPlan,
    RepaymentSchedule,
    Customer
)
from app.utils.response import NotFoundError, BusinessError
from app.config import Config


class PaymentService:
    """Payment processing service"""
    
    @staticmethod
    def get_payment_by_reference(reference: str) -> Payment:
        """Get payment by reference number"""
        payment = Payment.query.filter_by(payment_reference=reference).first()
        if not payment:
            raise NotFoundError("Payment", reference)
        return payment
    
    @staticmethod
    def get_payment_by_id(payment_id: int) -> Payment:
        """Get payment by ID"""
        payment = Payment.query.get(payment_id)
        if not payment:
            raise NotFoundError("Payment", payment_id)
        return payment
    
    @staticmethod
    def get_customer_payments(
        customer_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Payment]:
        """Get customer's payment history"""
        return Payment.query.filter_by(
            customer_id=customer_id
        ).order_by(
            Payment.payment_date.desc()
        ).offset(offset).limit(limit).all()
    
    @staticmethod
    def get_upcoming_payments(customer_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get upcoming payments for a customer
        
        Args:
            customer_id: Customer ID
            days: Number of days to look ahead
        
        Returns:
            List of upcoming payment details
        """
        cutoff_date = datetime.utcnow() + timedelta(days=days)
        
        # Get upcoming schedules
        schedules = RepaymentSchedule.query.join(
            RepaymentPlan
        ).filter(
            RepaymentPlan.customer_id == customer_id,
            RepaymentSchedule.status == "pending",
            RepaymentSchedule.due_date <= cutoff_date
        ).order_by(
            RepaymentSchedule.due_date
        ).all()
        
        upcoming = []
        for schedule in schedules:
            plan = RepaymentPlan.query.get(schedule.plan_id)
            transaction = Transaction.query.get(plan.transaction_id)
            
            upcoming.append({
                "schedule_id": schedule.id,
                "plan_id": plan.id,
                "transaction_id": transaction.id,
                "transaction_number": transaction.transaction_number,
                "installment_number": schedule.installment_number,
                "amount": schedule.amount,
                "due_date": schedule.due_date.isoformat(),
                "is_overdue": schedule.is_overdue
            })
        
        return upcoming
    
    @staticmethod
    def get_overdue_payments(customer_id: int = None) -> List[Dict[str, Any]]:
        """
        Get overdue payments
        
        Args:
            customer_id: Optional customer ID filter
        
        Returns:
            List of overdue payment details
        """
        query = RepaymentSchedule.query.join(
            RepaymentPlan
        ).filter(
            RepaymentSchedule.status == "pending",
            RepaymentSchedule.due_date < datetime.utcnow()
        )
        
        if customer_id:
            query = query.filter(RepaymentPlan.customer_id == customer_id)
        
        schedules = query.order_by(RepaymentSchedule.due_date).all()
        
        overdue = []
        for schedule in schedules:
            plan = RepaymentPlan.query.get(schedule.plan_id)
            transaction = Transaction.query.get(plan.transaction_id)
            customer = Customer.query.get(plan.customer_id)
            
            overdue.append({
                "schedule_id": schedule.id,
                "customer_id": customer.id,
                "transaction_number": transaction.transaction_number,
                "installment_number": schedule.installment_number,
                "amount": schedule.amount,
                "due_date": schedule.due_date.isoformat(),
                "days_overdue": (datetime.utcnow() - schedule.due_date).days
            })
        
        return overdue
    
    @staticmethod
    def calculate_late_status(customer_id: int) -> Dict[str, Any]:
        """
        Calculate customer's late payment status
        Used for risk assessment
        
        Args:
            customer_id: Customer ID
        
        Returns:
            Late payment statistics
        """
        # Get all completed schedules
        total_schedules = RepaymentSchedule.query.join(
            RepaymentPlan
        ).filter(
            RepaymentPlan.customer_id == customer_id,
            RepaymentSchedule.status == "paid"
        ).count()
        
        # Get late payments (paid after due date)
        late_payments = RepaymentSchedule.query.join(
            RepaymentPlan
        ).filter(
            RepaymentPlan.customer_id == customer_id,
            RepaymentSchedule.status == "paid",
            RepaymentSchedule.paid_date > RepaymentSchedule.due_date
        ).count()
        
        # Calculate on-time rate
        on_time_rate = ((total_schedules - late_payments) / total_schedules * 100 
                       if total_schedules > 0 else 100)
        
        return {
            "total_payments": total_schedules,
            "late_payments": late_payments,
            "on_time_payments": total_schedules - late_payments,
            "on_time_rate": round(on_time_rate, 2)
        }
    
    @staticmethod
    def get_platform_revenue(
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict[str, Any]:
        """
        Get platform revenue from commissions
        
        Args:
            start_date: Start date filter
            end_date: End date filter
        
        Returns:
            Revenue statistics
        """
        query = Settlement.query.filter_by(status="completed")
        
        if start_date:
            query = query.filter(Settlement.completed_at >= start_date)
        if end_date:
            query = query.filter(Settlement.completed_at <= end_date)
        
        result = db.session.query(
            func.count(Settlement.id).label('count'),
            func.sum(Settlement.gross_amount).label('gross'),
            func.sum(Settlement.commission_amount).label('commission'),
            func.sum(Settlement.net_amount).label('net_to_merchants')
        ).filter_by(status="completed")
        
        if start_date:
            result = result.filter(Settlement.completed_at >= start_date)
        if end_date:
            result = result.filter(Settlement.completed_at <= end_date)
        
        stats = result.first()
        
        return {
            "total_settlements": stats.count or 0,
            "gross_volume": float(stats.gross or 0),
            "total_commission": float(stats.commission or 0),
            "net_to_merchants": float(stats.net_to_merchants or 0),
            "commission_rate": Config.PLATFORM_COMMISSION_RATE
        }
    
    @staticmethod
    def update_overdue_transactions():
        """
        Batch update overdue transactions
        Called periodically by a scheduled job
        """
        # Find active transactions past due date
        overdue_transactions = Transaction.query.filter(
            Transaction.status == "active",
            Transaction.due_date < datetime.utcnow()
        ).all()
        
        count = 0
        for transaction in overdue_transactions:
            transaction.status = "overdue"
            count += 1
        
        # Update overdue schedules
        overdue_schedules = RepaymentSchedule.query.filter(
            RepaymentSchedule.status == "pending",
            RepaymentSchedule.due_date < datetime.utcnow()
        ).all()
        
        for schedule in overdue_schedules:
            schedule.status = "overdue"
        
        db.session.commit()
        
        return {
            "updated_transactions": count,
            "updated_schedules": len(overdue_schedules)
        }
    
    @staticmethod
    def generate_payment_receipt(payment_id: int) -> Dict[str, Any]:
        """
        Generate a payment receipt
        
        Args:
            payment_id: Payment ID
        
        Returns:
            Receipt data
        """
        payment = Payment.query.get(payment_id)
        if not payment:
            raise NotFoundError("Payment", payment_id)
        
        transaction = Transaction.query.get(payment.transaction_id)
        customer = Customer.query.get(payment.customer_id)
        
        return {
            "receipt_id": payment.payment_reference,
            "payment_id": payment.id,
            "date": payment.payment_date.isoformat(),
            "amount": payment.amount,
            "payment_method": payment.payment_method,
            "status": payment.status,
            "transaction": {
                "id": transaction.id,
                "number": transaction.transaction_number,
                "total_amount": transaction.total_amount,
                "paid_amount": transaction.paid_amount,
                "remaining_amount": transaction.remaining_amount
            },
            "customer_id": customer.id,
            "timestamp": datetime.utcnow().isoformat()
        }
