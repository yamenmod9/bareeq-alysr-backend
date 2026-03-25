"""
Flask Application
Handles Flask-SQLAlchemy initialization and admin routes
"""
import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from app.config import Config, get_config
from app.database import db, migrate, create_all_tables, init_db

# Get backend and workspace root directories
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = os.path.dirname(BACKEND_ROOT)
FRONTEND_DIST = os.path.join(WORKSPACE_ROOT, 'frontend', 'dist')


def create_flask_app() -> Flask:
    """
    Create and configure the Flask application
    Used for Flask-SQLAlchemy and admin functionality
    """
    app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path='')
    
    # Load configuration
    config = get_config()
    app.config.from_object(config)
    
    # Initialize extensions using init_db to store the app reference
    init_db(app)
    
    # Enable CORS
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # Import models to register them with SQLAlchemy
    with app.app_context():
        from app.models import (
            User, Customer, Merchant, Branch,
            PurchaseRequest, Transaction, Payment,
            Settlement, RepaymentPlan, RepaymentSchedule
        )
    
    # Register API blueprint
    from app.flask_routes import api
    app.register_blueprint(api)
    
    # Register Flask routes (frontend serving)
    register_flask_routes(app)
    
    return app


def register_flask_routes(app: Flask):
    """Register Flask-specific routes (frontend, admin, etc.)"""
    
    @app.route('/health')
    def flask_health():
        """Flask health check endpoint"""
        return jsonify({
            "status": "healthy",
            "framework": "flask",
            "database": "connected"
        })

    @app.route('/config')
    def public_config():
        """Public configuration endpoint for client apps"""
        return jsonify({
            "success": True,
            "data": {
                "default_credit_limit": Config.DEFAULT_CREDIT_LIMIT,
                "max_credit_limit": Config.MAX_CREDIT_LIMIT,
                "auto_approve_ceiling": Config.AUTO_APPROVE_LIMIT_CEILING,
                "commission_rate": Config.PLATFORM_COMMISSION_RATE,
                "commission_percentage": f"{Config.PLATFORM_COMMISSION_RATE * 100}%",
                "default_repayment_days": Config.DEFAULT_REPAYMENT_DAYS,
                "available_repayment_plans": Config.REPAYMENT_PLANS,
                "purchase_request_expiry_hours": Config.PURCHASE_REQUEST_EXPIRY_HOURS,
                "jwt_expiry_hours": Config.JWT_ACCESS_TOKEN_EXPIRE_HOURS,
            },
            "message": "Public configuration"
        })
    
    @app.route('/debug/files')
    def debug_files():
        """Debug endpoint to check frontend files"""
        import os
        files = []
        if os.path.exists(app.static_folder):
            for root, dirs, filenames in os.walk(app.static_folder):
                for filename in filenames:
                    files.append(os.path.relpath(os.path.join(root, filename), app.static_folder))
        return jsonify({
            "static_folder": app.static_folder,
            "exists": os.path.exists(app.static_folder),
            "files": files[:20]  # Limit to first 20 files
        })
    
    # Catch-all route for frontend (must be last)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        """Serve the React frontend or static files"""
        # API routes are handled by the blueprint, don't catch them here
        if path.startswith(('auth/', 'customers/', 'merchants/', 'admin/')):
            # Let the API blueprint handle these
            return jsonify({"error": "Not Found"}), 404
        
        # Serve static file if it exists
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        
        # Otherwise serve index.html for SPA routing
        return send_from_directory(app.static_folder, 'index.html')
    
    @app.route('/admin/stats')
    def admin_stats():
        """Admin statistics endpoint (Flask-based)"""
        from app.models import User, Customer, Merchant, Transaction, Settlement
        from sqlalchemy import func
        
        with app.app_context():
            stats = {
                "total_users": User.query.count(),
                "total_customers": Customer.query.count(),
                "total_merchants": Merchant.query.count(),
                "total_transactions": Transaction.query.count(),
                "active_transactions": Transaction.query.filter_by(status="active").count(),
                "completed_transactions": Transaction.query.filter_by(status="completed").count(),
                "total_settlements": Settlement.query.count(),
                "pending_settlements": Settlement.query.filter_by(status="pending").count(),
                "platform_commission": db.session.query(
                    func.sum(Settlement.commission_amount)
                ).filter_by(status="completed").scalar() or 0
            }
        
        return jsonify({
            "success": True,
            "data": stats,
            "message": "Admin statistics retrieved"
        })
    
    @app.route('/admin/create-test-data')
    def create_test_data():
        """Create test data for development"""
        from app.models import User, Customer, Merchant, Branch
        from app.config import Config
        
        with app.app_context():
            # Check if data exists
            if User.query.first():
                return jsonify({
                    "success": False,
                    "message": "Test data already exists"
                })
            
            # Create test customer
            customer_user = User(
                email="customer@test.com",
                full_name="Ahmed Customer",
                phone="+966501111111",
                national_id="1234567890",
                role="customer",
                is_active=True,
                is_verified=True
            )
            customer_user.set_password("password123")
            db.session.add(customer_user)
            db.session.flush()

            customer = Customer(
                user_id=customer_user.id,
                credit_limit=Config.DEFAULT_CREDIT_LIMIT,
                available_balance=Config.DEFAULT_CREDIT_LIMIT,
                status="active"
            )
            db.session.add(customer)

            # Create test merchant
            merchant_user = User(
                email="merchant@test.com",
                full_name="Mohammed Merchant",
                phone="+966502222222",
                national_id="0987654321",
                role="merchant",
                is_active=True,
                is_verified=True
            )
            merchant_user.set_password("password123")
            db.session.add(merchant_user)
            db.session.flush()

            merchant = Merchant(
                user_id=merchant_user.id,
                shop_name="Al-Yusr Electronics",
                shop_name_ar="الكترونيات اليسر",
                city="Riyadh",
                status="active",
                is_verified=True
            )
            db.session.add(merchant)
            db.session.flush()

            # Create test admin
            admin_user = User(
                email="admin@test.com",
                full_name="Admin User",
                phone="+966503333333",
                national_id="1122334455",
                role="admin",
                is_active=True,
                is_verified=True
            )
            admin_user.set_password("Admin@123")
            db.session.add(admin_user)
            db.session.flush()

            # Create test branch
            branch = Branch(
                merchant_id=merchant.id,
                name="Main Branch - Olaya",
                city="Riyadh",
                address="Olaya Street",
                is_active=True
            )
            db.session.add(branch)

            db.session.commit()

            return jsonify({
                "success": True,
                "data": {
                    "customer": {
                        "email": "customer@test.com",
                        "password": "password123",
                        "user_id": customer_user.id,
                        "customer_id": customer.id
                    },
                    "merchant": {
                        "email": "merchant@test.com",
                        "password": "password123",
                        "user_id": merchant_user.id,
                        "merchant_id": merchant.id
                    },
                    "admin": {
                        "email": "admin@test.com",
                        "password": "password123",
                        "user_id": admin_user.id
                    }
                },
                "message": "Test data created successfully"
            })


def init_database(app: Flask):
    """Initialize database tables"""
    with app.app_context():
        # Import all models
        from app.models import (
            User, Customer, Merchant, Branch,
            PurchaseRequest, Transaction, Payment,
            Settlement, RepaymentPlan, RepaymentSchedule
        )
        from app.models.customer import CustomerLimitHistory
        
        # Create tables
        db.create_all()
        print("✅ Database tables created successfully!")


# Create Flask app instance
flask_app = create_flask_app()
