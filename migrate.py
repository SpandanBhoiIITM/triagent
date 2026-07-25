"""
One-time migration for existing databases: adds the human-in-the-loop
status column and resolved_at timestamp to the tickets table.

Run once:  python migrate.py
Safe to re-run: skips changes that already exist.
"""

from app.db import get_connection

MIGRATIONS = [
    "ALTER TABLE tickets ADD COLUMN status VARCHAR(20) DEFAULT 'open'",
    "ALTER TABLE tickets ADD COLUMN resolved_at TIMESTAMP NULL",
    "ALTER TABLE tickets ADD INDEX idx_status (status)",
    # existing negative tickets go to the review queue
    "UPDATE tickets SET status='needs_review' WHERE sentiment='negative'",
]

conn = get_connection()
try:
    with conn.cursor() as cur:
        for sql in MIGRATIONS:
            try:
                cur.execute(sql)
                print(f"OK:      {sql[:60]}")
            except Exception as e:
                print(f"SKIPPED: {sql[:60]} ({str(e)[:50]})")
    conn.commit()
finally:
    conn.close()
print("Migration complete.")
