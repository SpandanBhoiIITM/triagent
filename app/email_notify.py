"""
Email notifications via SMTP. One function, ~15 lines of real logic.


"""

import os
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")        # your email address
SMTP_PASS = os.getenv("SMTP_PASS")        # app password, not your login password
NOTIFY_TO = os.getenv("NOTIFY_TO", SMTP_USER)  # who receives alerts


def send_email(subject, body):
    if not SMTP_USER or not SMTP_PASS:
        print(f"[email skipped - SMTP not configured] {subject}")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFY_TO

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()                    # encrypt the connection
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[email failed] {e}")
        return False


def notify_needs_review(ticket_id, subject, sentiment):
    send_email(
        subject=f"[Ticket Intelligence] Ticket #{ticket_id} needs review",
        body=(
            f"A ticket was routed to human review.\n\n"
            f"ID: {ticket_id}\nSubject: {subject}\nSentiment: {sentiment}\n\n"
            f"Open the Review queue tab to handle it."
        ),
    )
