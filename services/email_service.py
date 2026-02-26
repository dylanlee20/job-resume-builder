"""Email service — sends transactional emails via Resend API.

Supports:
- Email verification on registration
- Resend verification
- (Extensible for password-reset, etc.)
"""
import logging
from typing import Optional

import resend

from config import Config

logger = logging.getLogger(__name__)


class EmailService:
    """Thin Resend wrapper. All methods return (success: bool, error: str | None)."""

    # ------------------------------------------------------------------
    # Low-level send
    # ------------------------------------------------------------------

    @staticmethod
    def _send(to_email: str, subject: str, html_body: str) -> tuple[bool, Optional[str]]:
        """Send a single email via Resend. Returns (success, error_message)."""
        if not Config.RESEND_API_KEY:
            logger.warning("RESEND_API_KEY not configured — email not sent to %s", to_email)
            logger.info("[DEV] Email to %s | Subject: %s", to_email, subject)
            return True, None  # Dev mode: pretend success

        resend.api_key = Config.RESEND_API_KEY

        try:
            result = resend.Emails.send({
                "from": Config.FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            })
            email_id = result.get('id', 'unknown') if isinstance(result, dict) else getattr(result, 'id', 'unknown')
            logger.info("Email sent to %s (id: %s, subject: %s)", to_email, email_id, subject)
            return True, None
        except resend.exceptions.ResendError as exc:
            err = f"Resend API error: {exc}"
            logger.error(err)
            return False, err
        except Exception as exc:
            err = f"Email send error: {exc}"
            logger.error(err)
            return False, err

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def send_verification_email(
        cls, to_email: str, username: str, verify_url: str
    ) -> tuple[bool, Optional[str]]:
        """Send the email-verification link to a newly registered user."""
        subject = "Verify your NewWhale Career email address"
        expiry = Config.EMAIL_VERIFICATION_EXPIRY_MINUTES

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
                This link expires in {expiry} minutes.
                If you didn't create an account, you can safely ignore this email.
            </p>
            <hr style="border-color: #333;">
            <p style="color: #666; font-size: 12px;">&mdash; The NewWhale Career Team</p>
        </body>
        </html>
        """

        return cls._send(to_email, subject, html_body)
