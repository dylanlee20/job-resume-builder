"""Resume file utility functions"""
import uuid
import os
from config import Config
from utils.validation import sanitize_filename


def generate_stored_filename(original_filename):
    """
    Generate UUID-based stored filename
    
    Args:
        original_filename: Original uploaded filename
    
    Returns:
        str: UUID-based filename with extension
    """
    # Extract extension
    _, ext = os.path.splitext(original_filename)
    
    # Generate UUID
    unique_id = uuid.uuid4().hex
    
    return f"{unique_id}{ext}"


def get_upload_path(stored_filename, upload_type='resumes'):
    """
    Get absolute path for uploaded file
    
    Args:
        stored_filename: UUID-based filename
        upload_type: 'resumes' or 'templates'
    
    Returns:
        str: Absolute file path
    """
    if upload_type == 'resumes':
        base_dir = Config.UPLOAD_FOLDER_RESUMES
    else:
        base_dir = Config.UPLOAD_FOLDER_TEMPLATES
    
    return os.path.join(base_dir, stored_filename)


def delete_resume_file(file_path):
    """
    Safely delete resume file
    
    Args:
        file_path: Absolute path to file
    
    Returns:
        bool: True if deleted successfully
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception:
        return False
