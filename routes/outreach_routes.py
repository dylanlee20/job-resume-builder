"""Cold email outreach routes (annual plan only)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from models.database import db
from models.cold_email import EmailCampaign, EmailRecipient
from models.resume import Resume
from services.cold_email_service import ColdEmailService
import logging
import csv
import io

logger = logging.getLogger(__name__)

outreach_bp = Blueprint('outreach', __name__, url_prefix='/outreach')


def require_annual_plan(f):
    """Decorator to restrict access to annual plan subscribers"""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_premium:
            flash('Cold Email Outreach requires a Premium Annual subscription.', 'error')
            return redirect(url_for('web.pricing'))
        return f(*args, **kwargs)
    return decorated


@outreach_bp.route('/')
@login_required
@require_annual_plan
def dashboard():
    """Cold email outreach dashboard"""
    campaigns = EmailCampaign.query.filter_by(
        user_id=current_user.id
    ).order_by(EmailCampaign.created_at.desc()).all()

    # Get user's resumes for selection
    resumes = Resume.query.filter_by(
        user_id=current_user.id
    ).filter(Resume.status.in_(['parsed', 'assessed'])).order_by(
        Resume.uploaded_at.desc()
    ).all()

    return render_template('outreach/dashboard.html', campaigns=campaigns, resumes=resumes)


@outreach_bp.route('/campaign/new', methods=['GET', 'POST'])
@login_required
@require_annual_plan
def new_campaign():
    """Create a new email campaign"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()
        resume_id = request.form.get('resume_id', type=int)

        if not name or not subject or not body:
            flash('Please fill in all required fields.', 'error')
        else:
            campaign = ColdEmailService.create_campaign(
                user_id=current_user.id,
                name=name,
                subject_template=subject,
                body_template=body,
                resume_id=resume_id
            )
            flash(f'Campaign "{name}" created! Now add recipients.', 'success')
            return redirect(url_for('outreach.campaign_detail', campaign_id=campaign.id))

    resumes = Resume.query.filter_by(
        user_id=current_user.id
    ).filter(Resume.status.in_(['parsed', 'assessed'])).order_by(
        Resume.uploaded_at.desc()
    ).all()

    return render_template('outreach/new_campaign.html', resumes=resumes)


@outreach_bp.route('/campaign/<int:campaign_id>')
@login_required
@require_annual_plan
def campaign_detail(campaign_id):
    """View campaign details and recipients"""
    campaign = EmailCampaign.query.get_or_404(campaign_id)
    if campaign.user_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('outreach.dashboard'))

    recipients = campaign.recipients.order_by(EmailRecipient.created_at.desc()).all()
    stats = ColdEmailService.get_campaign_stats(campaign_id)

    return render_template(
        'outreach/campaign_detail.html',
        campaign=campaign,
        recipients=recipients,
        stats=stats
    )


@outreach_bp.route('/campaign/<int:campaign_id>/add-recipients', methods=['POST'])
@login_required
@require_annual_plan
def add_recipients(campaign_id):
    """Add recipients to campaign (JSON or CSV)"""
    campaign = EmailCampaign.query.get_or_404(campaign_id)
    if campaign.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    content_type = request.content_type or ''

    if 'application/json' in content_type:
        data = request.get_json()
        recipients = data.get('recipients', [])
    else:
        # Handle form data or CSV
        recipients = []

        # Check for CSV file
        if 'csv_file' in request.files:
            csv_file = request.files['csv_file']
            if csv_file.filename:
                stream = io.StringIO(csv_file.stream.read().decode('utf-8'))
                reader = csv.DictReader(stream)
                for row in reader:
                    recipients.append({
                        'email': row.get('email', row.get('Email', '')),
                        'name': row.get('name', row.get('Name', '')),
                        'company': row.get('company', row.get('Company', '')),
                        'title': row.get('title', row.get('Title', '')),
                    })

        # Check for single recipient form
        single_email = request.form.get('email', '').strip()
        if single_email:
            recipients.append({
                'email': single_email,
                'name': request.form.get('name', ''),
                'company': request.form.get('company', ''),
                'title': request.form.get('title', ''),
            })

    if not recipients:
        if 'application/json' in content_type:
            return jsonify({'success': False, 'message': 'No recipients provided'}), 400
        flash('No recipients to add.', 'error')
        return redirect(url_for('outreach.campaign_detail', campaign_id=campaign_id))

    added = ColdEmailService.add_recipients(campaign_id, recipients)

    if 'application/json' in content_type:
        return jsonify({'success': True, 'added': added})

    flash(f'{added} recipient(s) added successfully!', 'success')
    return redirect(url_for('outreach.campaign_detail', campaign_id=campaign_id))


@outreach_bp.route('/campaign/<int:campaign_id>/preview')
@login_required
@require_annual_plan
def preview_email(campaign_id):
    """Preview personalized email for a recipient"""
    campaign = EmailCampaign.query.get_or_404(campaign_id)
    if campaign.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    recipient_id = request.args.get('recipient_id', type=int)
    if recipient_id:
        recipient = EmailRecipient.query.get(recipient_id)
    else:
        recipient = campaign.recipients.first()

    if not recipient:
        return jsonify({'success': False, 'message': 'No recipients found'})

    subject = ColdEmailService.personalize_template(campaign.subject_template, recipient)
    body = ColdEmailService.personalize_template(campaign.body_template, recipient)

    return jsonify({
        'success': True,
        'subject': subject,
        'body': body,
        'recipient': recipient.to_dict()
    })


@outreach_bp.route('/campaign/<int:campaign_id>/recipient/<int:recipient_id>/mark-replied', methods=['POST'])
@login_required
@require_annual_plan
def mark_replied(campaign_id, recipient_id):
    """Manually mark a recipient as having replied"""
    campaign = EmailCampaign.query.get_or_404(campaign_id)
    if campaign.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    recipient = ColdEmailService.mark_replied(recipient_id)
    if recipient:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Recipient not found'}), 404


@outreach_bp.route('/track/<tracking_id>.png')
def track_open(tracking_id):
    """Tracking pixel endpoint - records email opens"""
    ColdEmailService.mark_opened(tracking_id)

    # Return 1x1 transparent PNG
    pixel = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
        b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
        b'\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    return Response(pixel, mimetype='image/png')
