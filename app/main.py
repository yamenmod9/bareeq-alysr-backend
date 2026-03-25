"""
FastAPI Main Application
Primary API server with all endpoints
"""
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError

from app.config import Config
from app.routers import auth_router, customers_router, merchants_router, admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler
    Runs on startup and shutdown
    """
    # Startup
    print(f"🚀 Starting {Config.APP_NAME} v{Config.APP_VERSION}")
    print(f"📊 Database: {Config.SQLALCHEMY_DATABASE_URI}")
    print(f"🔐 JWT Expiry: {Config.JWT_ACCESS_TOKEN_EXPIRE_HOURS} hours")
    print(f"💰 Commission Rate: {Config.PLATFORM_COMMISSION_RATE * 100}%")
    
    yield
    
    # Shutdown
    print(f"👋 Shutting down {Config.APP_NAME}")


# Create FastAPI application
app = FastAPI(
    title="Bareeq Al-Yusr BNPL API",
    description="""
    ## بريق اليسر - Buy Now Pay Later Platform
    
    A BNPL platform for essential goods in the Saudi market.
    
    ### Features:
    - 🔐 **JWT Authentication** - Secure token-based auth with Nafath simulation
    - 👤 **Customer Management** - Credit limits, balances, transactions
    - 🏪 **Merchant Management** - Shops, branches, settlements
    - 💳 **BNPL Transactions** - Purchase requests, acceptance, payments
    - 📅 **Repayment Plans** - 1, 3, 6, 12, 18, 24 month options
    - 💰 **Settlements** - 0.5% platform commission
    
    ### Business Rules:
    - No interest charges - customers pay exact amount
    - Default repayment period: 10 days
    - Platform commission: 0.5% from merchant
    - Auto-approve credit limit up to 5,000 SAR
    """,
    version=Config.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Exception Handlers ===

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {"errors": errors},
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": "HTTP_ERROR",
            "message": str(exc.detail),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {"error": str(exc)} if Config.DEBUG else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# === Include Routers ===

app.include_router(auth_router)
app.include_router(customers_router)
app.include_router(merchants_router)
app.include_router(admin_router)


# === Root Endpoints ===

@app.get("/", tags=["Root"])
async def root():
    """API root endpoint"""
    return {
        "success": True,
        "data": {
            "name": Config.APP_NAME,
            "version": Config.APP_VERSION,
            "description": "Buy Now Pay Later Platform API",
            "docs": "/docs",
            "redoc": "/redoc"
        },
        "message": "Welcome to Bareeq Al-Yusr API",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "version": Config.APP_VERSION,
            "framework": "fastapi",
            "database": "connected"
        },
        "message": "Service is healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/config", tags=["Config"])
async def get_public_config():
    """Get public configuration"""
    return {
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
            "jwt_expiry_hours": Config.JWT_ACCESS_TOKEN_EXPIRE_HOURS
        },
        "message": "Public configuration",
        "timestamp": datetime.utcnow().isoformat()
    }


# === Admin Endpoints ===

@app.post("/api/admin/create-test-data", tags=["Admin"])
async def create_test_data():
    """Create test data for development"""
    from app.flask_app import flask_app, db
    from app.models import User, Customer, Merchant, Branch

    # Use Flask application context for Flask-SQLAlchemy
    with flask_app.app_context():
        try:
            existing_customer = User.query.filter_by(email="customer@test.com").first()
            existing_merchant = User.query.filter_by(email="merchant@test.com").first()

            results = {"created": [], "existing": []}

            if not existing_customer:
                customer_user = User(
                    email="customer@test.com",
                    full_name="Ahmed Al-Customer",
                    role="customer",
                    is_active=True,
                    is_verified=True,
                )
                customer_user.set_password("password123")
                db.session.add(customer_user)
                db.session.flush()

                customer = Customer(
                    user_id=customer_user.id,
                    credit_limit=5000.0,
                    available_balance=5000.0,
                    outstanding_balance=0.0,
                    status="active",
                )
                db.session.add(customer)
                results["created"].append("customer@test.com")
            else:
                results["existing"].append("customer@test.com")

            if not existing_merchant:
                merchant_user = User(
                    email="merchant@test.com",
                    full_name="Mohammed Al-Merchant",
                    role="merchant",
                    is_active=True,
                    is_verified=True,
                )
                merchant_user.set_password("password123")
                db.session.add(merchant_user)
                db.session.flush()

                merchant = Merchant(
                    user_id=merchant_user.id,
                    shop_name="Test Electronics Shop",
                    status="active",
                    is_verified=True,
                    total_transactions=0,
                    total_volume=0.0,
                )
                db.session.add(merchant)
                db.session.flush()

                branch = Branch(
                    merchant_id=merchant.id,
                    name="Main Branch",
                    address="Riyadh, Saudi Arabia",
                    is_active=True,
                )
                db.session.add(branch)
                results["created"].append("merchant@test.com")
            else:
                results["existing"].append("merchant@test.com")

            db.session.commit()

            return {
                "success": True,
                "data": results,
                "message": "Test data processed",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            db.session.rollback()
            return {
                "success": False,
                "error": "CREATE_TEST_DATA_ERROR",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }


# === Static Files & Frontend ===

# Get the path to static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

@app.get("/app", tags=["Frontend"])
async def serve_frontend():
    """Serve the frontend HTML"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# Mount static files (must be after routes)
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
