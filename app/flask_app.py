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

    @app.route('/admin/self-test', methods=['GET'])
    @app.route('/admin/self-test/', methods=['GET'])
    def admin_self_test_page():
        """One-click backend self-test dashboard."""
        return """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Backend Self Test</title>
    <style>
        :root {
            --bg: #f5f7fb;
            --card: #ffffff;
            --ink: #1f2a37;
            --ok: #0f9d58;
            --bad: #c62828;
            --muted: #6b7280;
            --accent: #0b67c2;
        }
        body {
            margin: 0;
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(160deg, #eef5ff 0%, var(--bg) 50%, #f8f9fc 100%);
            color: var(--ink);
        }
        .wrap {
            max-width: 1080px;
            margin: 2rem auto;
            padding: 0 1rem;
        }
        .panel {
            background: var(--card);
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(16, 24, 40, 0.08);
            padding: 1rem;
            margin-bottom: 1rem;
        }
        h1 { margin: 0 0 0.75rem 0; font-size: 1.5rem; }
        .row { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
        button {
            border: 0;
            background: var(--accent);
            color: #fff;
            font-weight: 600;
            padding: 0.7rem 1rem;
            border-radius: 10px;
            cursor: pointer;
        }
        button:disabled { opacity: 0.55; cursor: not-allowed; }
        .meta { color: var(--muted); font-size: 0.92rem; }
        .ok { color: var(--ok); font-weight: 700; }
        .bad { color: var(--bad); font-weight: 700; }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.92rem;
            background: #fff;
        }
        th, td {
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
            padding: 0.55rem;
            vertical-align: top;
        }
        th { background: #f9fafb; }
        .tag {
            display: inline-block;
            padding: 0.1rem 0.45rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
            background: #edf2ff;
            color: #1f4e96;
        }
    </style>
</head>
<body>
    <div class="wrap">
        <div class="panel">
            <h1>Backend Self Test</h1>
            <div class="row">
                <button id="runBtn" type="button">Run Full Endpoint + Function Test</button>
                <span id="status" class="meta">Idle</span>
            </div>
            <p class="meta">This runs all configured endpoint and service-function checks automatically and returns a per-check status report.</p>
        </div>

        <div class="panel">
            <div id="summary" class="meta">No run yet.</div>
        </div>

        <div class="panel" style="overflow:auto;">
            <table>
                <thead>
                    <tr>
                        <th>Kind</th>
                        <th>Name</th>
                        <th>Status</th>
                        <th>HTTP</th>
                        <th>Duration (ms)</th>
                        <th>Message</th>
                    </tr>
                </thead>
                <tbody id="resultsBody">
                    <tr><td colspan="6" class="meta">Run the test to populate results.</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const runBtn = document.getElementById('runBtn');
        const status = document.getElementById('status');
        const summary = document.getElementById('summary');
        const resultsBody = document.getElementById('resultsBody');

        function esc(v) {
            return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }

        function setRows(checks) {
            if (!checks || checks.length === 0) {
                resultsBody.innerHTML = '<tr><td colspan="6" class="meta">No checks returned.</td></tr>';
                return;
            }
            resultsBody.innerHTML = checks.map(item => {
                const okClass = item.ok ? 'ok' : 'bad';
                const okText = item.ok ? 'PASS' : 'FAIL';
                return `
                    <tr>
                        <td><span class="tag">${esc(item.kind)}</span></td>
                        <td>${esc(item.name)}</td>
                        <td class="${okClass}">${okText}</td>
                        <td>${esc(item.status_code ?? '-')}</td>
                        <td>${esc(item.duration_ms ?? '-')}</td>
                        <td>${esc(item.message ?? '')}</td>
                    </tr>
                `;
            }).join('');
        }

        async function runTests() {
            runBtn.disabled = true;
            status.textContent = 'Running...';
            summary.textContent = 'Executing all checks...';
            try {
                const resp = await fetch('/admin/self-test/run', { method: 'POST' });
                const data = await resp.json();
                const s = data.summary || {};
                const cls = data.success ? 'ok' : 'bad';
                summary.innerHTML = `<span class="${cls}">${data.success ? 'PASS' : 'FAIL'}</span> ` +
                    `Total: ${esc(s.total)} | Passed: ${esc(s.passed)} | Failed: ${esc(s.failed)} | Duration: ${esc(s.duration_ms)} ms`;
                setRows(data.checks || []);
                status.textContent = 'Done';
            } catch (err) {
                summary.innerHTML = '<span class="bad">FAIL</span> Could not run self-test.';
                status.textContent = 'Error';
            } finally {
                runBtn.disabled = false;
            }
        }

        runBtn.addEventListener('click', runTests);
    </script>
</body>
</html>
        """

    @app.route('/admin/self-test/run', methods=['GET', 'POST'])
    @app.route('/admin/self-test/run/', methods=['GET', 'POST'])
    def admin_self_test_run():
        """Run endpoint/function self-test and return JSON report."""
        from app.self_test_runner import run_full_backend_self_test

        report = run_full_backend_self_test(app)
        return jsonify(report)

    if not Config.SERVE_WEB_APP:
        @app.route('/')
        def api_root():
            """API root endpoint when web hosting is disabled"""
            return jsonify({
                "success": True,
                "data": {
                    "name": Config.APP_NAME,
                    "version": Config.APP_VERSION,
                    "mode": "api"
                },
                "message": "Bareeq Alysr Flask API"
            })
    
    @app.route('/health')
    def flask_health():
        """Flask health check endpoint"""
        return jsonify({
            "success": True,
            "data": {
                "status": "healthy",
                "framework": "flask",
                "version": Config.APP_VERSION,
                "database": "connected"
            },
            "message": "Service is healthy"
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
    
    if Config.SERVE_WEB_APP:
        # Catch-all route for optional web app hosting (must be last)
        @app.route('/', defaults={'path': ''})
        @app.route('/<path:path>')
        def serve_frontend(path):
            """Serve static frontend files when web hosting is enabled"""
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
