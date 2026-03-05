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

    @classmethod
    def send_coffee_chat_booking_created(
        cls,
        to_email: str,
        recipient_name: str,
        counterpart_name: str,
        schedule_text: str,
    ) -> tuple[bool, Optional[str]]:
        """Notify user that a coffee chat booking was created and awaits payment confirmation."""
        subject = "Coffee Chat Booking Created (Pending Payment)"
        html_body = f"""
        <html><body style="font-family: Arial, sans-serif;">
            <h3>Coffee chat booking created</h3>
            <p>Hi {recipient_name},</p>
            <p>A mentorship booking with <strong>{counterpart_name}</strong> was created.</p>
            <p><strong>Schedule:</strong> {schedule_text}</p>
            <p>Status: <strong>Pending payment</strong>. You will receive a confirmation email when payment succeeds.</p>
            <hr>
            <p style="font-size: 12px; color: #666;">
                Mentorship sessions are strictly for career guidance and educational purposes.
                No investment, financial, or trading advice is provided.
            </p>
        </body></html>
        """
        return cls._send(to_email, subject, html_body)

    @classmethod
    def send_coffee_chat_booking_confirmed(
        cls,
        to_email: str,
        recipient_name: str,
        counterpart_name: str,
        schedule_text: str,
        meeting_url: str,
    ) -> tuple[bool, Optional[str]]:
        """Notify user that coffee chat payment succeeded and session is confirmed."""
        subject = "Coffee Chat Confirmed"
        html_body = f"""
        <html><body style="font-family: Arial, sans-serif;">
            <h3>Your coffee chat is confirmed</h3>
            <p>Hi {recipient_name},</p>
            <p>Your mentorship session with <strong>{counterpart_name}</strong> is now confirmed.</p>
            <p><strong>Schedule:</strong> {schedule_text}</p>
            <p><strong>Meeting link:</strong> <a href="{meeting_url}">{meeting_url}</a></p>
            <hr>
            <p style="font-size: 12px; color: #666;">
                The platform does not provide financial advice and is not responsible
                for statements made during mentorship sessions.
            </p>
        </body></html>
        """
        return cls._send(to_email, subject, html_body)

    @classmethod
    def send_coffee_chat_session_reminder(
        cls,
        to_email: str,
        recipient_name: str,
        counterpart_name: str,
        schedule_text: str,
        meeting_url: str,
    ) -> tuple[bool, Optional[str]]:
        """Send upcoming session reminder."""
        subject = "Coffee Chat Reminder"
        html_body = f"""
        <html><body style="font-family: Arial, sans-serif;">
            <h3>Session reminder</h3>
            <p>Hi {recipient_name},</p>
            <p>This is a reminder for your mentorship session with <strong>{counterpart_name}</strong>.</p>
            <p><strong>Schedule:</strong> {schedule_text}</p>
            <p><strong>Meeting link:</strong> <a href="{meeting_url}">{meeting_url}</a></p>
            <p>See you soon.</p>
        </body></html>
        """
        return cls._send(to_email, subject, html_body)
