"""Email verification service for user registration"""
import secrets
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from config import Config
from models.database import db
from models.user import User

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending verification and transactional emails"""

    @staticmethod
    def generate_verification_token():
        """Generate a secure, URL-safe verification token"""
        return secrets.token_urlsafe(48)

    @staticmethod
    def send_verification_email(user):
        """
        Generate a verification token and send the verification email.

        Args:
            user: User object (must have email set)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        token = EmailService.generate_verification_token()
        user.email_verification_token = token
        user.email_verification_sent_at = datetime.utcnow()
        db.session.commit()

        verify_url = f"{Config.SITE_URL}/verify-email/{token}"

        subject = "Verify your NewWhale account"
        html_body = f"""
        <div style="max-width: 600px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a2e;">
            <div style="background: #0a1628; padding: 30px; text-align: center;">
                <h1 style="color: #f5a623; margin: 0; font-size: 28px;">NewWhale Career</h1>
                <p style="color: #8899aa; margin: 8px 0 0;">AI-Proof Job Tracker &amp; Resume Tools</p>
            </div>
            <div style="padding: 30px; background: #f8f9fa; border: 1px solid #e0e0e0;">
                <h2 style="margin-top: 0; color: #1a1a2e;">Welcome, {user.username}!</h2>
                <p>Thanks for signing up. Please verify your email address to activate your account.</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verify_url}"
                       style="display: inline-block; background: #f5a623; color: #0a1628; padding: 14px 36px;
                              text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 16px;">
                        Verify Email Address
                    </a>
                </div>
                <p style="color: #666; font-size: 14px;">
                    This link expires in {Config.EMAIL_VERIFICATION_EXPIRY_HOURS} hours.
                    If you didn't create an account, you can safely ignore this email.
                </p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">
                    If the button doesn't work, copy and paste this link into your browser:<br>
                    <a href="{verify_url}" style="color: #f5a623; word-break: break-all;">{verify_url}</a>
                </p>
            </div>
            <div style="padding: 15px; text-align: center; color: #999; font-size: 12px;">
                &copy; NewWhale Career &mdash; newwhaletech.com
            </div>
        </div>
        """

        plain_body = (
            f"Welcome to NewWhale, {user.username}!\n\n"
            f"Please verify your email by visiting this link:\n{verify_url}\n\n"
            f"This link expires in {Config.EMAIL_VERIFICATION_EXPIRY_HOURS} hours.\n"
            f"If you didn't create an account, ignore this email."
        )

        return EmailService._send_email(user.email, subject, html_body, plain_body)

    @staticmethod
    def verify_token(token):
        """
        Verify an email verification token and activate the user.

        Args:
            token: The verification token from the URL

        Returns:
            tuple: (success: bool, message: str, user: User|None)
        """
        user = User.query.filter_by(email_verification_token=token).first()
        if not user:
            return False, 'Invalid or expired verification link.', None

        if user.email_verified:
            return True, 'Your email is already verified. You can sign in.', user

        # Check token expiry
        if user.email_verification_sent_at:
            expiry = user.email_verification_sent_at + timedelta(
                hours=Config.EMAIL_VERIFICATION_EXPIRY_HOURS
            )
            if datetime.utcnow() > expiry:
                return False, 'This verification link has expired. Please request a new one.', user

        user.email_verified = True
        user.email_verification_token = None
        db.session.commit()

        return True, 'Your email has been verified! You can now sign in.', user

    @staticmethod
    def can_resend(user):
        """
        Check if we can resend a verification email (rate limit: 1 per 60 seconds).

        Returns:
            tuple: (can_send: bool, wait_seconds: int)
        """
        if not user.email_verification_sent_at:
            return True, 0

        elapsed = (datetime.utcnow() - user.email_verification_sent_at).total_seconds()
        if elapsed < 60:
            return False, int(60 - elapsed)

        return True, 0

    @staticmethod
    def _send_email(to_email, subject, html_body, plain_body=None):
        """
        Send an email via SMTP.

        Returns:
            bool: True if sent successfully
        """
        if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
            logger.warning(
                "SMTP credentials not configured. Verification email NOT sent to %s. "
                "Set MAIL_USERNAME and MAIL_PASSWORD in .env",
                to_email
            )
            return False

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = Config.MAIL_DEFAULT_SENDER
        msg['To'] = to_email

        if plain_body:
            msg.attach(MIMEText(plain_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        try:
            if Config.MAIL_USE_TLS:
                server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(Config.MAIL_SERVER, Config.MAIL_PORT)

            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.sendmail(Config.MAIL_DEFAULT_SENDER, [to_email], msg.as_string())
            server.quit()
            logger.info("Verification email sent to %s", to_email)
            return True
        except Exception as e:
            logger.error("Failed to send email to %s: %s", to_email, e)
            return False
