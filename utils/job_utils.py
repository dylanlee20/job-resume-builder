"""Job utility functions for categorization and processing"""
from utils.ai_proof_filter import classify_ai_proof_role


def categorize_and_classify_job(title, description=''):
    """
    Categorize and classify a job using AI-proof filter
    
    Args:
        title: Job title
        description: Job description
    
    Returns:
        Dict with keys: is_ai_proof, ai_proof_category
    """
    is_ai_proof, category = classify_ai_proof_role(title, description)
    
    return {
        'is_ai_proof': is_ai_proof,
        'ai_proof_category': category if is_ai_proof else 'EXCLUDED',
        'category': category if is_ai_proof else None
    }


def normalize_location(location):
    """
    Normalize location string to consistent format
    (Will reuse logic from v1)
    
    Args:
        location: Raw location string
    
    Returns:
        Normalized location string
    """
    if not location:
        return "Unknown"
    
    # Basic normalization for now (can enhance later)
    location = location.strip()
    
    # Common mappings
    location_map = {
        'New York': 'United States, New York',
        'Hong Kong': 'China, Hong Kong',
        'Singapore': 'Singapore',
        'London': 'United Kingdom, London',
        'Tokyo': 'Japan, Tokyo',
    }
    
    return location_map.get(location, location)
