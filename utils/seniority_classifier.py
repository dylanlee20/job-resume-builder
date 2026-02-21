"""
Seniority Classification Utility
Classifies jobs as Student/Grad or Professional based on title and description
"""

def classify_seniority(title, description=''):
    """
    Classify job seniority level based on title and description

    Args:
        title: Job title
        description: Job description

    Returns:
        str: 'Student/Grad' or 'Professional'
    """
    text = f"{title} {description}".lower()

    # Student/Grad keywords (internships, campus programs, entry-level)
    student_keywords = [
        'intern',
        'internship',
        'summer analyst',
        'summer associate',
        'graduate',
        'grad program',
        'trainee',
        'campus',
        'university',
        'college',
        'undergraduate',
        'mba',
        'student',
        'graduate program',
        'rotational program',
        'off-cycle',
        'spring week',
        'insight',
        'spring intern',
        'winter intern',
        'penultimate',
        'first year',
        'sophomore',
        'junior',
        'senior year'
    ]

    # Check for student/grad keywords
    for keyword in student_keywords:
        if keyword in text:
            return 'Student/Grad'

    # Default to Professional
    return 'Professional'
