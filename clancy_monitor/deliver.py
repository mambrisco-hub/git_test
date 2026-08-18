"""Email delivery for the daily brief.

Sends the brief as a plain-text email via Gmail SMTP (App Password)
or any SMTP server. All settings come from environment variables.

Required env vars:
  SMTP_FROM      — sender address, e.g. yourname@gmail.com
  SMTP_TO        — recipient address (comma-separated for multiple)
  SMTP_PASSWORD  — Gmail App Password (not your main password)
                   Create one at: myaccount.google.com/apppasswords

Optional:
  SMTP_HOST      — defaults to smtp.gmail.com
  SMTP_PORT      — defaults to 587
"""

import os
import smtplib
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_brief(brief_text: str, brief_date: date | None = None) -> bool:
    """Send the brief via email. Returns True on success."""
    smtp_from = os.getenv("SMTP_FROM", "")
    smtp_to_raw = os.getenv("SMTP_TO", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not all([smtp_from, smtp_to_raw, smtp_password]):
        print("[deliver] Email not configured — skipping. Set SMTP_FROM, SMTP_TO, SMTP_PASSWORD.")
        return False

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    recipients = [r.strip() for r in smtp_to_raw.split(",") if r.strip()]

    if brief_date is None:
        brief_date = date.today()

    subject = f"Clancy Case Brief — {brief_date.strftime('%B %-d, %Y')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(brief_text, "plain", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_from, smtp_password)
            server.sendmail(smtp_from, recipients, msg.as_string())
        print(f"[deliver] Brief emailed to: {', '.join(recipients)}")
        return True
    except Exception as exc:
        print(f"[deliver] Email failed: {exc}")
        return False
