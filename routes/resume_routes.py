"""Resume upload, assessment, builder, and revision routes"""
import os
import logging
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models.database import db
from models.resume import Resume
from models.resume_assessment import ResumeAssessment
from models.resume_revision import ResumeRevision
from services.resume_parser_service import ResumeParserService
from services.resume_assessment_service import ResumeAssessmentService
from services.resume_builder_service import ResumeBuilderService
from utils.validation import validate_resume_file
from utils.resume_utils import generate_stored_filename, get_upload_path, delete_resume_file
from utils.feature_access import require_premium_feature

# Maximum character length for text fields sent to LLM
_MAX_TEXT_LEN = 5000

logger = logging.getLogger(__name__)
resume_bp = Blueprint('resume', __name__, url_prefix='/resume')


# ── Resume Hub ──────────────────────────────────────────────────────

@resume_bp.route('/')
@login_required
def hub():
    """Resume tools hub with unified flow and resume cache."""
    resumes = Resume.query.filter_by(
        user_id=current_user.id
    ).order_by(Resume.uploaded_at.desc()).limit(20).all()

    cache_entries = []
    latest_cache = None

    for resume in resumes:
        latest_revision = resume.revisions.order_by(ResumeRevision.created_at.desc()).first()
        latest_assessment = resume.assessments.order_by(ResumeAssessment.created_at.desc()).first()

        revision_at = latest_revision.created_at if latest_revision else None
        has_revision = bool(revision_at and revision_at >= resume.uploaded_at)

        if has_revision:
            preview_text = (latest_revision.revision_suggestions or '').strip()
            source_label = 'revised'
            last_edit_at = revision_at
            latest_revision_id = latest_revision.id
        else:
            preview_text = (resume.extracted_text or '').strip()
            source_label = 'uploaded'
            last_edit_at = resume.uploaded_at
            latest_revision_id = None

        entry = {
            'resume': resume,
            'source_label': source_label,
            'last_edit_at': last_edit_at,
            'preview_text': preview_text[:900],
            'has_preview_text': bool(preview_text),
            'latest_revision_id': latest_revision_id,
            'latest_assessment_id': latest_assessment.id if latest_assessment else None,
        }
        cache_entries.append(entry)

        if not latest_cache or last_edit_at > latest_cache['last_edit_at']:
            latest_cache = entry

    return render_template(
        'resume/hub.html',
        cache_entries=cache_entries,
        latest_cache=latest_cache,
    )


# ── Mode 1: Build from Scratch ─────────────────────────────────────

@resume_bp.route('/build')
@login_required
def build():
    """Guided resume builder form"""
    return render_template('resume/build.html')


@resume_bp.route('/api/build', methods=['POST'])
@login_required
def api_build():
    """API: Generate resume from structured input"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    # Input validation — require full_name, enforce max lengths
    full_name = (data.get('full_name') or '').strip()
    if not full_name:
        return jsonify({'success': False, 'message': 'Full name is required'}), 400

    # Truncate all string values to prevent oversized payloads reaching the LLM
    sanitised = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitised[key] = value[:_MAX_TEXT_LEN]
        elif isinstance(value, list):
            sanitised[key] = [
                (v[:_MAX_TEXT_LEN] if isinstance(v, str) else v)
                for v in value
            ]
        else:
            sanitised[key] = value

    result = ResumeBuilderService.build_from_scratch(sanitised)

    if result['success']:
        # Save the generated resume
        try:
            resume = Resume(
                user_id=current_user.id,
                original_filename='built_resume.txt',
                stored_filename=generate_stored_filename('built_resume.txt'),
                file_path='',
                file_size=len(result['resume_text']),
                file_type='txt',
                extracted_text=result['resume_text'],
                status='parsed'
            )
            db.session.add(resume)
            db.session.commit()
            result['resume_id'] = resume.id
        except Exception as e:
            logger.error(f"Error saving built resume: {e}")

    return jsonify(result)


# ── Mode 2: Format Draft ───────────────────────────────────────────

@resume_bp.route('/format')
@login_required
def format_draft():
    """Format unstructured resume text"""
    return render_template('resume/format_draft.html')


@resume_bp.route('/api/format', methods=['POST'])
@login_required
def api_format():
    """API: Format raw resume text"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    draft_text = (data.get('draft_text') or '').strip()[:_MAX_TEXT_LEN]
    target_industry = (data.get('target_industry') or '').strip()[:200]

    if len(draft_text) < 20:
        return jsonify({'success': False, 'message': 'Please provide more resume text (at least 20 characters)'}), 400

    result = ResumeBuilderService.format_draft(draft_text, target_industry)

    if result['success']:
        # Save the formatted resume
        try:
            resume = Resume(
                user_id=current_user.id,
                original_filename='formatted_resume.txt',
                stored_filename=generate_stored_filename('formatted_resume.txt'),
                file_path='',
                file_size=len(result['formatted_text']),
                file_type='txt',
                extracted_text=result['formatted_text'],
                status='parsed'
            )
            db.session.add(resume)
            db.session.commit()
            result['resume_id'] = resume.id
        except Exception as e:
            logger.error(f"Error saving formatted resume: {e}")

    return jsonify(result)


# ── Brainstorm API ────────────────────────────────────────────────

@resume_bp.route('/api/brainstorm', methods=['POST'])
@login_required
def api_brainstorm():
    """API: Generate bullet-point suggestions for a resume section"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    section = (data.get('section') or '').strip()[:50]
    context = (data.get('context') or '').strip()[:500]
    target_industry = (data.get('target_industry') or '').strip()[:200]

    if section not in ('experience', 'skills'):
        return jsonify({'success': False, 'message': 'Invalid section'}), 400

    result = ResumeBuilderService.brainstorm_bullets(section, context, target_industry)
    return jsonify(result)


# ── Mode 3: Upload & Improve ───────────────────────────────────────

@resume_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Resume upload page"""
    if request.method == 'POST':
        if 'resume_file' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(request.url)

        file = request.files['resume_file']

        is_valid, error_msg = validate_resume_file(file)
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(request.url)

        try:
            original_filename = secure_filename(file.filename)
            stored_filename = generate_stored_filename(original_filename)
            file_path = get_upload_path(stored_filename)

            file_type = 'pdf' if original_filename.lower().endswith('.pdf') else 'docx'

            file.save(file_path)
            file_size = os.path.getsize(file_path)

            resume = Resume(
                user_id=current_user.id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=file_path,
                file_size=file_size,
                file_type=file_type,
                status='uploaded'
            )

            db.session.add(resume)
            db.session.commit()

            flash('Resume uploaded successfully!', 'success')
            return redirect(url_for('resume.process', resume_id=resume.id))

        except Exception as e:
            logger.error(f"Error uploading resume: {e}")
            flash('Error uploading resume. Please try again.', 'error')
            return redirect(request.url)

    return render_template('resume/upload.html')


@resume_bp.route('/<int:resume_id>/process')
@login_required
def process(resume_id):
    """Process uploaded resume (parse and potentially assess)"""
    resume = Resume.query.get_or_404(resume_id)

    if resume.user_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('resume.hub'))

    if resume.status == 'uploaded':
        try:
            extracted_text = ResumeParserService.parse_resume(
                resume.file_path,
                resume.file_type
            )

            if extracted_text:
                resume.extracted_text = extracted_text
                resume.status = 'parsed'
                resume.parsed_at = datetime.utcnow()
                db.session.commit()
                flash('Resume parsed successfully!', 'success')
            else:
                resume.status = 'error'
                db.session.commit()
                flash('Could not parse resume. Please ensure it contains readable text.', 'error')

        except Exception as e:
            logger.error(f"Error parsing resume {resume_id}: {e}")
            resume.status = 'error'
            db.session.commit()
            flash('Error processing resume.', 'error')

    return render_template('resume/process.html', resume=resume)


@resume_bp.route('/<int:resume_id>/assess', methods=['POST'])
@login_required
def assess(resume_id):
    """Trigger free assessment for resume"""
    resume = Resume.query.get_or_404(resume_id)

    if resume.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    if resume.status not in ('parsed', 'assessed') or not resume.extracted_text:
        return jsonify({
            'success': False,
            'message': 'Resume must be parsed first'
        }), 400

    is_allowed, remaining = ResumeAssessmentService.check_rate_limit(current_user.id)
    if not is_allowed:
        return jsonify({
            'success': False,
            'message': 'Daily assessment limit reached. Upgrade to Premium for unlimited assessments.',
            'remaining': remaining
        }), 429

    try:
        assessment_result = ResumeAssessmentService.assess_resume(resume.extracted_text)

        if not assessment_result:
            return jsonify({
                'success': False,
                'message': 'Assessment failed. Please try again.'
            }), 500

        assessment = ResumeAssessment(
            resume_id=resume.id,
            user_id=current_user.id,
            overall_score=assessment_result['overall_score'],
            assessment_type='free',
            model_used=assessment_result.get('model_used'),
            tokens_used=assessment_result.get('tokens_used', 0),
            detailed_feedback=assessment_result.get('detailed_feedback', '')
        )

        assessment.set_strengths(assessment_result.get('strengths', []))
        assessment.set_weaknesses(assessment_result.get('weaknesses', []))
        assessment.set_industry_compatibility(assessment_result.get('industry_compatibility', {}))

        db.session.add(assessment)
        resume.status = 'assessed'
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Assessment completed!',
            'assessment_id': assessment.id,
            'remaining': remaining - 1 if remaining > 0 else 0
        })

    except Exception as e:
        logger.error(f"Error assessing resume {resume_id}: {e}")
        return jsonify({
            'success': False,
            'message': 'Assessment failed. Please try again.'
        }), 500


@resume_bp.route('/<int:resume_id>/revise', methods=['POST'])
@login_required
@require_premium_feature('Resume revision')
def revise(resume_id):
    """Premium: Revise resume with AI-powered improvements and before/after"""
    resume = Resume.query.get_or_404(resume_id)

    if resume.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    if not resume.extracted_text:
        return jsonify({
            'success': False,
            'message': 'Resume text not available for revision'
        }), 400

    # Get latest assessment for context
    latest_assessment = ResumeAssessment.query.filter_by(
        resume_id=resume.id
    ).order_by(ResumeAssessment.created_at.desc()).first()

    assessment_data = latest_assessment.to_dict() if latest_assessment else None

    data = request.get_json() or {}
    target_industry = data.get('target_industry', '')

    result = ResumeBuilderService.revise_resume(
        resume.extracted_text,
        assessment_data=assessment_data,
        target_industry=target_industry
    )

    if result.get('success'):
        try:
            before_score = latest_assessment.overall_score if latest_assessment else None
            projected_after = None
            if before_score is not None:
                projected_after = min(100, before_score + 8)

            revision = ResumeRevision(
                resume_id=resume.id,
                assessment_id=latest_assessment.id if latest_assessment else None,
                user_id=current_user.id,
                target_industry=target_industry or 'Auto-detect',
                templates_used='[]',
                revision_suggestions=result.get('revised_text', ''),
                before_score=before_score,
                projected_after_score=projected_after,
                model_used=result.get('model_used'),
                tokens_used=result.get('tokens_used'),
            )
            db.session.add(revision)
            db.session.commit()
            result['revision_id'] = revision.id
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving revision for resume {resume_id}: {e}")

    return jsonify(result)


@resume_bp.route('/<int:resume_id>/assessment/<int:assessment_id>')
@login_required
def view_assessment(resume_id, assessment_id):
    """View assessment results"""
    assessment = ResumeAssessment.query.get_or_404(assessment_id)

    if assessment.user_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('resume.hub'))

    resume = Resume.query.get_or_404(resume_id)

    return render_template('resume/assessment.html', assessment=assessment, resume=resume)


@resume_bp.route('/<int:resume_id>/revision/<int:revision_id>')
@login_required
def view_revision(resume_id, revision_id):
    """View a cached revised resume snapshot."""
    revision = ResumeRevision.query.get_or_404(revision_id)

    if revision.user_id != current_user.id or revision.resume_id != resume_id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('resume.hub'))

    resume = Resume.query.get_or_404(resume_id)
    return render_template('resume/revision.html', revision=revision, resume=resume)


@resume_bp.route('/history')
@login_required
def history():
    """Legacy route: send users to Resume Tools cache section."""
    return redirect(url_for('resume.hub', _anchor='resume-cache'))
