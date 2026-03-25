"""
Test login endpoint directly
"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("=== Testing Login Endpoints ===\n")

# Test merchant login
print("1. Testing Merchant Login...")
merchant_data = {
    "email": "merchant@test.com",
    "password": "password123"
}

try:
    response = requests.post(f"{BASE_URL}/auth/login", json=merchant_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Merchant login successful!")
    else:
        print("❌ Merchant login failed!")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*50 + "\n")

# Test customer login
print("2. Testing Customer Login...")
customer_data = {
    "email": "customer@test.com",
    "password": "password123"
}

try:
    response = requests.post(f"{BASE_URL}/auth/login", json=customer_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Customer login successful!")
    else:
        print("❌ Customer login failed!")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*50 + "\n")

# Test with wrong password
print("3. Testing Invalid Password...")
wrong_data = {
    "email": "merchant@test.com",
    "password": "wrongpassword"
}

try:
    response = requests.post(f"{BASE_URL}/auth/login", json=wrong_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 401:
        print("✅ Correctly rejected invalid password!")
    else:
        print("❌ Should have rejected invalid password!")
except Exception as e:
    print(f"❌ Error: {e}")
