"""
Create test users directly in the database
"""
from app.flask_app import flask_app, db
from app.models.user import User
from app.models.customer import Customer
from app.models.merchant import Merchant, Branch

print("Creating test data...")

with flask_app.app_context():
    # Create all tables first
    db.create_all()
    print("✓ Database tables created")
    
    # Check existing
    existing_customer = User.query.filter_by(email="customer@test.com").first()
    existing_merchant = User.query.filter_by(email="merchant@test.com").first()
    
    if existing_customer:
        print("✓ Customer already exists")
    else:
        print("Creating customer...")
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
        print("✓ Customer created")
    
    if existing_merchant:
        print("✓ Merchant already exists")
    else:
        print("Creating merchant...")
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
        print("✓ Merchant created")
    
    db.session.commit()
    print("\n✅ Test data created successfully!")
    
    # Verify
    print("\n=== Verification ===")
    merchant_user = User.query.filter_by(email="merchant@test.com").first()
    customer_user = User.query.filter_by(email="customer@test.com").first()
    
    if merchant_user:
        print(f"✓ Merchant: {merchant_user.email}")
        print(f"  Password test: {merchant_user.verify_password('password123')}")
    
    if customer_user:
        print(f"✓ Customer: {customer_user.email}")
        customer = Customer.query.filter_by(user_id=customer_user.id).first()
        print(f"  Password test: {customer_user.verify_password('password123')}")
        if customer:
            print(f"  Customer Code: {customer.customer_code}")
            print(f"  Credit Limit: {customer.credit_limit} SAR")
