"""Input validation utilities"""
import re
import os
from config import Config


def validate_resume_file(file):
    """
    Validate uploaded resume file
    
    Args:
        file: Flask FileStorage object
    
    Returns:
        Tuple (is_valid: bool, error_message: str or None)
    """
    if not file:
        return (False, "No file provided")
    
    if file.filename == '':
        return (False, "No file selected")
    
    # Check file extension
    filename = file.filename.lower()
    allowed_extensions = Config.ALLOWED_RESUME_EXTENSIONS
    
    if not any(filename.endswith(f'.{ext}') for ext in allowed_extensions):
        return (False, f"File type not allowed. Please upload {', '.join(allowed_extensions)} only.")
    
    # Check file size (read first to get size)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset to beginning
    
    max_size = Config.UPLOAD_MAX_SIZE_MB * 1024 * 1024  # Convert to bytes
    if file_size > max_size:
        return (False, f"File too large. Maximum size is {Config.UPLOAD_MAX_SIZE_MB}MB")
    
    if file_size == 0:
        return (False, "File is empty")
    
    return (True, None)


def validate_email(email):
    """
    Validate email format
    
    Args:
        email: Email string
    
    Returns:
        bool: True if valid
    """
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def sanitize_filename(filename):
    """
    Sanitize filename to prevent path traversal attacks
    
    Args:
        filename: Original filename
    
    Returns:
        str: Sanitized filename
    """
    if not filename:
        return "untitled"
    
    # Remove path components
    filename = os.path.basename(filename)
    
    # Remove or replace unsafe characters
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    
    return filename or "untitled"
