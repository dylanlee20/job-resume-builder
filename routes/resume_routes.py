"""Resume upload and assessment routes"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models.database import db
from models.resume import Resume
from models.resume_assessment import ResumeAssessment
from services.resume_parser_service import ResumeParserService
from services.resume_assessment_service import ResumeAssessmentService
from utils.validation import validate_resume_file
from utils.resume_utils import generate_stored_filename, get_upload_path, delete_resume_file
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
resume_bp = Blueprint('resume', __name__, url_prefix='/resume')


@resume_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Resume upload page"""
    if request.method == 'POST':
        # Check if file was uploaded
        if 'resume_file' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(request.url)
        
        file = request.files['resume_file']
        
        # Validate file
        is_valid, error_msg = validate_resume_file(file)
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(request.url)
        
        try:
            # Generate stored filename
            original_filename = secure_filename(file.filename)
            stored_filename = generate_stored_filename(original_filename)
            file_path = get_upload_path(stored_filename)
            
            # Get file type
            file_type = 'pdf' if original_filename.lower().endswith('.pdf') else 'docx'
            
            # Save file
            file.save(file_path)
            file_size = file.tell()
            
            # Create resume record
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
    
    # GET request - show upload form
    return render_template('resume/upload.html')


@resume_bp.route('/<int:resume_id>/process')
@login_required
def process(resume_id):
    """Process uploaded resume (parse and potentially assess)"""
    resume = Resume.query.get_or_404(resume_id)
    
    # Ensure user owns this resume
    if resume.user_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('resume.upload'))
    
    # Parse resume if not already parsed
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
    
    # Ensure user owns this resume
    if resume.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    # Check if resume is parsed
    if resume.status != 'parsed' or not resume.extracted_text:
        return jsonify({
            'success': False,
            'message': 'Resume must be parsed first'
        }), 400
    
    # Check rate limit
    is_allowed, remaining = ResumeAssessmentService.check_rate_limit(current_user.id)
    if not is_allowed:
        return jsonify({
            'success': False,
            'message': f'Daily assessment limit reached. Upgrade to Premium for unlimited assessments.',
            'remaining': remaining
        }), 429
    
    try:
        # Perform assessment
        assessment_result = ResumeAssessmentService.assess_resume(resume.extracted_text)
        
        if not assessment_result:
            return jsonify({
                'success': False,
                'message': 'Assessment failed. Please try again.'
            }), 500
        
        # Create assessment record
        assessment = ResumeAssessment(
            resume_id=resume.id,
            user_id=current_user.id,
            overall_score=assessment_result['overall_score'],
            assessment_type='free',
            model_used=assessment_result.get('model_used'),
            tokens_used=assessment_result.get('tokens_used', 0),
            detailed_feedback=assessment_result.get('detailed_feedback', '')
        )
        
        # Set JSON fields
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
            'remaining': remaining - 1
        })
        
    except Exception as e:
        logger.error(f"Error assessing resume {resume_id}: {e}")
        return jsonify({
            'success': False,
            'message': 'Assessment failed. Please try again.'
        }), 500


@resume_bp.route('/<int:resume_id>/assessment/<int:assessment_id>')
@login_required
def view_assessment(resume_id, assessment_id):
    """View assessment results"""
    assessment = ResumeAssessment.query.get_or_404(assessment_id)
    
    # Ensure user owns this assessment
    if assessment.user_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('resume.upload'))
    
    return render_template('resume/assessment.html', assessment=assessment)


@resume_bp.route('/history')
@login_required
def history():
    """View user's resume upload and assessment history"""
    resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.uploaded_at.desc()).all()
    return render_template('resume/history.html', resumes=resumes)
