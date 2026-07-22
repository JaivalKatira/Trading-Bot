"""
email_utils.py
--------------
Minimal SMTP sender. Uses Gmail's SMTP relay by default (smtp.gmail.com:465)
with an App Password (not your regular Gmail password — see README for how
to generate one). Each user who forks this repo sets their own credentials
as GitHub Secrets, so the email always goes from their own account to
themselves (or wherever EMAIL_TO points).

Required environment variables:
  EMAIL_ADDRESS       - the Gmail address sending the mail
  EMAIL_APP_PASSWORD  - a Gmail App Password (16-char, generated in
                        Google Account > Security > App Passwords)
Optional:
  EMAIL_TO            - recipient address (defaults to EMAIL_ADDRESS itself)
  SMTP_HOST           - defaults to smtp.gmail.com
  SMTP_PORT           - defaults to 465
"""

import os
import smtplib
from email.mime.text import MIMEText


def send_email(subject: str, body: str) -> None:
    email_address = os.environ["EMAIL_ADDRESS"]
    email_password = os.environ["EMAIL_APP_PASSWORD"]
    email_to = os.environ.get("EMAIL_TO") or email_address
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = email_address
    msg["To"] = email_to

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
        server.login(email_address, email_password)
        server.sendmail(email_address, [email_to], msg.as_string())
