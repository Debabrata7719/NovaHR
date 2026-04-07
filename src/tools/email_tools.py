import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from email_validator import validate_email, EmailNotValidError

load_dotenv()


def is_valid_email(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False


def send_email(to_email: str, subject: str, body: str) -> dict:
    if not is_valid_email(to_email):
        return {
            "success": False,
            "to": to_email or "N/A",
            "error": "Invalid or missing email address",
            "skipped": True,
        }

    email_address = os.getenv("EMAIL_ADDRESS")
    email_password = os.getenv("EMAIL_APP_PASSWORD")

    if not email_address or not email_password:
        return {
            "success": False,
            "error": "Email credentials not configured. Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in .env",
        }

    try:
        msg = MIMEMultipart()
        msg["From"] = email_address
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)

        return {"success": True, "to": to_email, "skipped": False}

    except Exception as e:
        return {"success": False, "to": to_email, "error": str(e), "skipped": False}


def send_bulk_emails(recipients: list, subject: str, body: str) -> dict:
    valid_recipients = []
    skipped_recipients = []
    results = []

    for recipient in recipients:
        email = recipient.get("email", "")
        if not is_valid_email(email):
            skipped_recipients.append(
                {
                    "employee_id": recipient.get("employee_id", "unknown"),
                    "name": recipient.get("name", "unknown"),
                    "email": email or "N/A",
                    "reason": "No valid email",
                }
            )
            continue
        valid_recipients.append(recipient)

    for recipient in valid_recipients:
        result = send_email(recipient["email"], subject, body)
        result["employee_id"] = recipient.get("employee_id", "unknown")
        result["name"] = recipient.get("name", "unknown")
        results.append(result)

    return {
        "sent": results,
        "skipped": skipped_recipients,
        "total_sent": sum(1 for r in results if r.get("success")),
        "total_skipped": len(skipped_recipients),
    }
