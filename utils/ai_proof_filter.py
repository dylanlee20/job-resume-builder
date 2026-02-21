"""
AI-Proof Job Classification Utility
Classifies finance jobs as AI-proof or excluded based on role requirements
"""
import re


# AI-Proof Categories (roles requiring human judgment and decision-making)
AI_PROOF_CATEGORIES = {
    'Investment Banking': [
        'investment banking', 'M&A', 'mergers and acquisitions', 'capital markets',
        'ECM', 'DCM', 'equity capital markets', 'debt capital markets',
        'corporate finance', 'financial advisory', 'restructuring advisory',
        'leveraged finance', 'sponsor coverage', 'industry coverage'
    ],
    
    'Sales & Trading': [
        'sales and trading', 'trading', 'trader', 'sales trader',
        'equity sales', 'fixed income sales', 'FX sales', 'forex sales',
        'commodities sales', 'derivatives sales', 'structured products',
        'market maker', 'market making', 'flow trading', 'prop trading',
        'proprietary trading', 'execution services', 'agency trading'
    ],
    
    'Portfolio Management': [
        'portfolio management', 'portfolio manager', 'investment management',
        'fund manager', 'asset management', 'wealth management',
        'private wealth', 'family office', 'alternative investments',
        'hedge fund', 'private equity investment', 'venture capital investment',
        'multi-asset', 'equity portfolio', 'fixed income portfolio'
    ],
    
    'Risk Management': [
        'risk management', 'market risk', 'credit risk', 'operational risk',
        'enterprise risk', 'risk analytics', 'stress testing', 'scenario analysis',
        'VaR', 'value at risk', 'CVA', 'credit valuation adjustment',
        'counterparty risk', 'liquidity risk', 'model risk', 'trading risk'
    ],
    
    'M&A Advisory': [
        'M&A advisory', 'merger advisory', 'acquisition advisory',
        'strategic advisory', 'corporate development', 'deal execution',
        'buy-side advisory', 'sell-side advisory', 'fairness opinion',
        'valuation advisory'
    ],
    
    'Private Equity': [
        'private equity', 'PE', 'buyout', 'growth equity',
        'venture capital', 'VC', 'principal investing',
        'direct investment', 'fund investing'
    ],
    
    'Structuring': [
        'structuring', 'structured products', 'derivatives structuring',
        'solutions', 'bespoke solutions', 'quantitative structuring'
    ],
}


# Excluded Categories (roles susceptible to AI automation)
EXCLUDED_CATEGORIES = {
    'Accounting': [
        'accountant', 'accounting', 'bookkeeping', 'accounts payable',
        'accounts receivable', 'general ledger', 'financial reporting analyst',
        'statutory reporting', 'tax reporting', 'GAAP', 'IFRS reporting'
    ],
    
    'Audit': [
        'audit', 'auditor', 'internal audit', 'external audit',
        'sox compliance', 'sarbanes-oxley', 'audit associate',
        'audit senior', 'assurance'
    ],
    
    'Back Office Operations': [
        'back office', 'settlement', 'reconciliation', 'trade support',
        'operations analyst', 'transaction processing', 'clearing',
        'custody', 'fund administration', 'transfer agency'
    ],
    
    'Basic Data Science': [
        'data entry', 'data analyst', 'reporting analyst', 'MIS',
        'management information systems', 'dashboard', 'business intelligence analyst',
        'data visualization', 'reporting coordinator'
    ],
    
    'Compliance Reporting': [
        'compliance reporting', 'regulatory reporting', 'KYC analyst',
        'AML analyst', 'sanctions screening', 'transaction monitoring analyst',
        'compliance associate', 'compliance analyst'
    ],
    
    'Administrative Support': [
        'administrative', 'coordinator', 'executive assistant',
        'office manager', 'receptionist', 'clerk'
    ],
}


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
    
    # Normalize text for matching
    text = f"{title} {description}".lower()
    
    # Check for excluded categories first (higher priority)
    for category, keywords in EXCLUDED_CATEGORIES.items():
        for keyword in keywords:
            if keyword in text:
                # Additional check: ensure it's not a senior role that might be strategic
                # e.g., "Head of Audit" might still require judgment
                if any(senior_term in text for senior_term in ['head of', 'chief', 'director of', 'vp of']):
                    continue  # Skip to AI-proof check
                return (False, 'EXCLUDED')
    
    # Check for AI-proof categories
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
