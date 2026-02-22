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
    Normalize location string to consistent 'Country, City' format.

    Args:
        location: Raw location string from scrapers

    Returns:
        Normalized location string
    """
    import re

    if not location:
        return "Unknown"

    # Strip whitespace, newlines, extra spaces
    location = re.sub(r'\s+', ' ', location.strip())

    # Remove HTML tags if any leaked through
    location = re.sub(r'<[^>]+>', '', location)

    # If multi-location (pipes, semicolons, " and ", " or "), take the first
    for sep in ['|', ';', ' and ', ' or ', ' & ']:
        if sep in location:
            location = location.split(sep)[0].strip()

    # Strip trailing commas or dots
    location = location.strip(' ,.')

    if not location or location.lower() in ('unknown', 'n/a', 'global', 'multiple locations', 'various'):
        return "Global"

    # Exact match lookup (case-insensitive)
    loc_lower = location.lower()

    # City -> "Country, City" mapping
    city_to_country = {
        # United States
        'new york': 'United States, New York',
        'new york, ny': 'United States, New York',
        'new york, new york': 'United States, New York',
        'new york city': 'United States, New York',
        'nyc': 'United States, New York',
        'jersey city': 'United States, Jersey City',
        'jersey city, nj': 'United States, Jersey City',
        'albany': 'United States, Albany',
        'atlanta': 'United States, Atlanta',
        'atlanta, ga': 'United States, Atlanta',
        'boston': 'United States, Boston',
        'boston, ma': 'United States, Boston',
        'chicago': 'United States, Chicago',
        'chicago, il': 'United States, Chicago',
        'dallas': 'United States, Dallas',
        'dallas, tx': 'United States, Dallas',
        'houston': 'United States, Houston',
        'houston, tx': 'United States, Houston',
        'richardson': 'United States, Richardson',
        'detroit': 'United States, Detroit',
        'los angeles': 'United States, Los Angeles',
        'los angeles, ca': 'United States, Los Angeles',
        'menlo park': 'United States, Menlo Park',
        'newport beach': 'United States, Newport Beach',
        'san francisco': 'United States, San Francisco',
        'san francisco, ca': 'United States, San Francisco',
        'miami': 'United States, Miami',
        'miami, fl': 'United States, Miami',
        'west palm beach': 'United States, West Palm Beach',
        'philadelphia': 'United States, Philadelphia',
        'philadelphia, pa': 'United States, Philadelphia',
        'pittsburgh': 'United States, Pittsburgh',
        'pittsburgh, pa': 'United States, Pittsburgh',
        'salt lake city': 'United States, Salt Lake City',
        'seattle': 'United States, Seattle',
        'seattle, wa': 'United States, Seattle',
        'washington': 'United States, Washington D.C.',
        'washington, dc': 'United States, Washington D.C.',
        'washington d.c.': 'United States, Washington D.C.',
        'wilmington': 'United States, Wilmington',
        'wilmington, de': 'United States, Wilmington',
        'charlotte': 'United States, Charlotte',
        'charlotte, nc': 'United States, Charlotte',
        'minneapolis': 'United States, Minneapolis',
        'minneapolis, mn': 'United States, Minneapolis',
        'united states': 'United States',
        'usa': 'United States',
        'us': 'United States',
        # Hong Kong & China
        'hong kong': 'Hong Kong',
        'hong kong sar': 'Hong Kong',
        'hong kong, china': 'Hong Kong',
        'beijing': 'China, Beijing',
        'shanghai': 'China, Shanghai',
        'shenzhen': 'China, Shenzhen',
        'mainland china': 'China',
        'china': 'China',
        # Asia Pacific
        'singapore': 'Singapore',
        'tokyo': 'Japan, Tokyo',
        'minato-ku': 'Japan, Tokyo',
        'seoul': 'South Korea, Seoul',
        'sydney': 'Australia, Sydney',
        'sydney, nsw': 'Australia, Sydney',
        'sydney, nsw, australia': 'Australia, Sydney',
        'melbourne': 'Australia, Melbourne',
        'auckland': 'New Zealand, Auckland',
        'mumbai': 'India, Mumbai',
        # Europe
        'london': 'United Kingdom, London',
        'birmingham': 'United Kingdom, Birmingham',
        'edinburgh': 'United Kingdom, Edinburgh',
        'united kingdom': 'United Kingdom',
        'paris': 'France, Paris',
        'frankfurt': 'Germany, Frankfurt',
        'zurich': 'Switzerland, Zurich',
        'geneva': 'Switzerland, Geneva',
        'amsterdam': 'Netherlands, Amsterdam',
        'dublin': 'Ireland, Dublin',
        'madrid': 'Spain, Madrid',
        'milan': 'Italy, Milan',
        # Middle East
        'dubai': 'UAE, Dubai',
        # Canada
        'toronto': 'Canada, Toronto',
        'calgary': 'Canada, Calgary',
        'montreal': 'Canada, Montreal',
    }

    if loc_lower in city_to_country:
        return city_to_country[loc_lower]

    # Handle patterns like "City, State, United States" or "City, State, US"
    parts = [p.strip() for p in location.split(',')]
    if len(parts) >= 3:
        country_part = parts[-1].strip().lower()
        if country_part in ('united states', 'usa', 'us', 'united states of america'):
            city = parts[0].strip()
            return f"United States, {city}"
        elif country_part in ('australia',):
            city = parts[0].strip()
            return f"Australia, {city}"
        elif country_part in ('canada',):
            city = parts[0].strip()
            return f"Canada, {city}"
        elif country_part in ('united kingdom', 'uk'):
            city = parts[0].strip()
            return f"United Kingdom, {city}"

    # Handle "City, State" (2-part US patterns with state abbreviations)
    if len(parts) == 2:
        us_states = {
            'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga',
            'hi', 'id', 'il', 'in', 'ia', 'ks', 'ky', 'la', 'me', 'md',
            'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv', 'nh', 'nj',
            'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc',
            'sd', 'tn', 'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy', 'dc',
        }
        state_part = parts[1].strip().lower()
        if state_part in us_states:
            city = parts[0].strip()
            return f"United States, {city}"

    # If nothing matched, return cleaned-up original
    return location
