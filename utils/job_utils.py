"""Job utility functions for categorization and location normalization."""
import re

from utils.ai_proof_filter import classify_ai_proof_role


_REMOTE_TOKENS = {
    'unknown', 'n/a', 'global', 'multiple locations', 'multiple', 'various',
    'worldwide', 'anywhere', 'tbd', 'remote', 'virtual', 'hybrid', 'flexible',
    'work from home', 'americas', 'emea', 'apac', 'asia pacific',
}

_COUNTRY_ALIASES = {
    'us': 'US',
    'usa': 'US',
    'united states': 'US',
    'united states of america': 'US',
    'uk': 'UK',
    'united kingdom': 'UK',
    'england': 'UK',
    'china': 'China',
    'hong kong': 'China',  # keep HK under China for this product's region model
    'japan': 'Japan',
    'south korea': 'South Korea',
    'korea': 'South Korea',
    'singapore': 'Singapore',
    'australia': 'Australia',
    'new zealand': 'New Zealand',
    'india': 'India',
    'france': 'France',
    'germany': 'Germany',
    'switzerland': 'Switzerland',
    'netherlands': 'Netherlands',
    'ireland': 'Ireland',
    'spain': 'Spain',
    'italy': 'Italy',
    'uae': 'UAE',
    'united arab emirates': 'UAE',
    'saudi arabia': 'Saudi Arabia',
    'qatar': 'Qatar',
    'bahrain': 'Bahrain',
    'canada': 'Canada',
    'brazil': 'Brazil',
    'mexico': 'Mexico',
    'argentina': 'Argentina',
}

_US_STATE_CODES = {
    'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga', 'hi', 'id',
    'il', 'in', 'ia', 'ks', 'ky', 'la', 'me', 'md', 'ma', 'mi', 'mn', 'ms',
    'mo', 'mt', 'ne', 'nv', 'nh', 'nj', 'nm', 'ny', 'nc', 'nd', 'oh', 'ok',
    'or', 'pa', 'ri', 'sc', 'sd', 'tn', 'tx', 'ut', 'vt', 'va', 'wa', 'wv',
    'wi', 'wy', 'dc',
}

_US_STATE_NAMES = {
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new hampshire', 'new jersey', 'new mexico', 'new york',
    'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon',
    'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
    'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
    'west virginia', 'wisconsin', 'wyoming', 'district of columbia',
}

_CITY_TO_COUNTRY = {
    'new york': ('US', 'New York'),
    'new york city': ('US', 'New York'),
    'nyc': ('US', 'New York'),
    'jersey city': ('US', 'Jersey City'),
    'boston': ('US', 'Boston'),
    'chicago': ('US', 'Chicago'),
    'los angeles': ('US', 'Los Angeles'),
    'san francisco': ('US', 'San Francisco'),
    'seattle': ('US', 'Seattle'),
    'washington dc': ('US', 'Washington D.C.'),
    'washington d.c.': ('US', 'Washington D.C.'),
    'dc': ('US', 'Washington D.C.'),
    'miami': ('US', 'Miami'),
    'houston': ('US', 'Houston'),
    'dallas': ('US', 'Dallas'),
    'charlotte': ('US', 'Charlotte'),
    'atlanta': ('US', 'Atlanta'),
    'stamford': ('US', 'Stamford'),

    'hong kong': ('China', 'Hong Kong'),
    'central': ('China', 'Hong Kong'),
    'wan chai': ('China', 'Hong Kong'),
    'kowloon': ('China', 'Hong Kong'),

    'beijing': ('China', 'Beijing'),
    'shanghai': ('China', 'Shanghai'),
    'shenzhen': ('China', 'Shenzhen'),

    'tokyo': ('Japan', 'Tokyo'),
    'osaka': ('Japan', 'Osaka'),

    'seoul': ('South Korea', 'Seoul'),

    'singapore': ('Singapore', None),

    'sydney': ('Australia', 'Sydney'),
    'melbourne': ('Australia', 'Melbourne'),
    'brisbane': ('Australia', 'Brisbane'),
    'perth': ('Australia', 'Perth'),

    'auckland': ('New Zealand', 'Auckland'),

    'mumbai': ('India', 'Mumbai'),
    'bangalore': ('India', 'Bangalore'),
    'bengaluru': ('India', 'Bangalore'),
    'pune': ('India', 'Pune'),

    'london': ('UK', 'London'),
    'edinburgh': ('UK', 'Edinburgh'),
    'manchester': ('UK', 'Manchester'),

    'paris': ('France', 'Paris'),
    'frankfurt': ('Germany', 'Frankfurt'),
    'berlin': ('Germany', 'Berlin'),
    'munich': ('Germany', 'Munich'),
    'zurich': ('Switzerland', 'Zurich'),
    'zürich': ('Switzerland', 'Zurich'),
    'amsterdam': ('Netherlands', 'Amsterdam'),
    'dublin': ('Ireland', 'Dublin'),
    'madrid': ('Spain', 'Madrid'),
    'milan': ('Italy', 'Milan'),
    'rome': ('Italy', 'Rome'),

    'dubai': ('UAE', 'Dubai'),
    'abu dhabi': ('UAE', 'Abu Dhabi'),
    'riyadh': ('Saudi Arabia', 'Riyadh'),
    'doha': ('Qatar', 'Doha'),

    'toronto': ('Canada', 'Toronto'),
    'vancouver': ('Canada', 'Vancouver'),
    'montreal': ('Canada', 'Montreal'),
    'calgary': ('Canada', 'Calgary'),
}


def categorize_and_classify_job(title, description=''):
    """Categorize and classify a job using AI-proof filters."""
    is_ai_proof, category = classify_ai_proof_role(title, description)
    return {
        'is_ai_proof': is_ai_proof,
        'ai_proof_category': category if is_ai_proof else 'EXCLUDED',
        'category': category if is_ai_proof else None,
    }


def _normalize_token(value):
    return re.sub(r'\s+', ' ', str(value or '').strip(' ,.')).lower()


def _normalize_country(value):
    token = _normalize_token(value)
    return _COUNTRY_ALIASES.get(token)


def _canonicalize_city(value, expected_country=None):
    token = _normalize_token(value)
    if not token or token in _REMOTE_TOKENS:
        return None

    mapped = _CITY_TO_COUNTRY.get(token)
    if mapped:
        mapped_country, mapped_city = mapped
        if expected_country and mapped_country != expected_country:
            return None
        return mapped_city

    # No lookup hit: preserve user-facing case but normalize spacing.
    city = re.sub(r'\s+', ' ', str(value or '').strip(' ,.'))
    if not city:
        return None
    if _normalize_token(city) in {'dc', 'd.c.', 'washington dc', 'washington d.c.'}:
        return 'Washington D.C.'
    return city.title()


def _clean_location(value):
    text = str(value or '').strip()
    if not text:
        return ''

    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(
        r'\s*\+?\s*\d+\s*(?:more\s+)?locations?\s*$',
        '',
        text,
        flags=re.IGNORECASE,
    ).strip()
    text = text.strip(' ,.')

    # Legacy scraper formats such as "Americas-United States-New York".
    if '-' in text and ',' not in text and text.count('-') >= 2:
        text = text.replace('-', ', ')
        text = re.sub(r'\s+', ' ', text).strip(' ,.')

    for sep in ('|', ';', ' / ', ' & '):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
    text = re.split(r'\s+(?:and|or)\s+', text, maxsplit=1, flags=re.IGNORECASE)[0].strip()

    return text


def parse_country_city(location):
    """
    Parse a location string into `(country, city)`.

    Handles:
    - "Country - City"
    - "City, Country"
    - "City, State" (mapped to US)
    - single known city or country tokens
    """
    value = _clean_location(location)
    if not value:
        return (None, None)

    token = _normalize_token(value)
    if token in _REMOTE_TOKENS:
        return ('Global', None)

    city_hit = _CITY_TO_COUNTRY.get(token)
    if city_hit:
        return city_hit

    country_hit = _normalize_country(token)
    if country_hit:
        return (country_hit, None)

    if ' - ' in value:
        left, right = [part.strip() for part in value.split(' - ', 1)]
        left_country = _normalize_country(left)
        right_country = _normalize_country(right)
        if left_country:
            return (left_country, _canonicalize_city(right, expected_country=left_country))
        if right_country:
            return (right_country, _canonicalize_city(left, expected_country=right_country))

    parts = [part.strip() for part in value.split(',') if part.strip()]
    if len(parts) >= 2:
        first, second, last = parts[0], parts[1], parts[-1]
        last_country = _normalize_country(last)
        if last_country:
            return (last_country, _canonicalize_city(first, expected_country=last_country))

        first_country = _normalize_country(first)
        if first_country:
            return (first_country, _canonicalize_city(second, expected_country=first_country))

        second_token = _normalize_token(second)
        if second_token in _US_STATE_CODES or second_token in _US_STATE_NAMES:
            return ('US', _canonicalize_city(first, expected_country='US'))

    # Support "City ST" (e.g. "New York NY")
    state_suffix_match = re.match(r'^(?P<city>.+?)\s+(?P<state>[A-Za-z]{2})$', value)
    if state_suffix_match:
        state = _normalize_token(state_suffix_match.group('state'))
        if state in _US_STATE_CODES:
            city = state_suffix_match.group('city')
            return ('US', _canonicalize_city(city, expected_country='US'))

    return (None, _canonicalize_city(value))


def normalize_location(location):
    """
    Normalize raw location to one canonical string:
    - "Country - City" when city is available
    - "Country" for country-only
    - "Global" for remote/unknown buckets
    """
    country, city = parse_country_city(location)
    if country == 'Global':
        return 'Global'
    if country and city:
        return f'{country} - {city}'
    if country:
        return country
    if city:
        return city
    return 'Unknown'
