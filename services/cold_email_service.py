"""Cold email outreach service"""
import logging
import smtplib
import socket
import uuid
import os
import mimetypes
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
from datetime import datetime
import html
from config import Config
from models.database import db
from models.cold_email import EmailCampaign, EmailRecipient
from services.gmail_service import GmailService
from services.outlook_service import OutlookService

logger = logging.getLogger(__name__)


class ColdEmailService:
    """Service for cold email campaigns (paid premium feature)."""

    @staticmethod
    def _validate_sender_profile(user, mode=None):
        """Return None if sender profile is usable, else an error string."""
        if mode == 'gmail':
            if not user.gmail_refresh_token:
                return 'Gmail is not connected. Connect Gmail OAuth in Mailbox Settings.'
            if not (user.gmail_email or user.sender_email):
                return 'Connected Gmail account is missing sender email.'
            return None

        if mode == 'outlook':
            if not user.outlook_refresh_token:
                return 'Outlook is not connected. Connect Outlook OAuth in Mailbox Settings.'
            if not (user.outlook_email or user.sender_email):
                return 'Connected Outlook account is missing sender email.'
            return None

        if mode is None and (user.has_gmail_sender_profile or user.has_outlook_sender_profile):
            return None

        if not user.sender_email:
            return 'Sender email is required.'
        if not user.smtp_host:
            return 'SMTP host is required.'
        if not user.smtp_port:
            return 'SMTP port is required.'
        if not user.smtp_username:
            return 'SMTP username is required.'
        if not user.smtp_password:
            return 'SMTP password/app password is required.'
        return None

    @staticmethod
    def _sender_mode(user):
        """Return active sender mode: gmail, outlook, smtp, or None."""
        if user.has_gmail_sender_profile:
            return 'gmail'
        if user.has_outlook_sender_profile:
            return 'outlook'
        if user.has_smtp_sender_profile:
            return 'smtp'
        return None

    @staticmethod
    def _from_email(user):
        """Return effective sender email address."""
        return (
            user.sender_email
            or user.gmail_email
            or user.outlook_email
            or user.smtp_username
        )

    @staticmethod
    def _open_smtp_connection(user):
        """Create and authenticate an SMTP connection for this user."""
        host = (user.smtp_host or '').strip()
        port = int(user.smtp_port)
        timeout = 30

        addr_info = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        # Prefer IPv4 first because many low-cost VPS setups have broken IPv6 routes.
        addr_info = sorted(
            addr_info,
            key=lambda item: 0 if item[0] == socket.AF_INET else 1
        )

        seen = set()
        last_error = None
        for family, _socktype, _proto, _canonname, sockaddr in addr_info:
            ip_address = sockaddr[0]
            key = (family, ip_address)
            if key in seen:
                continue
            seen.add(key)

            server = smtplib.SMTP(timeout=timeout)
            try:
                # Connect by resolved IP to control IPv4/IPv6 attempt order.
                server.connect(ip_address, port)
                # Keep TLS SNI/cert hostname aligned with the mailbox host.
                server._host = host  # pylint: disable=protected-access
                server.ehlo()
                if user.smtp_use_tls:
                    server.starttls()
                    server.ehlo()
                server.login(user.smtp_username, user.smtp_password)
                return server
            except smtplib.SMTPAuthenticationError:
                try:
                    server.quit()
                except Exception:
                    pass
                raise
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "SMTP connect attempt failed for host=%s ip=%s port=%s: %s",
                    host, ip_address, port, exc
                )
                try:
                    server.quit()
                except Exception:
                    pass

        if last_error:
            raise last_error
        raise ConnectionError(f'Could not resolve/connect SMTP host: {host}:{port}')

    @staticmethod
    def _format_mailbox_connection_error(user, exc):
        """Return a user-facing mailbox connection error with actionable hints."""
        host = (user.smtp_host or '').strip() or 'SMTP host'
        port = user.smtp_port or 'SMTP port'

        if isinstance(exc, socket.gaierror):
            return f'DNS lookup failed for {host}:{port} ({exc}).'

        err_no = getattr(exc, 'errno', None)
        if err_no == 101:
            return (
                f'{exc}. Outbound network route to {host}:{port} is unavailable from the server. '
                'Check VPS outbound firewall/provider SMTP restrictions, or try a provider host with IPv4.'
            )

        if isinstance(exc, (TimeoutError, socket.timeout)):
            return (
                f'Connection to {host}:{port} timed out. '
                'Check SMTP host/port, TLS mode, and VPS outbound firewall rules.'
            )

        return str(exc)

    @staticmethod
    def test_sender_profile(user):
        """
        Validate SMTP settings by opening an authenticated connection.

        Returns:
            Tuple[bool, str | None]
        """
        error = ColdEmailService._validate_sender_profile(user, mode='smtp')
        if error:
            return False, error

        try:
            server = ColdEmailService._open_smtp_connection(user)
            server.quit()
            user.smtp_verified_at = datetime.utcnow()
            db.session.commit()
            return True, None
        except Exception as exc:
            user.smtp_verified_at = None
            db.session.commit()
            return False, ColdEmailService._format_mailbox_connection_error(user, exc)

    @staticmethod
    def _html_with_tracking(body_text, tracking_id):
        """Convert text email body to HTML and append open-tracking pixel."""
        escaped = html.escape(body_text).replace('\n', '<br>\n')
        base_url = (Config.APP_BASE_URL or '').rstrip('/') or 'http://localhost:5000'
        pixel_url = f'{base_url}/outreach/track/{tracking_id}.png'
        pixel = f'<img src="{pixel_url}" width="1" height="1" style="display:none;" alt="">'
        return f'{escaped}<br><br>{pixel}'

    @staticmethod
    def _attach_resume_if_available(msg, campaign):
        """Attach campaign resume when present (file or generated text)."""
        resume = campaign.resume
        if not resume:
            return

        # Prefer original uploaded file if available.
        if resume.file_path and os.path.exists(resume.file_path):
            ctype, _ = mimetypes.guess_type(resume.original_filename or resume.file_path)
            if ctype is None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)

            with open(resume.file_path, 'rb') as file_obj:
                part = MIMEBase(maintype, subtype)
                part.set_payload(file_obj.read())
                encoders.encode_base64(part)
                filename = resume.original_filename or os.path.basename(resume.file_path)
                part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                msg.attach(part)
            return

        # Built/formatted resumes may not have a real file path. Attach text fallback.
        if resume.extracted_text:
            attachment = MIMEText(resume.extracted_text, 'plain', 'utf-8')
            attachment.add_header('Content-Disposition', 'attachment; filename="resume.txt"')
            msg.attach(attachment)

    @staticmethod
    def _build_outlook_attachments(campaign):
        """Build Microsoft Graph fileAttachment objects for campaign resume."""
        resume = campaign.resume
        if not resume:
            return None

        attachments = []
        if resume.file_path and os.path.exists(resume.file_path):
            ctype, _ = mimetypes.guess_type(resume.original_filename or resume.file_path)
            if ctype is None:
                ctype = 'application/octet-stream'
            filename = resume.original_filename or os.path.basename(resume.file_path)
            with open(resume.file_path, 'rb') as file_obj:
                attachments.append({
                    '@odata.type': '#microsoft.graph.fileAttachment',
                    'name': filename,
                    'contentType': ctype,
                    'contentBytes': base64.b64encode(file_obj.read()).decode('utf-8'),
                })
            return attachments

        if resume.extracted_text:
            attachments.append({
                '@odata.type': '#microsoft.graph.fileAttachment',
                'name': 'resume.txt',
                'contentType': 'text/plain',
                'contentBytes': base64.b64encode(resume.extracted_text.encode('utf-8')).decode('utf-8'),
            })
        return attachments or None

    @staticmethod
    def send_campaign(campaign_id, user_id, limit=None):
        """
        Send pending campaign emails through the user's connected mailbox.

        Returns:
            Dict with success flag and send summary.
        """
        campaign = EmailCampaign.query.get(campaign_id)
        if not campaign:
            return {'success': False, 'message': 'Campaign not found.'}
        if campaign.user_id != user_id:
            return {'success': False, 'message': 'Unauthorized campaign access.'}

        user = campaign.user
        mode = ColdEmailService._sender_mode(user)
        error = ColdEmailService._validate_sender_profile(user, mode=mode)
        if error:
            return {
                'success': False,
                'message': f'Sender profile incomplete: {error}',
            }

        pending_q = campaign.recipients.filter_by(status='pending').order_by(EmailRecipient.id.asc())
        if limit and limit > 0:
            recipients = pending_q.limit(limit).all()
        else:
            recipients = pending_q.all()

        if not recipients:
            return {
                'success': True,
                'message': 'No pending recipients to send.',
                'sent': 0,
                'failed': 0,
                'remaining': 0,
            }

        sent = 0
        failed = 0
        failure_samples = []
        campaign.status = 'active'
        db.session.commit()

        server = None
        if mode == 'smtp':
            try:
                server = ColdEmailService._open_smtp_connection(user)
            except Exception as exc:
                return {
                    'success': False,
                    'message': (
                        'Could not connect to your mailbox (SMTP): '
                        f'{ColdEmailService._format_mailbox_connection_error(user, exc)}'
                    ),
                }
        elif mode not in ('gmail', 'outlook'):
            return {
                'success': False,
                'message': 'No mailbox is connected. Connect Gmail OAuth, Outlook OAuth, or SMTP first.',
            }

        try:
            for recipient in recipients:
                try:
                    subject = ColdEmailService.personalize_template(campaign.subject_template, recipient)
                    body_text = ColdEmailService.personalize_template(campaign.body_template, recipient)
                    body_html = ColdEmailService._html_with_tracking(body_text, recipient.tracking_id)

                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = subject
                    from_email = ColdEmailService._from_email(user)
                    msg['From'] = formataddr((user.username, from_email))
                    msg['To'] = recipient.email
                    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
                    msg.attach(MIMEText(body_html, 'html', 'utf-8'))
                    ColdEmailService._attach_resume_if_available(msg, campaign)

                    if mode == 'gmail':
                        GmailService.send_mime_message(user, msg)
                    elif mode == 'outlook':
                        OutlookService.send_email(
                            user=user,
                            to_email=recipient.email,
                            subject=subject,
                            body_html=body_html,
                            attachments=ColdEmailService._build_outlook_attachments(campaign),
                        )
                    else:
                        server.sendmail(from_email, [recipient.email], msg.as_string())

                    recipient.status = 'sent'
                    recipient.sent_at = datetime.utcnow()
                    sent += 1
                except Exception as exc:
                    recipient.status = 'failed'
                    failed += 1
                    if len(failure_samples) < 5:
                        failure_samples.append(f'{recipient.email}: {exc}')
                    logger.error("Failed sending outreach email to %s: %s", recipient.email, exc)

            # Recompute campaign counters from recipient states.
            campaign.total_sent = campaign.recipients.filter(
                EmailRecipient.status.in_(['sent', 'opened', 'replied'])
            ).count()
            campaign.total_opened = campaign.recipients.filter(
                EmailRecipient.status.in_(['opened', 'replied'])
            ).count()
            campaign.total_replied = campaign.recipients.filter_by(status='replied').count()

            remaining = campaign.recipients.filter_by(status='pending').count()
            campaign.status = 'completed' if remaining == 0 else 'active'
            db.session.commit()

            message = f'Sent {sent} email(s)'
            if failed:
                message += f', {failed} failed.'
            else:
                message += ' successfully.'

            return {
                'success': True,
                'message': message,
                'sent': sent,
                'failed': failed,
                'remaining': remaining,
                'failures': failure_samples,
            }
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    @staticmethod
    def create_campaign(user_id, name, subject_template, body_template, resume_id=None):
        """
        Create a new email campaign.

        Args:
            user_id: User ID
            name: Campaign name
            subject_template: Email subject with {{placeholders}}
            body_template: Email body with {{placeholders}}
            resume_id: Optional resume to reference

        Returns:
            EmailCampaign object
        """
        campaign = EmailCampaign(
            user_id=user_id,
            name=name,
            subject_template=subject_template,
            body_template=body_template,
            resume_id=resume_id,
            status='draft'
        )
        db.session.add(campaign)
        db.session.commit()
        return campaign

    @staticmethod
    def add_recipients(campaign_id, recipients_data):
        """
        Add recipients to a campaign.

        Args:
            campaign_id: Campaign ID
            recipients_data: List of dicts with email, name, company, title

        Returns:
            int: Number of recipients added
        """
        added = 0
        for r in recipients_data:
            email = r.get('email', '').strip()
            if not email:
                continue

            # Check for duplicate in this campaign
            existing = EmailRecipient.query.filter_by(
                campaign_id=campaign_id, email=email
            ).first()
            if existing:
                continue

            recipient = EmailRecipient(
                campaign_id=campaign_id,
                email=email,
                name=r.get('name', '').strip(),
                company=r.get('company', '').strip(),
                title=r.get('title', '').strip(),
                tracking_id=uuid.uuid4().hex,
                status='pending'
            )
            db.session.add(recipient)
            added += 1

        db.session.commit()
        return added

    @staticmethod
    def get_campaign_stats(campaign_id):
        """Get campaign statistics"""
        campaign = EmailCampaign.query.get(campaign_id)
        if not campaign:
            return None

        total = campaign.recipients.count()
        sent = campaign.recipients.filter(
            EmailRecipient.status.in_(['sent', 'opened', 'replied'])
        ).count()
        opened = campaign.recipients.filter(
            EmailRecipient.status.in_(['opened', 'replied'])
        ).count()
        replied = campaign.recipients.filter_by(status='replied').count()
        pending = campaign.recipients.filter_by(status='pending').count()

        return {
            'total': total,
            'sent': sent,
            'opened': opened,
            'replied': replied,
            'pending': pending,
            'open_rate': round((opened / sent * 100), 1) if sent > 0 else 0,
            'reply_rate': round((replied / sent * 100), 1) if sent > 0 else 0,
        }

    @staticmethod
    def personalize_template(template, recipient):
        """
        Replace placeholders in template with recipient data.

        Supported placeholders: {{name}}, {{company}}, {{title}}, {{email}}
        """
        result = template
        result = result.replace('{{name}}', recipient.name or 'there')
        result = result.replace('{{company}}', recipient.company or 'your company')
        result = result.replace('{{title}}', recipient.title or '')
        result = result.replace('{{email}}', recipient.email or '')
        # Also support first name
        first_name = (recipient.name or 'there').split()[0] if recipient.name else 'there'
        result = result.replace('{{first_name}}', first_name)
        return result

    @staticmethod
    def mark_opened(tracking_id):
        """Mark recipient as having opened the email"""
        recipient = EmailRecipient.query.filter_by(tracking_id=tracking_id).first()
        if recipient and recipient.status == 'sent':
            recipient.status = 'opened'
            recipient.opened_at = datetime.utcnow()

            # Update campaign stats
            campaign = recipient.campaign
            campaign.total_opened = campaign.recipients.filter(
                EmailRecipient.status.in_(['opened', 'replied'])
            ).count()
            db.session.commit()

        return recipient

    @staticmethod
    def mark_replied(recipient_id):
        """Mark recipient as having replied"""
        recipient = EmailRecipient.query.get(recipient_id)
        if recipient and recipient.status in ('sent', 'opened'):
            recipient.status = 'replied'
            recipient.replied_at = datetime.utcnow()

            campaign = recipient.campaign
            campaign.total_replied = campaign.recipients.filter_by(status='replied').count()
            db.session.commit()

        return recipient
