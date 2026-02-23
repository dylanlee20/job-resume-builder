"""Resume upload, assessment, builder, and revision routes"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models.database import db
from models.resume import Resume
from models.resume_assessment import ResumeAssessment
from services.resume_parser_service import ResumeParserService
from services.resume_assessment_service import ResumeAssessmentService
from services.resume_builder_service import ResumeBuilderService
from utils.validation import validate_resume_file
from utils.resume_utils import generate_stored_filename, get_upload_path, delete_resume_file
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
resume_bp = Blueprint('resume', __name__, url_prefix='/resume')


# ── Resume Hub ──────────────────────────────────────────────────────

@resume_bp.route('/')
@login_required
def hub():
    """Resume tools hub - choose your mode"""
    recent_resumes = Resume.query.filter_by(
        user_id=current_user.id
    ).order_by(Resume.uploaded_at.desc()).limit(5).all()

    return render_template('resume/hub.html', recent_resumes=recent_resumes)


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

    result = ResumeBuilderService.build_from_scratch(data)

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

    draft_text = data.get('draft_text', '').strip()
    target_industry = data.get('target_industry', '')

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
            file_size = file.tell()

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
def revise(resume_id):
    """Premium: Revise resume with AI-powered improvements and before/after"""
    if not current_user.is_premium():
        return jsonify({
            'success': False,
            'message': 'Resume revision requires a Premium subscription.'
        }), 403

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


@resume_bp.route('/history')
@login_required
def history():
    """View user's resume upload and assessment history"""
    resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.uploaded_at.desc()).all()
    return render_template('resume/history.html', resumes=resumes)
