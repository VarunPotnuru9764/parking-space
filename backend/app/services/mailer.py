import smtplib
import ssl
from email.message import EmailMessage

from app.config import get_setting


def email_delivery_configuration() -> tuple[str, int, str, str | None, str | None, bool]:
    host = get_setting("SMTP_HOST")
    sender = get_setting("SMTP_FROM")
    username = get_setting("SMTP_USERNAME")
    password = get_setting("SMTP_PASSWORD")
    port_value = get_setting("SMTP_PORT", "587") or "587"
    use_ssl = (get_setting("SMTP_USE_SSL", "") or "").lower() == "true"
    if not host or not sender or not port_value:
        raise RuntimeError("Email delivery is not configured. Set SMTP_HOST, SMTP_PORT and SMTP_FROM in backend/.env.")
    try:
        port = int(port_value)
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT must be a valid integer.") from exc
    return host, port, sender, username, password, use_ssl


def send_account_email(recipient: str, subject: str, body: str) -> None:
    host, port, sender, username, password, use_ssl = email_delivery_configuration()

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    context = ssl.create_default_context()
    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as server:
                if username and password:
                    server.login(username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                if username and password:
                    server.login(username, password)
                server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise RuntimeError("Could not deliver account email. Check the SMTP settings in backend/.env.") from exc
