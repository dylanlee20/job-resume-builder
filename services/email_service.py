"""Email service — sends transactional emails via SMTP.

Supports:
- Email verification on registration
- Resend verification
- (Extensible for password-reset, etc.)
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config import Config

logger = logging.getLogger(__name__)


class EmailService:
    """Thin SMTP wrapper. All methods return (success: bool, error: str | None)."""

    # ------------------------------------------------------------------
    # Low-level send
    # ------------------------------------------------------------------

    @staticmethod
    def _send(to_email: str, subject: str, html_body: str, text_body: str) -> tuple[bool, Optional[str]]:
        """Send a single email. Returns (success, error_message)."""
        if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
            logger.warning(
                "MAIL_USERNAME / MAIL_PASSWORD not configured — email not sent to %s",
                to_email,
            )
            # In development we log the body instead of failing hard
            logger.info("[DEV] Email to %s | Subject: %s", to_email, subject)
            logger.debug("[DEV] Body: %s", text_body)
            return True, None  # Pretend success so registration flow continues

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = Config.MAIL_DEFAULT_SENDER
        msg['To'] = to_email

        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        try:
            with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=15) as server:
                if Config.MAIL_USE_TLS:
                    server.starttls()
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.sendmail(Config.MAIL_DEFAULT_SENDER, [to_email], msg.as_string())
            logger.info("Email sent to %s (subject: %s)", to_email, subject)
            return True, None
        except smtplib.SMTPAuthenticationError:
            err = "SMTP authentication failed — check MAIL_USERNAME and MAIL_PASSWORD"
            logger.error(err)
            return False, err
        except smtplib.SMTPException as exc:
            err = f"SMTP error: {exc}"
            logger.error(err)
            return False, err
        except OSError as exc:
            err = f"Network error sending email: {exc}"
            logger.error(err)
            return False, err

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def send_verification_email(cls, user_email: str, username: str, token: str) -> tuple[bool, Optional[str]]:
        """Send the email-verification link to a newly registered user."""
        verify_url = f"{Config.SITE_URL.rstrip('/')}/auth/verify-email/{token}"

        subject = "Verify your NewWhale Career email address"

        text_body = (
            f"Hi {username},\n\n"
            "Welcome to NewWhale Career! Please verify your email address by visiting:\n"
            f"{verify_url}\n\n"
            f"This link expires in {Config.EMAIL_VERIFICATION_EXPIRY_HOURS} hours.\n\n"
            "If you didn't create an account, you can safely ignore this email.\n\n"
            "— The NewWhale Team"
        )

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #00d4aa;">Welcome to NewWhale Career!</h2>
            <p>Hi <strong>{username}</strong>,</p>
            <p>Thanks for signing up. Please verify your email address to get started.</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{verify_url}"
                   style="background-color: #00d4aa; color: #000; padding: 14px 28px;
                          text-decoration: none; border-radius: 6px; font-weight: bold;
                          display: inline-block;">
                    Verify My Email
                </a>
            </p>
            <p style="color: #888; font-size: 13px;">
                Or copy and paste this link into your browser:<br>
                <a href="{verify_url}" style="color: #00d4aa;">{verify_url}</a>
            </p>
            <p style="color: #888; font-size: 13px;">
                This link expires in {Config.EMAIL_VERIFICATION_EXPIRY_HOURS} hours.
                If you didn't create an account, you can safely ignore this email.
            </p>
            <hr style="border-color: #333;">
            <p style="color: #666; font-size: 12px;">— The NewWhale Career Team</p>
        </body>
        </html>
        """

        return cls._send(user_email, subject, html_body, text_body)

    @classmethod
    def send_resend_verification_email(cls, user_email: str, username: str, token: str) -> tuple[bool, Optional[str]]:
        """Same as send_verification_email but with slightly different copy."""
        return cls.send_verification_email(user_email, username, token)
