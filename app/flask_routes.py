"""
Flask API Routes
Provides active API endpoints for the Flask runtime
"""
from flask import Blueprint, jsonify, request
from functools import wraps
from datetime import datetime

from app.database import db
from app.services.auth_service import AuthService
from app.services.customer_service import CustomerService
from app.services.merchant_service import MerchantService
from app.utils.auth import TokenInfo, create_access_token, verify_token
from app.config import Config

# Create blueprint for API routes
api = Blueprint('api', __name__)


def _pagination_params():
    """Read safe pagination query params."""
    page = max(int(request.args.get('page', 1)), 1)
    page_size = min(max(int(request.args.get('page_size', 20)), 1), 100)
    return page, page_size


def _resolve_customer_by_code(customer_code):
    """Resolve customer and user by customer code only."""
    from app.models import Customer, User

    normalized_code = (customer_code or '').strip().upper()
    if not normalized_code:
        return None, None

    if len(normalized_code) != 8 or not normalized_code.isalnum():
        return None, None

    customer = Customer.query.filter_by(customer_code=normalized_code).first()
    if not customer:
        return None, None

    customer_user = db.session.get(User, customer.user_id)

    return customer, customer_user


def get_current_user_flask():
    """Get current user from JWT token in request headers"""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    try:
        payload = verify_token(token)
        from app.models import User
        return db.session.get(User, payload.get('sub'))
    except Exception:
        return None


def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user_flask()
        if not user:
            return jsonify({
                "success": False,
                "error": "UNAUTHORIZED",
                "message": "Authentication required"
            }), 401
        return f(user, *args, **kwargs)
    return decorated


def require_role(*roles):
    """Decorator to require specific role(s)"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user_flask()
            if not user:
                return jsonify({
                    "success": False,
                    "error": "UNAUTHORIZED",
                    "message": "Authentication required"
                }), 401
            if user.role not in roles:
                return jsonify({
                    "success": False,
                    "error": "FORBIDDEN",
                    "message": "Insufficient permissions"
                }), 403
            return f(user, *args, **kwargs)
        return decorated
    return decorator


# === Auth Routes ===

@api.route('/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    national_id = data.get('national_id')
    
    try:
        user, token = AuthService.authenticate(
            email=email,
            password=password,
            national_id=national_id
        )
        
        return jsonify({
            "success": True,
            "data": {
                "access_token": token,
                "token_type": "bearer",
                "expires_in": TokenInfo.get_expiry_seconds(),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "phone": user.phone,
                    "role": user.role,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified
                }
            },
            "message": "Login successful"
        })
    except Exception as e:
        error_message = str(e)
        if "Invalid email or password" in error_message:
            user_message = "The email or password is incorrect."
        elif "Account is deactivated" in error_message:
            user_message = "This account is deactivated."
        elif "National ID does not match" in error_message:
            user_message = "National ID does not match our records."
        else:
            user_message = error_message
        return jsonify({
            "success": False,
            "error": "AUTH_ERROR",
            "message": user_message
        }), 401


@api.route('/auth/register', methods=['POST'])
def register():
    """User registration endpoint"""
    data = request.get_json() or {}
    
    try:
        role = data.get('role', 'customer')
        if role == 'merchant':
            user, _merchant = AuthService.register_merchant(
                email=data.get('email'),
                password=data.get('password'),
                full_name=data.get('full_name'),
                shop_name=data.get('shop_name') or data.get('full_name') or 'Merchant Shop',
                phone=data.get('phone'),
                national_id=data.get('national_id')
            )
        else:
            user, _customer = AuthService.register_customer(
                email=data.get('email'),
                password=data.get('password'),
                full_name=data.get('full_name'),
                phone=data.get('phone'),
                national_id=data.get('national_id')
            )
        
        # Generate token
        token = create_access_token(user.id, email=user.email, role=user.role)
        
        return jsonify({
            "success": True,
            "data": {
                "access_token": token,
                "token_type": "bearer",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role
                }
            },
            "message": "Registration successful"
        }), 201
    except Exception as e:
        error_message = str(e)
        if "Email already registered" in error_message:
            user_message = "This email is already registered."
        elif "National ID already registered" in error_message:
            user_message = "This national ID is already registered."
        elif "Missing required field" in error_message:
            user_message = "Please fill in all required fields."
        else:
            user_message = error_message
        return jsonify({
            "success": False,
            "error": "REGISTRATION_ERROR",
            "message": user_message
        }), 400


@api.route('/auth/me', methods=['GET'])
@require_auth
def get_me(user):
    """Get current user profile"""
    return jsonify({
        "success": True,
        "data": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": user.role,
            "is_active": user.is_active,
            "is_verified": user.is_verified
        },
        "message": "Profile retrieved"
    })


@api.route('/auth/profile', methods=['PATCH'])
@require_auth
def update_profile(user):
    """Update authenticated user profile."""
    data = request.get_json() or {}
    try:
        updated = AuthService.update_profile(
            user_id=user.id,
            full_name=data.get('full_name'),
            phone=data.get('phone'),
            email=data.get('email'),
        )
        return jsonify({
            "success": True,
            "data": {
                "id": updated.id,
                "email": updated.email,
                "full_name": updated.full_name,
                "phone": updated.phone,
                "role": updated.role,
            },
            "message": "Profile updated"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "PROFILE_UPDATE_ERROR",
            "message": str(e)
        }), 400


@api.route('/auth/change-password', methods=['POST'])
@require_auth
def change_password(user):
    """Change account password."""
    data = request.get_json() or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    if len(new_password) < 8:
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": "New password must be at least 8 characters"
        }), 400

    try:
        AuthService.change_password(user.id, old_password, new_password)
        return jsonify({
            "success": True,
            "data": {"changed": True},
            "message": "Password changed"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "CHANGE_PASSWORD_ERROR",
            "message": str(e)
        }), 400


@api.route('/auth/verify-nafath', methods=['POST'])
@require_auth
def verify_nafath(user):
    """Simulate Nafath verification."""
    data = request.get_json() or {}
    national_id = (data.get('national_id') or '').strip()
    if len(national_id) != 10 or not national_id.isdigit():
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": "National ID must be 10 digits"
        }), 400
    try:
        AuthService.simulate_nafath_verification(user.id, national_id)
        refreshed_user = AuthService.get_user_by_id(user.id)
        return jsonify({
            "success": True,
            "data": {
                "nafath_verified": refreshed_user.nafath_verified,
                "is_verified": refreshed_user.is_verified,
                "national_id": refreshed_user.national_id,
            },
            "message": "Nafath verification successful"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "NAFATH_VERIFICATION_ERROR",
            "message": str(e)
        }), 400


@api.route('/auth/2fa', methods=['POST'])
@require_auth
def configure_2fa(user):
    """Enable/disable simulated 2FA."""
    data = request.get_json() or {}
    enabled = bool(data.get('enabled', True))
    user.two_factor_enabled = enabled
    db.session.commit()
    return jsonify({
        "success": True,
        "data": {
            "two_factor_enabled": user.two_factor_enabled,
        },
        "message": "2FA preferences updated"
    })


# === Customer Routes ===

@api.route('/customers/me/dashboard', methods=['GET'])
@require_role('customer')
def customer_dashboard(user):
    """Get customer dashboard data"""
    from app.models import Customer, Transaction, Payment
    from sqlalchemy import func
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({
            "success": False,
            "error": "NOT_FOUND",
            "message": "Customer profile not found"
        }), 404
    
    # Get statistics
    total_transactions = Transaction.query.filter_by(customer_id=customer.id).count()
    active_transactions = Transaction.query.filter_by(
        customer_id=customer.id, 
        status='active'
    ).count()
    
    total_paid = db.session.query(func.sum(Payment.amount)).filter(
        Payment.transaction_id.in_(
            db.session.query(Transaction.id).filter_by(customer_id=customer.id)
        )
    ).scalar() or 0
    
    outstanding_balance = db.session.query(func.sum(Transaction.remaining_amount)).filter(
        Transaction.customer_id == customer.id,
        Transaction.status == 'active'
    ).scalar() or 0
    
    return jsonify({
        "success": True,
        "data": {
            "credit_limit": float(customer.credit_limit),
            "available_balance": float(customer.available_balance),
            "used_credit": float(customer.credit_limit - customer.available_balance),
            "total_transactions": total_transactions,
            "active_transactions": active_transactions,
            "total_paid": float(total_paid),
            "outstanding_balance": float(outstanding_balance),
            "status": customer.status
        },
        "message": "Dashboard data retrieved"
    })


@api.route('/customers/me/transactions', methods=['GET'])
@require_role('customer')
def customer_transactions(user):
    """Get customer transactions"""
    from app.models import Customer, Transaction, Merchant
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({
            "success": False,
            "error": "NOT_FOUND",
            "message": "Customer profile not found"
        }), 404
    
    # Get transactions with pagination
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 10))
    
    transactions = Transaction.query.filter_by(customer_id=customer.id)\
        .order_by(Transaction.created_at.desc())\
        .offset((page-1)*page_size).limit(page_size).all()
    
    return jsonify({
        "success": True,
        "data": [
            {
                "id": txn.id,
                "amount": float(txn.total_amount),
                "status": txn.status,
                "merchant_name": txn.merchant.shop_name if txn.merchant else "Unknown",
                "created_at": txn.created_at.isoformat() if txn.created_at else None
            }
            for txn in transactions
        ],
        "message": "Transactions retrieved"
    })


# Additional endpoints expected by frontend
@api.route('/customers/me', methods=['GET'])
@require_role('customer')
def customer_profile(user):
    """Get customer profile"""
    from app.models import Customer
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({
            "success": False,
            "error": "NOT_FOUND",
            "message": "Customer profile not found"
        }), 404
    
    return jsonify({
        "success": True,
        "data": {
            "id": customer.id,
            "user_id": customer.user_id,
            "customer_code": customer.customer_code,
            "credit_limit": float(customer.credit_limit),
            "available_balance": float(customer.available_balance),
            "outstanding_balance": float(customer.outstanding_balance),
            "status": customer.status,
            "user": {
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone
            }
        },
        "message": "Customer profile retrieved"
    })


@api.route('/customers/me/regenerate-code', methods=['POST'])
@require_role('customer')
def customer_regenerate_code(user):
    """Regenerate customer unique code for merchant lookup."""
    from app.models import Customer

    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({
            "success": False,
            "error": "NOT_FOUND",
            "message": "Customer profile not found"
        }), 404

    old_code = customer.customer_code
    try:
        new_code = customer.regenerate_customer_code()
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": "CODE_REGENERATION_FAILED",
            "message": "Could not regenerate customer code"
        }), 500

    return jsonify({
        "success": True,
        "data": {
            "old_customer_code": old_code,
            "customer_code": new_code
        },
        "message": "Customer code regenerated successfully"
    })


@api.route('/customers/pending-requests', methods=['GET'])
@require_role('customer')
def customer_pending_requests(user):
    """Get customer pending requests"""
    return jsonify({
        "success": True,
        "data": [],
        "message": "Pending requests retrieved"
    })


@api.route('/customers/limit-history', methods=['GET'])
@require_role('customer')
def customer_limit_history(user):
    """Get customer limit history"""
    return jsonify({
        "success": True,
        "data": [],
        "message": "Limit history retrieved"
    })


@api.route('/customers/limits', methods=['GET'])
@require_role('customer')
def customer_limits(user):
    """Get customer credit limits"""
    from app.models import Customer
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({
            "success": False,
            "error": "NOT_FOUND",
            "message": "Customer profile not found"
        }), 404
    
    return jsonify({
        "success": True,
        "data": {
            "credit_limit": float(customer.credit_limit),
            "available_balance": float(customer.available_balance),
            "used_credit": float(customer.credit_limit - customer.available_balance),
            "outstanding_balance": float(customer.outstanding_balance),
            "status": customer.status
        },
        "message": "Customer limits retrieved"
    })


@api.route('/customers/requests', methods=['GET'])
@require_role('customer')
def customer_requests(user):
    """Get customer purchase requests"""
    from app.models import Customer, PurchaseRequest, Merchant
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({
            "success": False,
            "error": "NOT_FOUND", 
            "message": "Customer profile not found"
        }), 404
    
    # Get query parameters
    status = request.args.get('status', 'all')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 10))
    
    # Build query
    query = PurchaseRequest.query.filter_by(customer_id=customer.id)
    if status != 'all':
        query = query.filter_by(status=status)
    
    # Paginate
    requests = query.order_by(PurchaseRequest.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    
    data = []
    for req in requests:
        try:
            # Safely get merchant name
            merchant_name = "Unknown"
            if hasattr(req, 'merchant') and req.merchant:
                merchant_name = getattr(req.merchant, 'shop_name', 'Unknown')
            
            # Safely get amount
            amount = 0.0
            if hasattr(req, 'total_amount') and req.total_amount:
                amount = float(req.total_amount)
            elif hasattr(req, 'amount') and req.amount:
                amount = float(req.amount)
            
            data.append({
                "id": req.id,
                "amount": amount,
                "status": getattr(req, 'status', 'unknown'),
                "merchant_name": merchant_name,
                "created_at": req.created_at.isoformat() if req.created_at else None
            })
        except Exception as e:
            # Skip this request if there are any errors
            continue
    
    return jsonify({
        "success": True,
        "data": data,
        "message": "Purchase requests retrieved"
    })


@api.route('/customers/schedules', methods=['GET'])
@require_role('customer')
def customer_schedules(user):
    """Get customer repayment schedules"""
    from app.models import Customer
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({
            "success": False,
            "error": "NOT_FOUND",
            "message": "Customer profile not found"
        }), 404
    
    # Get query parameters
    status = request.args.get('status', 'all')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 10))
    
    # For now, return empty schedules to avoid SQLAlchemy join errors
    # TODO: Implement proper repayment schedule functionality
    data = []
    
    return jsonify({
        "success": True,
        "data": data,
        "message": "Repayment schedules retrieved"
    })


# Additional customer endpoints that frontend expects

@api.route('/customers/my-transactions', methods=['GET'])
@require_role('customer')
def customer_my_transactions(user):
    """Get customer transactions (alias for /customers/me/transactions)"""
    from app.models import Customer, Transaction
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    
    transactions = Transaction.query.filter_by(customer_id=customer.id).order_by(
        Transaction.created_at.desc()
    ).limit(50).all()
    
    result = []
    for t in transactions:
        result.append({
            "id": t.id,
            "merchant_name": "Sample Merchant",
            "amount": float(t.total_amount),
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "created_at": t.created_at.isoformat() if t.created_at else None
        })
    
    return jsonify({
        "success": True,
        "data": result,
        "message": "Transactions retrieved"
    })


@api.route('/customers/upcoming-payments', methods=['GET'])
@require_role('customer')
def customer_upcoming_payments(user):
    """Get customer upcoming payments"""
    from app.models import Customer, Payment, Transaction
    from datetime import datetime, timedelta
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    
    # Simplified query - get payments from customer's transactions
    future_date = datetime.utcnow() + timedelta(days=30)
    
    try:
        # Get customer transactions first, then their payments
        customer_transactions = Transaction.query.filter_by(customer_id=customer.id).all()
        transaction_ids = [t.id for t in customer_transactions]
        
        if not transaction_ids:
            return jsonify({
                "success": True,
                "data": [],
                "message": "No upcoming payments found"
            })
        
        payments = Payment.query.filter(
            Payment.transaction_id.in_(transaction_ids),
            Payment.payment_date >= datetime.utcnow(),
            Payment.payment_date <= future_date,
            Payment.status.in_(['pending', 'overdue'])
        ).order_by(Payment.payment_date.asc()).limit(20).all()
        
        result = []
        for p in payments:
            result.append({
                "id": p.id,
                "amount": float(p.amount),
                "due_date": p.payment_date.isoformat() if p.payment_date else None,
                "status": p.status,
                "transaction_id": p.transaction_id
            })
        
    except Exception as e:
        # If there's still an error, return empty data
        result = []
    
    return jsonify({
        "success": True,
        "data": result,
        "message": "Upcoming payments retrieved"
    })


@api.route('/customers/repayment-plans', methods=['GET'])
@require_role('customer')
def customer_repayment_plans(user):
    """Get customer repayment plans"""
    from app.models import Customer, Transaction, Payment
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    
    # Get active transactions with their payment schedules
    transactions = Transaction.query.filter_by(
        customer_id=customer.id,
        status='active'
    ).limit(20).all()
    
    result = []
    for t in transactions:
        payments = Payment.query.filter_by(transaction_id=t.id).order_by(Payment.payment_date.asc()).all()
        
        payment_schedule = []
        for p in payments:
            payment_schedule.append({
                "id": p.id,
                "amount": float(p.amount),
                "due_date": p.payment_date.isoformat() if p.payment_date else None,
                "status": p.status
            })
        
        result.append({
            "transaction_id": t.id,
            "total_amount": float(t.total_amount),
            "remaining_balance": float(t.remaining_amount),
            "status": t.status,
            "payment_schedule": payment_schedule,
            "created_at": t.created_at.isoformat() if t.created_at else None
        })
    
    return jsonify({
        "success": True,
        "data": result,
        "message": "Repayment plans retrieved"
    })


@api.route('/customers/transactions', methods=['GET'])
@require_role('customer')
def customer_transactions_filtered(user):
    """Get customer transactions with filtering"""
    from app.models import Customer, Transaction
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    
    # Get query parameters
    status = request.args.get('status', 'all')
    page = int(request.args.get('page', 1))
    page_size = min(int(request.args.get('page_size', 10)), 100)
    
    # Build query
    query = Transaction.query.filter_by(customer_id=customer.id)
    
    if status and status != 'all':
        query = query.filter(Transaction.status == status)
    
    # Order and paginate
    transactions = query.order_by(Transaction.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    result = []
    for t in transactions:
        result.append({
            "id": t.id,
            "merchant_name": "Sample Merchant",
            "amount": float(t.total_amount),
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "created_at": t.created_at.isoformat() if t.created_at else None
        })
    
    return jsonify({
        "success": True,
        "data": result,
        "message": "Transactions retrieved",
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": query.count()
        }
    })


@api.route('/merchants/stats', methods=['GET'])
@require_role('merchant')
def merchant_stats(user):
    """Get merchant statistics"""
    return jsonify({
        "success": True,
        "data": {
            "total_transactions": 0,
            "total_revenue": 0.0,
            "pending_settlements": 0.0,
            "completed_settlements": 0.0
        },
        "message": "Merchant stats retrieved"
    })


@api.route('/merchants/branches', methods=['GET'])
@require_role('merchant')
def merchant_branches(user):
    """Get merchant branches"""
    return jsonify({
        "success": True,
        "data": [],
        "message": "Branches retrieved"
    })


# === Merchant Routes ===

@api.route('/merchants/me/dashboard', methods=['GET'])
@require_role('merchant')
def merchant_dashboard(user):
    """Get merchant dashboard data"""
    from app.models import Merchant, Transaction, Settlement
    from sqlalchemy import func
    
    merchant = Merchant.query.filter_by(user_id=user.id).first()
    if not merchant:
        return jsonify({
            "success": False,
            "error": "NOT_FOUND",
            "message": "Merchant profile not found"
        }), 404
    
    # Get statistics
    total_transactions = Transaction.query.filter_by(merchant_id=merchant.id).count()
    
    total_sales = db.session.query(func.sum(Transaction.total_amount)).filter(
        Transaction.merchant_id == merchant.id
    ).scalar() or 0
    
    total_settled = db.session.query(func.sum(Settlement.net_amount)).filter(
        Settlement.merchant_id == merchant.id,
        Settlement.status == 'completed'
    ).scalar() or 0
    
    pending_settlement = db.session.query(func.sum(Settlement.net_amount)).filter(
        Settlement.merchant_id == merchant.id,
        Settlement.status == 'pending'
    ).scalar() or 0
    
    return jsonify({
        "success": True,
        "data": {
            "total_sales": float(total_sales),
            "total_transactions": total_transactions,
            "total_settled": float(total_settled),
            "pending_settlement": float(pending_settlement),
            "commission_rate": Config.PLATFORM_COMMISSION_RATE * 100,
            "status": merchant.status,
            "is_verified": merchant.is_verified
        },
        "message": "Dashboard data retrieved"
    })


@api.route('/merchants/me/transactions', methods=['GET'])
@require_role('merchant')
def merchant_transactions(user):
    """Get merchant transactions"""
    from app.models import Merchant, Transaction, Customer, User
    
    merchant = Merchant.query.filter_by(user_id=user.id).first()
    if not merchant:
        return jsonify({"success": False, "message": "Merchant not found"}), 404
    
    transactions = Transaction.query.filter_by(merchant_id=merchant.id).order_by(
        Transaction.created_at.desc()
    ).limit(50).all()
    
    result = []
    for t in transactions:
        customer = db.session.get(Customer, t.customer_id)
        customer_user = db.session.get(User, customer.user_id) if customer else None
        result.append({
            "id": t.id,
            "transaction_number": t.transaction_number,
            "amount": float(t.total_amount),
            "remaining_amount": float(t.remaining_amount),
            "status": t.status,
            "customer_name": customer_user.full_name if customer_user else "Unknown",
            "created_at": t.created_at.isoformat() if t.created_at else None
        })
    
    return jsonify({
        "success": True,
        "data": result,
        "message": "Transactions retrieved"
    })


@api.route('/merchants/me/settlements', methods=['GET'])
@require_role('merchant')
def merchant_settlements(user):
    """Get merchant settlements"""
    from app.models import Merchant, Settlement
    
    merchant = Merchant.query.filter_by(user_id=user.id).first()
    if not merchant:
        return jsonify({"success": False, "message": "Merchant not found"}), 404
    
    settlements = Settlement.query.filter_by(merchant_id=merchant.id).order_by(
        Settlement.created_at.desc()
    ).limit(50).all()
    
    result = []
    for s in settlements:
        result.append({
            "id": s.id,
            "gross_amount": float(s.gross_amount),
            "commission_amount": float(s.commission_amount),
            "net_amount": float(s.net_amount),
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "settled_at": s.completed_at.isoformat() if s.completed_at else None
        })
    
    return jsonify({
        "success": True,
        "data": result,
        "message": "Settlements retrieved"
    })


# Additional merchant endpoints that frontend expects

@api.route('/merchants/transactions', methods=['GET'])
@require_role('merchant')
def merchant_transactions_paginated(user):
    """Get merchant transactions with pagination (frontend endpoint)"""
    from app.models import Merchant, Transaction, Customer, User
    
    merchant = Merchant.query.filter_by(user_id=user.id).first()
    if not merchant:
        return jsonify({"success": False, "message": "Merchant not found"}), 404
    
    # Get query parameters
    page = int(request.args.get('page', 1))
    page_size = min(int(request.args.get('page_size', 10)), 100)
    
    # Get transactions with pagination
    transactions = Transaction.query.filter_by(merchant_id=merchant.id).order_by(
        Transaction.created_at.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()
    
    result = []
    for t in transactions:
        customer = db.session.get(Customer, t.customer_id)
        customer_user = db.session.get(User, customer.user_id) if customer else None
        
        result.append({
            "id": t.id,
            "customer_name": customer_user.full_name if customer_user else "Unknown",
            "amount": float(t.total_amount),
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "created_at": t.created_at.isoformat() if t.created_at else None
        })
    
    return jsonify({
        "success": True,
        "data": result,
        "message": "Transactions retrieved",
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": Transaction.query.filter_by(merchant_id=merchant.id).count()
        }
    })


@api.route('/merchants/settlements', methods=['GET'])
@require_role('merchant')
def merchant_settlements_filtered(user):
    """Get merchant settlements with filtering (frontend endpoint)"""
    from app.models import Merchant, Settlement
    
    merchant = Merchant.query.filter_by(user_id=user.id).first()
    if not merchant:
        return jsonify({"success": False, "message": "Merchant not found"}), 404
    
    # Get query parameters
    status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    page = int(request.args.get('page', 1))
    page_size = min(int(request.args.get('page_size', 10)), 100)
    
    # Build query
    query = Settlement.query.filter_by(merchant_id=merchant.id)
    
    if status:
        query = query.filter(Settlement.status == status)
    
    # Get settlements with pagination
    settlements = query.order_by(Settlement.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    result = []
    for s in settlements:
        result.append({
            "id": s.id,
            "gross_amount": float(s.gross_amount),
            "commission_amount": float(s.commission_amount),
            "net_amount": float(s.net_amount),
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "settled_at": s.completed_at.isoformat() if s.completed_at else None
        })
    
    return jsonify({
        "success": True,
        "data": result,
        "message": "Settlements retrieved",
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": query.count()
        }
    })


@api.route('/merchants/me', methods=['GET'])
@require_role('merchant')
def merchant_profile(user):
    """Get merchant profile"""
    from app.models import Merchant
    
    merchant = Merchant.query.filter_by(user_id=user.id).first()
    if not merchant:
        return jsonify({"success": False, "message": "Merchant not found"}), 404
    
    return jsonify({
        "success": True,
        "data": {
            "id": merchant.id,
            "shop_name": merchant.shop_name,
            "shop_name_ar": merchant.shop_name_ar,
            "address": merchant.address,
            "city": merchant.city,
            "business_phone": merchant.business_phone,
            "business_email": merchant.business_email,
            "commercial_registration": merchant.commercial_registration,
            "vat_number": merchant.vat_number,
            "status": merchant.status,
            "is_verified": merchant.is_verified,
            "total_transactions": merchant.total_transactions,
            "total_volume": float(merchant.total_volume or 0),
            "balance": float(merchant.balance or 0),
            "created_at": merchant.created_at.isoformat() if merchant.created_at else None
        },
        "message": "Merchant profile retrieved"
    })


@api.route('/merchants/lookup-customer/<customer_code>', methods=['GET'])
@require_role('merchant')
def lookup_customer(user, customer_code):
    """Look up customer by customer code"""
    customer, customer_user = _resolve_customer_by_code(customer_code)
    
    if not customer or not customer_user:
        return jsonify({
            "success": False,
            "message": "Customer not found"
        }), 404
    
    return jsonify({
        "success": True,
        "data": {
            "id": customer.id,
            "customer_code": customer.customer_code,
            "full_name": customer_user.full_name,
            "phone": customer_user.phone,
            "email": customer_user.email,
            "available_balance": float(customer.available_balance or 0),
            "credit_limit": float(customer.credit_limit or 0),
            "outstanding_balance": float(customer.outstanding_balance or 0),
            "status": customer.status
        },
        "message": "Customer found"
    })


@api.route('/merchants/purchase-requests', methods=['GET'])
@require_role('merchant')
def merchant_purchase_requests_list(user):
    """Get merchant purchase requests (GET endpoint)"""
    from app.models import Merchant, PurchaseRequest, Customer, User
    
    merchant = Merchant.query.filter_by(user_id=user.id).first()
    if not merchant:
        return jsonify({"success": False, "message": "Merchant not found"}), 404
    
    requests = PurchaseRequest.query.filter_by(merchant_id=merchant.id).order_by(
        PurchaseRequest.created_at.desc()
    ).limit(50).all()
    
    result = []
    for r in requests:
        customer = db.session.get(Customer, r.customer_id)
        customer_user = db.session.get(User, customer.user_id) if customer else None
        
        result.append({
            "id": r.id,
            "request_number": r.reference_number,
            "customer_name": customer_user.full_name if customer_user else "Unknown",
            "amount": float(r.total_amount),
            "description": r.product_description,
            "status": r.status,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    
    return jsonify({
        "success": True,
        "data": result,
        "message": "Purchase requests retrieved"
    })


# === Purchase Request Routes ===

@api.route('/merchants/purchase-requests', methods=['POST'])
@require_role('merchant')
def create_purchase_request(user):
    """Create a new purchase request"""
    from app.models import Merchant, PurchaseRequest
    from datetime import datetime, timedelta
    import uuid
    
    data = request.get_json() or {}
    merchant = Merchant.query.filter_by(user_id=user.id).first()
    
    if not merchant:
        return jsonify({"success": False, "message": "Merchant not found"}), 404
    
    customer_code = data.get('customer_code')
    if not customer_code:
        return jsonify({"success": False, "message": "customer_code is required"}), 400

    customer, customer_user = _resolve_customer_by_code(customer_code)

    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    
    amount = float(data.get('amount', 0))
    
    # Check customer balance
    if amount > customer.available_balance:
        return jsonify({
            "success": False, 
            "message": f"Insufficient balance. Available: {customer.available_balance} SAR"
        }), 400
    
    # Create purchase request
    pr = PurchaseRequest(
        merchant_id=merchant.id,
        customer_id=customer.id,
        product_name=data.get('product_name') or 'Purchase',
        product_description=data.get('description', ''),
        quantity=int(data.get('quantity', 1)),
        unit_price=amount,
        total_amount=amount,
        status='pending',
        expires_at=datetime.utcnow() + timedelta(hours=Config.PURCHASE_REQUEST_EXPIRY_HOURS)
    )
    
    db.session.add(pr)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "data": {
            "id": pr.id,
            "request_number": pr.reference_number,
            "amount": float(pr.total_amount),
            "status": pr.status,
            "customer_name": customer_user.full_name,
            "customer_code": customer.customer_code,
            "expires_at": pr.expires_at.isoformat()
        },
        "message": "Purchase request created"
    }), 201


@api.route('/merchants/send-purchase-request', methods=['POST'])
@require_role('merchant')
def send_purchase_request(user):
    """Send purchase request (alternative endpoint for frontend)"""
    from app.models import Merchant, Customer, User, PurchaseRequest
    from datetime import datetime, timedelta
    import uuid
    
    data = request.get_json() or {}
    merchant = Merchant.query.filter_by(user_id=user.id).first()
    
    if not merchant:
        return jsonify({"success": False, "message": "Merchant not found"}), 404
    
    # Preferred input is customer_id from lookup. customer_code is accepted as fallback.
    customer_id = data.get('customer_id')
    if not customer_id:
        customer_code = data.get('customer_code')
        if customer_code:
            customer, _customer_user = _resolve_customer_by_code(customer_code)
            customer_id = customer.id if customer else None
        
        if not customer_id:
            return jsonify({"success": False, "message": "Customer not found"}), 404
    
    customer = db.session.get(Customer, customer_id)
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    
    customer_user = db.session.get(User, customer.user_id)
    amount = float(data.get('amount', 0))
    
    # Check customer balance
    if amount > customer.available_balance:
        return jsonify({
            "success": False, 
            "message": f"Insufficient balance. Available: {customer.available_balance} SAR"
        }), 400
    
    # Create purchase request
    pr = PurchaseRequest(
        merchant_id=merchant.id,
        customer_id=customer.id,
        product_name=data.get('product_name') or 'Purchase',
        product_description=data.get('description', ''),
        quantity=int(data.get('quantity', 1)),
        unit_price=amount,
        total_amount=amount,
        status='pending',
        expires_at=datetime.utcnow() + timedelta(hours=24)  # 24 hours expiry
    )
    
    db.session.add(pr)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "data": {
            "id": pr.id,
            "request_number": pr.reference_number,
            "amount": float(pr.total_amount),
            "status": pr.status,
            "customer_name": customer_user.full_name,
            "customer_phone": customer_user.phone,
            "customer_code": customer.customer_code,
            "expires_at": pr.expires_at.isoformat(),
            "created_at": pr.created_at.isoformat() if pr.created_at else None
        },
        "message": "Purchase request sent successfully"
    }), 201


@api.route('/merchants/request-withdrawal', methods=['POST'])
@require_role('merchant')
def merchant_request_withdrawal(user):
    """Create a pending merchant withdrawal settlement request."""
    from app.models import Merchant, Settlement

    merchant = Merchant.query.filter_by(user_id=user.id).first()
    if not merchant:
        return jsonify({"success": False, "message": "Merchant not found"}), 404

    data = request.get_json() or {}
    amount = float(data.get('amount', 0) or 0)
    if amount <= 0:
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": "Amount must be positive"
        }), 400

    if amount > float(merchant.balance or 0):
        return jsonify({
            "success": False,
            "error": "INSUFFICIENT_BALANCE",
            "message": "Withdrawal amount exceeds merchant balance"
        }), 400

    commission_rate = Config.PLATFORM_COMMISSION_RATE
    commission_amount = amount * commission_rate
    net_amount = amount - commission_amount

    settlement = Settlement(
        merchant_id=merchant.id,
        settlement_type='withdrawal',
        gross_amount=amount,
        commission_rate=commission_rate,
        commission_amount=commission_amount,
        net_amount=net_amount,
        status='pending',
        notes=data.get('notes'),
    )
    db.session.add(settlement)
    db.session.commit()

    return jsonify({
        "success": True,
        "data": settlement.to_dict(),
        "message": "Withdrawal request created"
    }), 201


@api.route('/customers/purchase-requests/pending', methods=['GET'])
@require_role('customer')
def get_pending_requests(user):
    """Get pending purchase requests for customer"""
    from app.models import Customer, PurchaseRequest, Merchant
    from datetime import datetime
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    
    # Get pending requests that haven't expired
    requests = PurchaseRequest.query.filter(
        PurchaseRequest.customer_id == customer.id,
        PurchaseRequest.status == 'pending',
        PurchaseRequest.expires_at > datetime.utcnow()
    ).order_by(PurchaseRequest.created_at.desc()).all()
    
    result = []
    for r in requests:
        merchant = db.session.get(Merchant, r.merchant_id)
        result.append({
            "id": r.id,
            "request_number": r.reference_number,
            "amount": float(r.total_amount),
            "description": r.product_description,
            "merchant_name": merchant.shop_name if merchant else "Unknown",
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    
    return jsonify({
        "success": True,
        "data": result,
        "message": "Pending requests retrieved"
    })


@api.route('/customers/purchase-requests/<int:request_id>/accept', methods=['POST'])
@require_role('customer')
def accept_purchase_request(user, request_id):
    """Accept a purchase request"""
    from app.models import Customer, PurchaseRequest, Transaction, Settlement
    from datetime import datetime
    import uuid
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    
    pr = db.session.get(PurchaseRequest, request_id)
    if not pr or pr.customer_id != customer.id:
        return jsonify({"success": False, "message": "Request not found"}), 404
    
    if pr.status != 'pending':
        return jsonify({"success": False, "message": "Request is not pending"}), 400
    
    if pr.expires_at < datetime.utcnow():
        return jsonify({"success": False, "message": "Request has expired"}), 400
    
    if pr.total_amount > customer.available_balance:
        return jsonify({"success": False, "message": "Insufficient balance"}), 400
    
    # Update purchase request
    pr.status = 'accepted'
    
    # Deduct from customer balance
    customer.available_balance -= pr.total_amount
    
    # Create transaction
    transaction = Transaction(
        transaction_number=f"TXN-{uuid.uuid4().hex[:8].upper()}",
        customer_id=customer.id,
        merchant_id=pr.merchant_id,
        purchase_request_id=pr.id,
        total_amount=pr.total_amount,
        remaining_amount=pr.total_amount,
        commission_rate=Config.PLATFORM_COMMISSION_RATE,
        status='active'
    )
    db.session.add(transaction)
    db.session.flush()
    
    # Create settlement for merchant
    commission = pr.total_amount * Config.PLATFORM_COMMISSION_RATE
    settlement = Settlement(
        merchant_id=pr.merchant_id,
        transaction_id=transaction.id,
        gross_amount=pr.total_amount,
        commission_amount=commission,
        net_amount=pr.total_amount - commission,
        status='pending'
    )
    db.session.add(settlement)
    
    db.session.commit()
    
    return jsonify({
        "success": True,
        "data": {
            "transaction_id": transaction.id,
            "transaction_number": transaction.transaction_number,
            "amount": float(transaction.total_amount),
            "new_balance": float(customer.available_balance)
        },
        "message": "Purchase request accepted"
    })


@api.route('/customers/purchase-requests/<int:request_id>/reject', methods=['POST'])
@require_role('customer')
def reject_purchase_request(user, request_id):
    """Reject a purchase request"""
    from app.models import Customer, PurchaseRequest
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    
    pr = db.session.get(PurchaseRequest, request_id)
    if not pr or pr.customer_id != customer.id:
        return jsonify({"success": False, "message": "Request not found"}), 404
    
    if pr.status != 'pending':
        return jsonify({"success": False, "message": "Request is not pending"}), 400
    
    pr.status = 'rejected'
    db.session.commit()
    
    return jsonify({
        "success": True,
        "data": {"id": pr.id, "status": "rejected"},
        "message": "Purchase request rejected"
    })


# === Payment Routes ===

@api.route('/customers/transactions/<int:transaction_id>/pay', methods=['POST'])
@require_role('customer')
def make_payment(user, transaction_id):
    """Make a payment on a transaction"""
    from app.models import Customer, Transaction, Payment
    from datetime import datetime
    import uuid
    
    customer = Customer.query.filter_by(user_id=user.id).first()
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    
    transaction = db.session.get(Transaction, transaction_id)
    if not transaction or transaction.customer_id != customer.id:
        return jsonify({"success": False, "message": "Transaction not found"}), 404
    
    if transaction.status == 'completed':
        return jsonify({"success": False, "message": "Transaction already completed"}), 400
    
    data = request.get_json()
    amount = float(data.get('amount', 0))
    
    if amount <= 0:
        return jsonify({"success": False, "message": "Invalid payment amount"}), 400
    
    if amount > transaction.remaining_amount:
        amount = float(transaction.remaining_amount)
    
    # Create payment
    payment = Payment(
        payment_reference=f"PAY-{uuid.uuid4().hex[:8].upper()}",
        transaction_id=transaction.id,
        customer_id=customer.id,
        amount=amount,
        payment_method=data.get('payment_method', 'card'),
        status='completed',
        payment_date=datetime.utcnow()
    )
    db.session.add(payment)
    
    # Update transaction
    transaction.remaining_amount -= amount
    if transaction.remaining_amount <= 0:
        transaction.remaining_amount = 0
        transaction.status = 'completed'
    
    # Restore customer balance
    customer.available_balance += amount
    
    db.session.commit()
    
    return jsonify({
        "success": True,
        "data": {
            "payment_id": payment.id,
            "payment_number": payment.payment_reference,
            "amount_paid": float(payment.amount),
            "remaining_amount": float(transaction.remaining_amount),
            "transaction_status": transaction.status,
            "new_balance": float(customer.available_balance)
        },
        "message": "Payment successful"
    })


# === Health Check ===

@api.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "success": True,
        "data": {
            "status": "healthy",
            "framework": "flask",
            "version": Config.APP_VERSION
        },
        "message": "Service is healthy"
    })


# === Admin Routes ===

@api.route('/admin/dashboard/stats', methods=['GET'])
@require_role('admin')
def admin_dashboard_stats(user):
    """Admin dashboard aggregate metrics."""
    from sqlalchemy import func
    from app.models import User, Customer, Merchant, Transaction, PurchaseRequest, Settlement

    data = {
        "total_users": User.query.count(),
        "total_customers": Customer.query.count(),
        "total_merchants": Merchant.query.count(),
        "total_transactions": Transaction.query.count(),
        "active_transactions": Transaction.query.filter_by(status='active').count(),
        "total_purchase_requests": PurchaseRequest.query.count(),
        "pending_purchase_requests": PurchaseRequest.query.filter_by(status='pending').count(),
        "total_settlements": Settlement.query.count(),
        "pending_settlements": Settlement.query.filter_by(status='pending').count(),
        "platform_commission": float(
            db.session.query(func.sum(Settlement.commission_amount)).scalar() or 0
        ),
    }
    return jsonify({"success": True, "data": data, "message": "Admin stats retrieved"})


@api.route('/admin/users', methods=['GET'])
@require_role('admin')
def admin_users(user):
    from app.models import User
    page, page_size = _pagination_params()
    query = User.query
    role = request.args.get('role')
    if role:
        query = query.filter_by(role=role)
    items = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return jsonify({
        "success": True,
        "data": [i.to_dict() for i in items],
        "message": "Users retrieved",
        "pagination": {"page": page, "page_size": page_size, "total": query.count()},
    })


@api.route('/admin/customers', methods=['GET'])
@require_role('admin')
def admin_customers(user):
    from app.models import Customer
    page, page_size = _pagination_params()
    query = Customer.query
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    items = query.order_by(Customer.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return jsonify({
        "success": True,
        "data": [i.to_dict() for i in items],
        "message": "Customers retrieved",
        "pagination": {"page": page, "page_size": page_size, "total": query.count()},
    })


@api.route('/admin/merchants', methods=['GET'])
@require_role('admin')
def admin_merchants(user):
    from app.models import Merchant
    page, page_size = _pagination_params()
    query = Merchant.query
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    items = query.order_by(Merchant.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return jsonify({
        "success": True,
        "data": [i.to_dict() for i in items],
        "message": "Merchants retrieved",
        "pagination": {"page": page, "page_size": page_size, "total": query.count()},
    })


@api.route('/admin/transactions', methods=['GET'])
@require_role('admin')
def admin_transactions(user):
    from app.models import Transaction
    page, page_size = _pagination_params()
    query = Transaction.query
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    items = query.order_by(Transaction.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return jsonify({
        "success": True,
        "data": [i.to_dict() for i in items],
        "message": "Transactions retrieved",
        "pagination": {"page": page, "page_size": page_size, "total": query.count()},
    })


@api.route('/admin/purchase-requests', methods=['GET'])
@require_role('admin')
def admin_purchase_requests(user):
    from app.models import PurchaseRequest
    page, page_size = _pagination_params()
    query = PurchaseRequest.query
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    items = query.order_by(PurchaseRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return jsonify({
        "success": True,
        "data": [i.to_dict() for i in items],
        "message": "Purchase requests retrieved",
        "pagination": {"page": page, "page_size": page_size, "total": query.count()},
    })


@api.route('/admin/settlements', methods=['GET'])
@require_role('admin')
def admin_settlements(user):
    from app.models import Settlement
    page, page_size = _pagination_params()
    query = Settlement.query
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    items = query.order_by(Settlement.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return jsonify({
        "success": True,
        "data": [i.to_dict() for i in items],
        "message": "Settlements retrieved",
        "pagination": {"page": page, "page_size": page_size, "total": query.count()},
    })


@api.route('/admin/users/<int:user_id>/status', methods=['PUT'])
@require_role('admin')
def moderate_user_status(user, user_id):
    from app.models import User
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({"success": False, "message": "User not found"}), 404
    data = request.get_json() or {}
    target.is_active = bool(data.get('is_active', True))
    db.session.commit()
    return jsonify({"success": True, "data": target.to_dict(), "message": "User status updated"})


@api.route('/admin/customers/<int:customer_id>/status', methods=['PUT'])
@require_role('admin')
def moderate_customer_status(user, customer_id):
    from app.models import Customer
    target = db.session.get(Customer, customer_id)
    if not target:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    data = request.get_json() or {}
    status = data.get('status')
    if not status:
        return jsonify({"success": False, "message": "status is required"}), 400
    target.status = status
    db.session.commit()
    return jsonify({"success": True, "data": target.to_dict(), "message": "Customer status updated"})


@api.route('/admin/merchants/<int:merchant_id>/status', methods=['PUT'])
@require_role('admin')
def moderate_merchant_status(user, merchant_id):
    from app.models import Merchant
    target = db.session.get(Merchant, merchant_id)
    if not target:
        return jsonify({"success": False, "message": "Merchant not found"}), 404
    data = request.get_json() or {}
    if 'status' in data:
        target.status = data.get('status')
    if 'is_verified' in data:
        target.is_verified = bool(data.get('is_verified'))
    db.session.commit()
    return jsonify({"success": True, "data": target.to_dict(), "message": "Merchant status updated"})


@api.route('/admin/settlements/<int:settlement_id>/status', methods=['PUT'])
@require_role('admin')
def moderate_settlement_status(user, settlement_id):
    from app.models import Settlement
    target = db.session.get(Settlement, settlement_id)
    if not target:
        return jsonify({"success": False, "message": "Settlement not found"}), 404
    data = request.get_json() or {}
    status = data.get('status')
    if not status:
        return jsonify({"success": False, "message": "status is required"}), 400
    target.status = status
    if status == 'completed':
        target.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True, "data": target.to_dict(), "message": "Settlement status updated"})
