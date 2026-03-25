import sqlite3
import secrets

# Generate customer code
def generate_customer_code():
    alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(8))

conn = sqlite3.connect('instance/bareeq_alysr.db')
cursor = conn.cursor()

# Check columns
cursor.execute('PRAGMA table_info(customers)')
cols = [r[1] for r in cursor.fetchall()]
print('Current columns:', cols)

if 'customer_code' not in cols:
    print('Adding customer_code column...')
    cursor.execute('ALTER TABLE customers ADD COLUMN customer_code VARCHAR(8)')
    
    # Generate codes for existing customers
    cursor.execute('SELECT id FROM customers')
    customers = cursor.fetchall()
    for (customer_id,) in customers:
        code = generate_customer_code()
        cursor.execute('UPDATE customers SET customer_code = ? WHERE id = ?', (code, customer_id))
        print(f'  Customer {customer_id} => {code}')
    
    conn.commit()
    print('Done!')
else:
    print('Column already exists')
    # Show existing codes
    cursor.execute('SELECT id, customer_code FROM customers')
    for row in cursor.fetchall():
        print(f'  Customer {row[0]} => {row[1]}')

conn.close()
