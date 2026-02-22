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

    # Replace dash separators with commas (e.g. "Americas-United States-New York")
    if '-' in location and ',' not in location:
        location = location.replace('-', ', ')
        location = re.sub(r'\s+', ' ', location).strip()

    # Strip trailing "+N locations" or "+N more" patterns (e.g. "New York +2 locations")
    location = re.sub(r'\s*\+?\s*\d+\s*(?:more\s+)?locations?\s*$', '', location, flags=re.IGNORECASE).strip()

    # If the entire string is just "N locations" or "N+ locations" with nothing useful, treat as Global
    if re.match(r'^\d+\s*\+?\s*(?:more\s+)?locations?\s*$', location, flags=re.IGNORECASE):
        return "Global"

    # If multi-location (pipes, semicolons, " and ", " or "), take the first
    for sep in ['|', ';', ' and ', ' or ', ' & ']:
        if sep in location:
            location = location.split(sep)[0].strip()

    # Strip zip/postal codes (e.g. "New York, NY 10019" → "New York, NY")
    location = re.sub(r'\s+\d{5}(?:-\d{4})?\s*$', '', location).strip()

    # Strip trailing commas or dots
    location = location.strip(' ,.')

    if not location or location.lower() in ('unknown', 'n/a', 'global', 'multiple locations', 'various',
                                              'multiple', 'worldwide', 'anywhere', 'tbd', 'remote',
                                              'virtual', 'hybrid', 'flexible', 'work from home',
                                              'americas', 'emea', 'apac', 'asia pacific'):
        return "Global"

    # Exact match lookup (case-insensitive)
    loc_lower = location.lower()

    # City -> "Country, City" mapping (comprehensive)
    city_to_country = {
        # === United States ===
        # New York variants
        'new york': 'United States, New York',
        'new york, ny': 'United States, New York',
        'new york, new york': 'United States, New York',
        'new york city': 'United States, New York',
        'new york city, ny': 'United States, New York',
        'nyc': 'United States, New York',
        'ny': 'United States, New York',
        'manhattan': 'United States, New York',
        'manhattan, ny': 'United States, New York',
        'brooklyn': 'United States, New York',
        'brooklyn, ny': 'United States, New York',
        'new york, united states': 'United States, New York',
        'new york, us': 'United States, New York',
        'new york, usa': 'United States, New York',
        # Jersey City
        'jersey city': 'United States, Jersey City',
        'jersey city, nj': 'United States, Jersey City',
        'jersey city, new jersey': 'United States, Jersey City',
        # Other US cities
        'albany': 'United States, Albany',
        'albany, ny': 'United States, Albany',
        'atlanta': 'United States, Atlanta',
        'atlanta, ga': 'United States, Atlanta',
        'atlanta, georgia': 'United States, Atlanta',
        'boston': 'United States, Boston',
        'boston, ma': 'United States, Boston',
        'boston, massachusetts': 'United States, Boston',
        'charlotte': 'United States, Charlotte',
        'charlotte, nc': 'United States, Charlotte',
        'charlotte, north carolina': 'United States, Charlotte',
        'chicago': 'United States, Chicago',
        'chicago, il': 'United States, Chicago',
        'chicago, illinois': 'United States, Chicago',
        'dallas': 'United States, Dallas',
        'dallas, tx': 'United States, Dallas',
        'dallas, texas': 'United States, Dallas',
        'denver': 'United States, Denver',
        'denver, co': 'United States, Denver',
        'denver, colorado': 'United States, Denver',
        'detroit': 'United States, Detroit',
        'detroit, mi': 'United States, Detroit',
        'detroit, michigan': 'United States, Detroit',
        'houston': 'United States, Houston',
        'houston, tx': 'United States, Houston',
        'houston, texas': 'United States, Houston',
        'los angeles': 'United States, Los Angeles',
        'los angeles, ca': 'United States, Los Angeles',
        'los angeles, california': 'United States, Los Angeles',
        'la': 'United States, Los Angeles',
        'menlo park': 'United States, Menlo Park',
        'menlo park, ca': 'United States, Menlo Park',
        'miami': 'United States, Miami',
        'miami, fl': 'United States, Miami',
        'miami, florida': 'United States, Miami',
        'minneapolis': 'United States, Minneapolis',
        'minneapolis, mn': 'United States, Minneapolis',
        'minneapolis, minnesota': 'United States, Minneapolis',
        'newport beach': 'United States, Newport Beach',
        'newport beach, ca': 'United States, Newport Beach',
        'philadelphia': 'United States, Philadelphia',
        'philadelphia, pa': 'United States, Philadelphia',
        'philadelphia, pennsylvania': 'United States, Philadelphia',
        'pittsburgh': 'United States, Pittsburgh',
        'pittsburgh, pa': 'United States, Pittsburgh',
        'pittsburgh, pennsylvania': 'United States, Pittsburgh',
        'richardson': 'United States, Richardson',
        'richardson, tx': 'United States, Richardson',
        'salt lake city': 'United States, Salt Lake City',
        'salt lake city, ut': 'United States, Salt Lake City',
        'salt lake city, utah': 'United States, Salt Lake City',
        'san francisco': 'United States, San Francisco',
        'san francisco, ca': 'United States, San Francisco',
        'san francisco, california': 'United States, San Francisco',
        'sf': 'United States, San Francisco',
        'seattle': 'United States, Seattle',
        'seattle, wa': 'United States, Seattle',
        'seattle, washington': 'United States, Seattle',
        'stamford': 'United States, Stamford',
        'stamford, ct': 'United States, Stamford',
        'stamford, connecticut': 'United States, Stamford',
        'washington': 'United States, Washington D.C.',
        'washington, dc': 'United States, Washington D.C.',
        'washington, d.c.': 'United States, Washington D.C.',
        'washington d.c.': 'United States, Washington D.C.',
        'washington dc': 'United States, Washington D.C.',
        'dc': 'United States, Washington D.C.',
        'd.c.': 'United States, Washington D.C.',
        'west palm beach': 'United States, West Palm Beach',
        'west palm beach, fl': 'United States, West Palm Beach',
        'wilmington': 'United States, Wilmington',
        'wilmington, de': 'United States, Wilmington',
        'wilmington, delaware': 'United States, Wilmington',
        # Country-level US
        'united states': 'United States',
        'united states of america': 'United States',
        'usa': 'United States',
        'us': 'United States',

        # === Hong Kong ===
        'hong kong': 'Hong Kong',
        'hong kong sar': 'Hong Kong',
        'hong kong, china': 'Hong Kong',
        'hong kong sar, china': 'Hong Kong',
        'hk': 'Hong Kong',
        'hkg': 'Hong Kong',
        'central': 'Hong Kong',
        'central, hong kong': 'Hong Kong',
        'wan chai': 'Hong Kong',
        'kowloon': 'Hong Kong',
        'admiralty': 'Hong Kong',
        'quarry bay': 'Hong Kong',

        # === China ===
        'beijing': 'China, Beijing',
        'beijing, china': 'China, Beijing',
        'shanghai': 'China, Shanghai',
        'shanghai, china': 'China, Shanghai',
        'shenzhen': 'China, Shenzhen',
        'shenzhen, china': 'China, Shenzhen',
        'mainland china': 'China',
        'china': 'China',

        # === Singapore ===
        'singapore': 'Singapore',
        'sg': 'Singapore',

        # === Japan ===
        'tokyo': 'Japan, Tokyo',
        'tokyo, japan': 'Japan, Tokyo',
        'minato-ku': 'Japan, Tokyo',
        'minato': 'Japan, Tokyo',
        'japan': 'Japan',

        # === South Korea ===
        'seoul': 'South Korea, Seoul',
        'seoul, south korea': 'South Korea, Seoul',
        'south korea': 'South Korea',
        'korea': 'South Korea',

        # === Australia ===
        'sydney': 'Australia, Sydney',
        'sydney, nsw': 'Australia, Sydney',
        'sydney, nsw, australia': 'Australia, Sydney',
        'sydney, australia': 'Australia, Sydney',
        'melbourne': 'Australia, Melbourne',
        'melbourne, vic': 'Australia, Melbourne',
        'melbourne, australia': 'Australia, Melbourne',
        'perth': 'Australia, Perth',
        'brisbane': 'Australia, Brisbane',
        'australia': 'Australia',

        # === New Zealand ===
        'auckland': 'New Zealand, Auckland',
        'new zealand': 'New Zealand',

        # === India ===
        'mumbai': 'India, Mumbai',
        'mumbai, india': 'India, Mumbai',
        'bangalore': 'India, Bangalore',
        'bengaluru': 'India, Bangalore',
        'pune': 'India, Pune',
        'india': 'India',

        # === United Kingdom ===
        'london': 'United Kingdom, London',
        'london, uk': 'United Kingdom, London',
        'london, united kingdom': 'United Kingdom, London',
        'london, england': 'United Kingdom, London',
        'birmingham': 'United Kingdom, Birmingham',
        'birmingham, uk': 'United Kingdom, Birmingham',
        'edinburgh': 'United Kingdom, Edinburgh',
        'edinburgh, uk': 'United Kingdom, Edinburgh',
        'glasgow': 'United Kingdom, Glasgow',
        'manchester': 'United Kingdom, Manchester',
        'united kingdom': 'United Kingdom',
        'uk': 'United Kingdom',
        'england': 'United Kingdom',

        # === Europe ===
        'paris': 'France, Paris',
        'paris, france': 'France, Paris',
        'france': 'France',
        'frankfurt': 'Germany, Frankfurt',
        'frankfurt, germany': 'Germany, Frankfurt',
        'frankfurt am main': 'Germany, Frankfurt',
        'munich': 'Germany, Munich',
        'berlin': 'Germany, Berlin',
        'germany': 'Germany',
        'zurich': 'Switzerland, Zurich',
        'zürich': 'Switzerland, Zurich',
        'zurich, switzerland': 'Switzerland, Zurich',
        'geneva': 'Switzerland, Geneva',
        'switzerland': 'Switzerland',
        'amsterdam': 'Netherlands, Amsterdam',
        'amsterdam, netherlands': 'Netherlands, Amsterdam',
        'netherlands': 'Netherlands',
        'dublin': 'Ireland, Dublin',
        'dublin, ireland': 'Ireland, Dublin',
        'ireland': 'Ireland',
        'madrid': 'Spain, Madrid',
        'spain': 'Spain',
        'milan': 'Italy, Milan',
        'milano': 'Italy, Milan',
        'rome': 'Italy, Rome',
        'italy': 'Italy',
        'luxembourg': 'Luxembourg',
        'brussels': 'Belgium, Brussels',
        'belgium': 'Belgium',
        'lisbon': 'Portugal, Lisbon',
        'stockholm': 'Sweden, Stockholm',
        'oslo': 'Norway, Oslo',
        'copenhagen': 'Denmark, Copenhagen',
        'warsaw': 'Poland, Warsaw',
        'prague': 'Czech Republic, Prague',
        'vienna': 'Austria, Vienna',

        # === Middle East ===
        'dubai': 'UAE, Dubai',
        'dubai, uae': 'UAE, Dubai',
        'abu dhabi': 'UAE, Abu Dhabi',
        'uae': 'UAE',
        'united arab emirates': 'UAE',
        'riyadh': 'Saudi Arabia, Riyadh',
        'doha': 'Qatar, Doha',
        'bahrain': 'Bahrain',

        # === Canada ===
        'toronto': 'Canada, Toronto',
        'toronto, on': 'Canada, Toronto',
        'toronto, ontario': 'Canada, Toronto',
        'toronto, canada': 'Canada, Toronto',
        'calgary': 'Canada, Calgary',
        'calgary, ab': 'Canada, Calgary',
        'calgary, alberta': 'Canada, Calgary',
        'montreal': 'Canada, Montreal',
        'montreal, qc': 'Canada, Montreal',
        'vancouver': 'Canada, Vancouver',
        'canada': 'Canada',

        # === Latin America ===
        'sao paulo': 'Brazil, Sao Paulo',
        'são paulo': 'Brazil, Sao Paulo',
        'mexico city': 'Mexico, Mexico City',
        'buenos aires': 'Argentina, Buenos Aires',
    }

    if loc_lower in city_to_country:
        return city_to_country[loc_lower]

    # US state abbreviation to full name mapping (for pattern matching)
    us_state_abbrevs = {
        'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga',
        'hi', 'id', 'il', 'in', 'ia', 'ks', 'ky', 'la', 'me', 'md',
        'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv', 'nh', 'nj',
        'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc',
        'sd', 'tn', 'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy', 'dc',
    }

    us_state_names = {
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

    country_names = {
        'united states', 'united states of america', 'usa', 'us',
        'australia', 'canada', 'united kingdom', 'uk', 'england',
        'france', 'germany', 'switzerland', 'netherlands', 'ireland',
        'spain', 'italy', 'japan', 'china', 'india', 'singapore',
        'south korea', 'hong kong', 'new zealand', 'brazil', 'mexico',
        'uae', 'united arab emirates', 'qatar', 'bahrain', 'saudi arabia',
        'luxembourg', 'belgium', 'portugal', 'sweden', 'norway', 'denmark',
        'poland', 'czech republic', 'austria',
    }

    country_display = {
        'united states': 'United States', 'united states of america': 'United States',
        'usa': 'United States', 'us': 'United States',
        'australia': 'Australia', 'canada': 'Canada',
        'united kingdom': 'United Kingdom', 'uk': 'United Kingdom', 'england': 'United Kingdom',
        'france': 'France', 'germany': 'Germany', 'switzerland': 'Switzerland',
        'netherlands': 'Netherlands', 'ireland': 'Ireland', 'spain': 'Spain',
        'italy': 'Italy', 'japan': 'Japan', 'china': 'China', 'india': 'India',
        'singapore': 'Singapore', 'south korea': 'South Korea',
        'hong kong': 'Hong Kong', 'new zealand': 'New Zealand',
        'brazil': 'Brazil', 'mexico': 'Mexico',
        'uae': 'UAE', 'united arab emirates': 'UAE',
        'qatar': 'Qatar', 'bahrain': 'Bahrain', 'saudi arabia': 'Saudi Arabia',
        'luxembourg': 'Luxembourg', 'belgium': 'Belgium', 'portugal': 'Portugal',
        'sweden': 'Sweden', 'norway': 'Norway', 'denmark': 'Denmark',
        'poland': 'Poland', 'czech republic': 'Czech Republic', 'austria': 'Austria',
    }

    # Split on commas for multi-part patterns
    parts = [p.strip() for p in location.split(',')]

    # Strip zip codes from last part (e.g. "NY 10019" → "NY")
    if parts:
        parts[-1] = re.sub(r'\s+\d{5}(?:-\d{4})?$', '', parts[-1]).strip()

    # Handle 3+ part patterns: "City, State, Country"
    if len(parts) >= 3:
        country_part = parts[-1].strip().lower()
        city = parts[0].strip()
        if country_part in country_display:
            display_country = country_display[country_part]
            # Re-normalize: look up city in our table to get canonical name
            city_key = city.lower()
            if city_key in city_to_country:
                return city_to_country[city_key]
            return f"{display_country}, {city}"

    # Handle 2-part patterns
    if len(parts) == 2:
        part0 = parts[0].strip()
        part1 = parts[1].strip()
        part0_lower = part0.lower()
        part1_lower = part1.lower()

        # "City, State Abbreviation" (e.g. "Chicago, IL")
        if part1_lower in us_state_abbrevs:
            # Re-normalize city through lookup
            city_key = part0_lower
            if city_key in city_to_country:
                return city_to_country[city_key]
            return f"United States, {part0}"

        # "City, Full State Name" (e.g. "Chicago, Illinois")
        if part1_lower in us_state_names:
            city_key = part0_lower
            if city_key in city_to_country:
                return city_to_country[city_key]
            return f"United States, {part0}"

        # "City, Country" (e.g. "London, UK" or "Sydney, Australia")
        if part1_lower in country_display:
            display_country = country_display[part1_lower]
            city_key = part0_lower
            if city_key in city_to_country:
                return city_to_country[city_key]
            return f"{display_country}, {part0}"

        # "Country, City" (already in our format — just normalize the country)
        if part0_lower in country_display:
            display_country = country_display[part0_lower]
            city_key = part1_lower
            if city_key in city_to_country:
                return city_to_country[city_key]
            return f"{display_country}, {part1}"

    # Single part: check if it's just a state name (e.g. "New York" the state vs city)
    if len(parts) == 1 and loc_lower in us_state_names and loc_lower not in city_to_country:
        return "United States"

    # If nothing matched, return cleaned-up original
    return location
