import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.db')
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Get counts by overall_status where it's a by-poll
c.execute("SELECT overall_status, COUNT(*) FROM records WHERE el_type LIKE '%-BP' GROUP BY overall_status")
bp_stats = c.fetchall()
print("By-Poll Stats:", bp_stats)

# Get counts by overall_status for normal elections
c.execute("SELECT overall_status, COUNT(*) FROM records WHERE el_type NOT LIKE '%-BP' GROUP BY overall_status")
normal_stats = c.fetchall()
print("Normal Stats:", normal_stats)

conn.close()
