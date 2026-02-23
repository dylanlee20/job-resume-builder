"""
AI-Proof Job Classification Utility
Classifies finance jobs as AI-proof or excluded based on role requirements
"""
import re


# Technology/Engineering keywords — checked against TITLE ONLY to exclude tech roles
# before they can match finance keywords in the description
TECH_TITLE_KEYWORDS = [
    'software engineer', 'software developer', 'sre', 'site reliability',
    'devops', 'platform engineer', 'infrastructure engineer', 'cloud engineer',
    'backend engineer', 'frontend engineer', 'full stack', 'fullstack',
    'data engineer', 'machine learning engineer', 'ml engineer', 'ai engineer',
    'systems engineer', 'network engineer', 'security engineer',
    'solutions architect', 'cloud architect', 'systems architect',
    'web developer', 'mobile developer', 'ios developer', 'android developer',
    'qa engineer', 'test engineer', 'automation engineer',
    'technical program manager', 'engineering manager',
    'scrum master', 'product owner', 'ux designer', 'ui designer',
    'database administrator', 'dba',
]


# AI-Proof Categories (roles requiring human judgment and decision-making)
# All keywords are lowercase for case-insensitive matching
AI_PROOF_CATEGORIES = {
    'Investment Banking': [
        'investment banking', 'investment banker',
        'm&a', 'mergers and acquisitions',
        'capital markets', 'ecm', 'dcm',
        'equity capital markets', 'debt capital markets',
        'corporate finance', 'financial advisory', 'restructuring advisory',
        'leveraged finance', 'sponsor coverage', 'industry coverage',
        'pitchbook', 'pitch book',
    ],

    'Sales & Trading': [
        'sales and trading', 'sales & trading',
        'sales trader', 'equity sales', 'fixed income sales',
        'fx sales', 'forex sales', 'commodities sales', 'derivatives sales',
        'market maker', 'market making',
        'flow trading', 'prop trading', 'proprietary trading',
        'execution services', 'agency trading',
        'rates trader', 'credit trader', 'equity trader',
        'commodity trader', 'fx trader', 'forex trader',
        'options trader', 'futures trader', 'bond trader',
    ],

    'Asset Management': [
        'portfolio management', 'portfolio manager',
        'investment management', 'investment manager',
        'fund manager', 'asset management', 'asset manager',
        'wealth management', 'wealth manager', 'wealth advisor',
        'private wealth', 'family office', 'alternative investments',
        'hedge fund', 'private equity investment', 'venture capital investment',
        'multi-asset', 'equity portfolio', 'fixed income portfolio',
    ],

    'Risk Management': [
        'risk management', 'risk manager', 'risk analyst',
        'market risk', 'credit risk', 'operational risk',
        'enterprise risk', 'risk analytics', 'stress testing', 'scenario analysis',
        'var', 'value at risk', 'cva', 'credit valuation adjustment',
        'counterparty risk', 'liquidity risk', 'model risk', 'trading risk',
    ],

    'M&A Advisory': [
        'm&a advisory', 'merger advisory', 'acquisition advisory',
        'strategic advisory', 'corporate development', 'deal execution',
        'buy-side advisory', 'sell-side advisory', 'fairness opinion',
        'valuation advisory',
    ],

    'Private Equity': [
        'private equity', 'buyout', 'growth equity',
        'venture capital', 'principal investing',
        'direct investment', 'fund investing',
    ],

    'Structuring': [
        'derivatives structuring', 'structured products',
        'quantitative structuring', 'equity structuring',
        'credit structuring', 'rates structuring',
        'fx structuring', 'commodity structuring',
    ],
}


# Excluded Categories (roles susceptible to AI automation)
EXCLUDED_CATEGORIES = {
    'Accounting': [
        'accountant', 'accounting', 'bookkeeping', 'accounts payable',
        'accounts receivable', 'general ledger', 'financial reporting analyst',
        'statutory reporting', 'tax reporting', 'gaap', 'ifrs reporting',
    ],

    'Audit': [
        'audit', 'auditor', 'internal audit', 'external audit',
        'sox compliance', 'sarbanes-oxley', 'audit associate',
        'audit senior', 'assurance',
    ],

    'Back Office Operations': [
        'back office', 'settlement', 'reconciliation', 'trade support',
        'operations analyst', 'transaction processing', 'clearing',
        'custody', 'fund administration', 'transfer agency',
    ],

    'Basic Data Science': [
        'data entry', 'data analyst', 'reporting analyst',
        'management information systems', 'dashboard',
        'business intelligence analyst', 'data visualization',
        'reporting coordinator',
    ],

    'Compliance Reporting': [
        'compliance reporting', 'regulatory reporting', 'kyc analyst',
        'aml analyst', 'sanctions screening', 'transaction monitoring analyst',
        'compliance associate', 'compliance analyst',
    ],

    'Administrative Support': [
        'administrative', 'coordinator', 'executive assistant',
        'office manager', 'receptionist', 'clerk',
    ],

    'Technology & Engineering': [
        'software engineer', 'software developer', 'developer',
        'programmer', 'devops', 'site reliability',
        'platform engineer', 'infrastructure engineer', 'cloud engineer',
        'backend engineer', 'frontend engineer', 'full stack engineer',
        'data engineer', 'machine learning engineer', 'ml engineer',
        'systems engineer', 'network engineer', 'security engineer',
        'solutions architect', 'cloud architect', 'systems architect',
        'web developer', 'mobile developer',
        'qa engineer', 'test engineer', 'automation engineer',
        'database administrator', 'sre',
        'technical support', 'it support', 'help desk',
    ],
}


def _is_tech_title(title_lower):
    """Check if the job title indicates a technology/engineering role"""
    for keyword in TECH_TITLE_KEYWORDS:
        if keyword in title_lower:
            return True
    return False


def classify_ai_proof_role(title, description=''):
    """
    Classify a job as AI-proof or excluded based on title and description

    Args:
        title: Job title string
        description: Job description string (optional)

    Returns:
        Tuple (is_ai_proof: bool, category: str)
        - is_ai_proof: True if role is AI-proof, False if excluded
        - category: The specific category name or 'EXCLUDED'
    """
    if not title:
        return (False, 'EXCLUDED')

    title_lower = title.lower()
    # Use title + description for keyword matching
    text = f"{title} {description}".lower()

    # FIRST: Check if title is clearly a tech/engineering role
    # Tech roles should be excluded even if description mentions trading/finance
    if _is_tech_title(title_lower):
        return (False, 'EXCLUDED')

    # Check for excluded categories (higher priority)
    for category, keywords in EXCLUDED_CATEGORIES.items():
        for keyword in keywords:
            if keyword in text:
                # Senior roles (Head of, Chief, Director, VP) may be strategic
                if any(senior_term in text for senior_term in ['head of', 'chief', 'director of', 'vp of']):
                    continue  # Skip to AI-proof check
                return (False, 'EXCLUDED')

    # Check for AI-proof categories (match against TITLE primarily)
    # First pass: check title only (strongest signal)
    for category, keywords in AI_PROOF_CATEGORIES.items():
        for keyword in keywords:
            if keyword in title_lower:
                return (True, category)

    # Second pass: check full text (title + description) for broader matching
    for category, keywords in AI_PROOF_CATEGORIES.items():
        for keyword in keywords:
            if keyword in text:
                return (True, category)

    # Default: if no match, consider it excluded (conservative approach)
    return (False, 'EXCLUDED')


def get_ai_proof_category_list():
    """Get list of all AI-proof category names"""
    return list(AI_PROOF_CATEGORIES.keys())


def get_excluded_category_list():
    """Get list of all excluded category names"""
    return list(EXCLUDED_CATEGORIES.keys())
