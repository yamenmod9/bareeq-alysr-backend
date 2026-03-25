import requests
import json

print("Testing merchant login...")
response = requests.post(
    "http://localhost:8000/auth/login",
    json={"email": "merchant@test.com", "password": "password123"}
)

print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

if response.status_code == 200:
    print("\n✅ MERCHANT LOGIN SUCCESSFUL!")
else:
    print("\n❌ Merchant login failed")
