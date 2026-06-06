import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

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


def _franchise_recipient_email() -> str:
    return (settings.franchise_enquiry_recipient or settings.smtp_username or "").strip()


def _build_franchise_enquiry_message(
    enquiry: dict[str, Any],
    document: tuple[str, bytes, str] | None = None,
) -> EmailMessage:
    recipient_email = _franchise_recipient_email()
    if not recipient_email:
        raise RuntimeError("Franchise enquiry recipient email is not configured")

    message = EmailMessage()
    message["Subject"] = f"New Franchise Enquiry - {enquiry['full_name']}"
    message["From"] = formataddr((settings.email_from_name, _sender_email()))
    message["To"] = recipient_email
    message["Reply-To"] = enquiry["email"]

    message.set_content(
        "\n".join(
            [
                "A new franchise enquiry has been submitted.",
                "",
                "Personal Information",
                f"Full Name: {enquiry['full_name']}",
                f"Email Address: {enquiry['email']}",
                f"Phone Number: {enquiry['phone']}",
                f"Country: {enquiry['country']}",
                "",
                "Investment Details",
                f"Level of Interest: {enquiry['level_of_interest']}",
                f"Estimated Investment Capacity: {enquiry['investment_capacity']}",
                "",
                "Additional Information / Questions",
                enquiry.get("additional_info") or "Not provided",
            ]
        )
    )

    if document:
        filename, content, content_type = document
        maintype, _, subtype = (content_type or "application/octet-stream").partition("/")
        if not subtype:
            maintype, subtype = "application", "octet-stream"
        message.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

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


async def send_franchise_enquiry_email(
    enquiry: dict[str, Any],
    document: tuple[str, bytes, str] | None = None,
) -> None:
    message = _build_franchise_enquiry_message(enquiry, document)
    await asyncio.to_thread(_send_email_sync, message)
