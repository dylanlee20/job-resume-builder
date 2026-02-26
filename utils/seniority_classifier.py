"""
Job Type Classification Utility
Classifies jobs as Internship or Full Time based on title and description
"""


def classify_job_type(title, description=''):
    """
    Classify job type based on title and description.

    Args:
        title: Job title
        description: Job description

    Returns:
        str: 'Internship' or 'Full Time'
    """
    text = f"{title} {description}".lower()

    # Internship keywords (internships, campus programs, rotational)
    internship_keywords = [
        'intern',
        'internship',
        'summer analyst',
        'summer associate',
        'graduate program',
        'grad program',
        'trainee',
        'campus',
        'rotational program',
        'off-cycle',
        'spring week',
        'spring intern',
        'winter intern',
        'insight program',
        'insight week',
        'co-op',
        'coop program',
        'placement year',
        'industrial placement',
    ]

    for keyword in internship_keywords:
        if keyword in text:
            return 'Internship'

    return 'Full Time'


# Backwards-compatible alias
def classify_seniority(title, description=''):
    """Legacy alias — maps old values to new job type values."""
    return classify_job_type(title, description)
