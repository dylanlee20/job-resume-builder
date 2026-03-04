"""Cold email outreach routes (paid premium feature)."""
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, session
from flask_login import login_required, current_user
from models.database import db
from models.cold_email import EmailCampaign, EmailRecipient
from models.resume import Resume
from services.cold_email_service import ColdEmailService
from services.gmail_service import GmailService
from utils.feature_access import require_premium_feature
import csv
import io

outreach_bp = Blueprint('outreach', __name__, url_prefix='/outreach')


@outreach_bp.route('/')
@login_required
@require_premium_feature('Cold Email Outreach')
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

    return render_template(
        'outreach/dashboard.html',
        campaigns=campaigns,
        resumes=resumes,
        sender_profile=current_user.sender_profile_summary,
    )


@outreach_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@require_premium_feature('Cold Email Outreach')
def sender_settings():
    """Configure mailbox credentials used for YAMM-style sending."""
    if request.method == 'POST':
        current_user.sender_email = (request.form.get('sender_email') or '').strip()
        current_user.smtp_host = (request.form.get('smtp_host') or '').strip()
        current_user.smtp_port = request.form.get('smtp_port', type=int) or 587
        current_user.smtp_username = (request.form.get('smtp_username') or '').strip()
        current_user.smtp_use_tls = request.form.get('smtp_use_tls') == '1'

        # Only overwrite password when provided.
        new_password = request.form.get('smtp_password', '').strip()
        if new_password:
            current_user.smtp_password = new_password

        db.session.commit()

        if request.form.get('test_connection') == '1':
            ok, err = ColdEmailService.test_sender_profile(current_user)
            if ok:
                flash('Mailbox connected successfully. You can now send campaigns from your own inbox.', 'success')
            else:
                flash(f'Mailbox connection failed: {err}', 'error')
        else:
            flash('Sender settings saved.', 'success')

        return redirect(url_for('outreach.sender_settings'))

    return render_template(
        'outreach/settings.html',
        sender_profile=current_user.sender_profile_summary,
        gmail_oauth_ready=GmailService.is_configured(),
    )


@outreach_bp.route('/gmail/connect')
@login_required
@require_premium_feature('Cold Email Outreach')
def connect_gmail():
    """Start Google OAuth flow to connect Gmail mailbox."""
    if not GmailService.is_configured():
        flash('Google OAuth is not configured on the server. Set GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET.', 'error')
        return redirect(url_for('outreach.sender_settings'))

    state = secrets.token_urlsafe(24)
    session['gmail_oauth_state'] = state
    session['gmail_oauth_user_id'] = current_user.id
    auth_url = GmailService.build_authorization_url(state)
    return redirect(auth_url)


@outreach_bp.route('/gmail/callback')
@login_required
@require_premium_feature('Cold Email Outreach')
def gmail_callback():
    """Handle Google OAuth callback and persist Gmail tokens."""
    expected_state = session.pop('gmail_oauth_state', None)
    oauth_user_id = session.pop('gmail_oauth_user_id', None)
    state = request.args.get('state')

    if not expected_state or state != expected_state or oauth_user_id != current_user.id:
        flash('Invalid Gmail OAuth state. Please try connecting again.', 'error')
        return redirect(url_for('outreach.sender_settings'))

    oauth_error = request.args.get('error')
    if oauth_error:
        flash(f'Gmail connection canceled/failed: {oauth_error}', 'error')
        return redirect(url_for('outreach.sender_settings'))

    code = request.args.get('code')
    if not code:
        flash('Gmail OAuth callback missing authorization code.', 'error')
        return redirect(url_for('outreach.sender_settings'))

    try:
        connected_email = GmailService.connect_user_with_code(current_user, code)
        flash(
            f'Gmail connected successfully ({connected_email}). '
            'Campaigns will now send via Gmail API from your mailbox.',
            'success'
        )
    except Exception as exc:
        flash(f'Gmail connection failed: {exc}', 'error')

    return redirect(url_for('outreach.sender_settings'))


@outreach_bp.route('/gmail/disconnect', methods=['POST'])
@login_required
@require_premium_feature('Cold Email Outreach')
def disconnect_gmail():
    """Disconnect Gmail OAuth credentials for current user."""
    GmailService.disconnect_user(current_user)
    flash('Gmail connection removed.', 'info')
    return redirect(url_for('outreach.sender_settings'))


@outreach_bp.route('/campaign/new', methods=['GET', 'POST'])
@login_required
@require_premium_feature('Cold Email Outreach')
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
@require_premium_feature('Cold Email Outreach')
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
        stats=stats,
        sender_profile=current_user.sender_profile_summary,
    )


@outreach_bp.route('/campaign/<int:campaign_id>/send', methods=['POST'])
@login_required
@require_premium_feature('Cold Email Outreach')
def send_campaign(campaign_id):
    """Send pending emails in a campaign via user's connected mailbox."""
    campaign = EmailCampaign.query.get_or_404(campaign_id)
    if campaign.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    limit = request.form.get('limit', type=int)
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        if not limit:
            limit = payload.get('limit')

    result = ColdEmailService.send_campaign(campaign_id, current_user.id, limit=limit)
    status_code = 200 if result.get('success') else 400

    if request.is_json:
        return jsonify(result), status_code

    if result.get('success'):
        flash(result.get('message', 'Campaign send completed.'), 'success')
        failures = result.get('failures') or []
        if failures:
            flash('Some emails failed: ' + ' | '.join(failures), 'warning')
    else:
        flash(result.get('message', 'Could not send campaign.'), 'error')

    return redirect(url_for('outreach.campaign_detail', campaign_id=campaign_id))


@outreach_bp.route('/campaign/<int:campaign_id>/add-recipients', methods=['POST'])
@login_required
@require_premium_feature('Cold Email Outreach')
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
@require_premium_feature('Cold Email Outreach')
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
@require_premium_feature('Cold Email Outreach')
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
