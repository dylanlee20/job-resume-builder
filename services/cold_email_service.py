"""Cold email outreach service"""
import logging
import smtplib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import Config
from models.database import db
from models.cold_email import EmailCampaign, EmailRecipient

logger = logging.getLogger(__name__)


class ColdEmailService:
    """Service for cold email campaigns (annual plan only)"""

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
        sent = campaign.recipients.filter_by(status='sent').count()
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
