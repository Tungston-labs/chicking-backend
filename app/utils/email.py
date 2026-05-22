import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.config.settings import get_settings


settings = get_settings()


def _normalized_smtp_password() -> str:
    return (settings.smtp_password or "").replace(" ", "").strip()


def _sender_email() -> str:
    return (settings.email_from or settings.smtp_username or "").strip()


def _ensure_email_settings() -> None:
    if not settings.smtp_host or not settings.smtp_username:
        raise RuntimeError("SMTP host or username is not configured")
    if not _normalized_smtp_password():
        raise RuntimeError("SMTP password is not configured")
    if not _sender_email():
        raise RuntimeError("Sender email is not configured")


def _build_otp_message(recipient_email: str, otp: str, expires_in_minutes: int) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "Your Chicking CMS verification code"
    message["From"] = formataddr((settings.email_from_name, _sender_email()))
    message["To"] = recipient_email
    message.set_content(
        "\n".join(
            [
                "Hello,",
                "",
                "We received a request to reset your password for Chicking CMS.",
                f"Your verification OTP is: {otp}",
                f"This OTP will expire in {expires_in_minutes} minutes.",
                "",
                "If you did not request this, you can ignore this email.",
            ]
        )
    )
    return message


def _send_email_sync(message: EmailMessage) -> None:
    _ensure_email_settings()

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as server:
        server.ehlo()
        if settings.smtp_use_tls:
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
        server.login(settings.smtp_username, _normalized_smtp_password())
        server.send_message(message)


async def send_password_reset_otp_email(recipient_email: str, otp: str, expires_in_minutes: int) -> None:
    message = _build_otp_message(recipient_email, otp, expires_in_minutes)
    await asyncio.to_thread(_send_email_sync, message)
