from app.flask_app import flask_app
from app.models.user import User
from app.models.merchant import Merchant
from app.models.customer import Customer

with flask_app.app_context():
    print("=== Checking Test Users ===\n")
    
    merchant = User.query.filter_by(email="merchant@test.com").first()
    if merchant:
        print(f"✓ Merchant user: {merchant.email}")
        print(f"  Role: {merchant.role}")
        print(f"  Active: {merchant.is_active}")
        print(f"  Verified: {merchant.is_verified}")
        print(f"  Has password hash: {bool(merchant.password_hash)}")
        
        # Test password
        test_result = merchant.verify_password("password123")
        print(f"  Password 'password123' verifies: {test_result}")
        
        # Check merchant profile
        merchant_profile = Merchant.query.filter_by(user_id=merchant.id).first()
        if merchant_profile:
            print(f"  ✓ Merchant profile: {merchant_profile.shop_name}")
        else:
            print(f"  ✗ No merchant profile found!")
    else:
        print("✗ No merchant user found in database")
    
    print()
    
    customer = User.query.filter_by(email="customer@test.com").first()
    if customer:
        print(f"✓ Customer user: {customer.email}")
        print(f"  Password 'password123' verifies: {customer.verify_password('password123')}")
        
        customer_profile = Customer.query.filter_by(user_id=customer.id).first()
        if customer_profile:
            print(f"  ✓ Customer profile exists")
        else:
            print(f"  ✗ No customer profile found!")
    else:
        print("✗ No customer user found in database")
    
    print("\n=== Summary ===")
    print(f"Total users: {User.query.count()}")
    print(f"Total merchants: {Merchant.query.count()}")
    print(f"Total customers: {Customer.query.count()}")
