import asyncio
from datetime import datetime, timezone
from celery import shared_task
from sqlalchemy import delete
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from src.config.settings import settings
from src.database.session import AsyncSessionLocal
from src.database.models.accounts import ActivationToken, PasswordResetToken
from src.database.models.cart import Cart, CartItem, MoviePurchase
from src.celery_app import celery_app

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=False,
    VALIDATE_CERTS=False,
)


def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@shared_task(name="delete_expired_tokens_task")
def delete_expired_tokens():
    return run_async(_delete_expired_tokens_logic())


async def _delete_expired_tokens_logic():
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        await db.execute(
            delete(ActivationToken).where(ActivationToken.expires_at < now)
        )
        await db.execute(
            delete(PasswordResetToken).where(PasswordResetToken.expires_at < now)
        )
        await db.commit()
        return f"Tokens cleaned at {now}"


@shared_task(name="send_activation_email_task")
def send_activation_email(email: str, token: str):
    return run_async(_send_email_logic(email, token, "activation"))


@shared_task(name="send_reset_password_email_task")
def send_reset_password_email(email: str, token: str):
    return run_async(_send_email_logic(email, token, "reset"))


async def _send_email_logic(email: str, token: str, mode: str):
    if mode == "activation":
        subject = "Account Activation - Online Cinema"
        url = f"http://localhost:8000/accounts/activate/?email={email}&token={token}"
        body = f"""
            <p>Welcome to Online Cinema!</p>
            <p>Please click the link below to activate your account (valid for 24 hours):</p>
            <p><a href='{url}'>Activate Account</a></p>
            <p>If you did not register on our site, please ignore this email.</p>
        """
    else:
        subject = "Password Reset - Online Cinema"
        body = f"""
                <p>You requested a password reset for your Online Cinema account.</p>
                <p>Use this token to reset your password via POST /accounts/password-reset/confirm/:</p>
                <p><b>{token}</b></p>
                <p>Token is valid for 1 hour.</p>
                <p>If you did not request this, please secure your account.</p>
            """

    message = MessageSchema(
        subject=subject, recipients=[email], body=body, subtype=MessageType.html
    )

    fm = FastMail(conf)
    await fm.send_message(message)
    return f"Email ({mode}) sent to {email}"
