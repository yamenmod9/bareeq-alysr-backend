import sqlite3

conn = sqlite3.connect('instance/bareeq_alysr.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("TABLES:", [r[0] for r in cursor.fetchall()])

# Check customers (has credit limit info)
cursor.execute("SELECT * FROM customers")
print("\nCUSTOMERS:")
for r in cursor.fetchall():
    print(f"  {r}")

# Check merchants
cursor.execute("SELECT * FROM merchants")
print("\nMERCHANTS:")
for r in cursor.fetchall():
    print(f"  {r}")

# Check purchase_requests
cursor.execute("SELECT * FROM purchase_requests")
print("\nPURCHASE_REQUESTS:")
for r in cursor.fetchall():
    print(f"  {r}")

# Check transactions
cursor.execute("SELECT * FROM transactions")
print("\nTRANSACTIONS:")
for r in cursor.fetchall():
    print(f"  {r}")

conn.close()
