"""
Database helpers using PyMySQL. Plain simple functions, no async, no ORM.

Interview points:
- Why raw SQL instead of ORM? Full control, you can explain every query,
  and you can show EXPLAIN output for index usage.
- get_connection() opens a fresh connection per call. Simple and safe for
  a small project. Mention in interviews: "in production I would use a
  connection pool (e.g. DBUtils or SQLAlchemy pool) to avoid the cost of
  opening a TCP connection on every request."
"""

import os
import pymysql

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "database": os.getenv("DB_NAME", "ticketdb"),
    "cursorclass": pymysql.cursors.DictCursor,  # rows come back as dicts
}


def get_connection():
    return pymysql.connect(**DB_CONFIG)


def decide_status(category, sentiment):
    """
    Human-in-the-loop routing rule:
    - negative tickets ALWAYS need a human review before being worked on
    - neutral billing tickets also go to review (money issues are risky
      even when the customer sounds calm)
    - everything else is handled automatically ('open')
    Interview point: ML makes the fast decision, humans stay in the loop
    for the high-risk slice. This is how real AI systems are deployed.
    """
    if sentiment == "negative":
        return "needs_review"
    if sentiment == "neutral" and category == "billing":
        return "needs_review"
    return "open"


def insert_ticket(subject, body, category=None, sentiment=None):
    status = decide_status(category, sentiment)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tickets (subject, body, category, sentiment, status) "
                "VALUES (%s, %s, %s, %s, %s)",
                (subject, body, category, sentiment, status),
            )
        conn.commit()
        return cur.lastrowid, status
    finally:
        conn.close()


def search_tickets(query, limit=50):
    """Keyword search over subject + body using SQL LIKE."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            like = f"%{query}%"
            cur.execute(
                "SELECT * FROM tickets WHERE subject LIKE %s OR body LIKE %s "
                "ORDER BY created_at DESC LIMIT %s",
                (like, like, limit),
            )
            return cur.fetchall()
    finally:
        conn.close()


def get_review_queue():
    """Tickets waiting for a human decision. Uses idx_status."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM tickets WHERE status='needs_review' "
                "ORDER BY created_at ASC"
            )
            return cur.fetchall()
    finally:
        conn.close()


def resolve_ticket(ticket_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tickets SET status='resolved', resolved_at=NOW() "
                "WHERE id=%s",
                (ticket_id,),
            )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def cleanup_resolved(days=7):
    """
    Retention policy: resolved tickets are deleted after `days` days.
    Keeps the database from growing forever.
    Interview point: in production this runs on a scheduler (cron /
    rq-scheduler); here it runs at API startup and after each analysis job.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tickets WHERE status='resolved' "
                "AND resolved_at < NOW() - INTERVAL %s DAY",
                (days,),
            )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_tickets(category=None, limit=100):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if category:
                # uses idx_category index -- show EXPLAIN in interviews
                cur.execute(
                    "SELECT * FROM tickets WHERE category = %s "
                    "ORDER BY created_at DESC LIMIT %s",
                    (category, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM tickets ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
            return cur.fetchall()
    finally:
        conn.close()


def create_job(job_id, query_text):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO analysis_jobs (id, status, query_text) "
                "VALUES (%s, 'queued', %s)",
                (job_id, query_text),
            )
        conn.commit()
    finally:
        conn.close()


def update_job_status(job_id, status):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if status in ("done", "failed"):
                cur.execute(
                    "UPDATE analysis_jobs SET status=%s, finished_at=NOW() "
                    "WHERE id=%s",
                    (status, job_id),
                )
            else:
                cur.execute(
                    "UPDATE analysis_jobs SET status=%s WHERE id=%s",
                    (status, job_id),
                )
        conn.commit()
    finally:
        conn.close()


def get_job(job_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM analysis_jobs WHERE id=%s", (job_id,))
            return cur.fetchone()
    finally:
        conn.close()


def save_report(job_id, content):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO reports (job_id, content) VALUES (%s, %s)",
                (job_id, content),
            )
        conn.commit()
    finally:
        conn.close()


def get_report(job_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM reports WHERE job_id=%s ORDER BY id DESC LIMIT 1",
                (job_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()
