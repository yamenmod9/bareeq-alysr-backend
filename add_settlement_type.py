import sqlite3

conn = sqlite3.connect('instance/bareeq_alysr.db')
cur = conn.cursor()

# Check if column exists
cur.execute('PRAGMA table_info(settlements)')
columns = [col[1] for col in cur.fetchall()]

if 'settlement_type' not in columns:
    cur.execute("ALTER TABLE settlements ADD COLUMN settlement_type VARCHAR(20) DEFAULT 'income'")
    print('Added settlement_type column')
else:
    print('Column already exists')

conn.commit()
conn.close()
print('Done!')
