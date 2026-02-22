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
    Normalize location string to consistent 'Country - City' format.

    Args:
        location: Raw location string from scrapers

    Returns:
        Normalized location string (e.g. 'US - New York City', 'China - Hong Kong')
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

    # City -> "Country - City" mapping (comprehensive)
    city_to_country = {
        # === United States ===
        # New York variants
        'new york': 'US - New York',
        'new york, ny': 'US - New York',
        'new york, new york': 'US - New York',
        'new york city': 'US - New York',
        'new york city, ny': 'US - New York',
        'nyc': 'US - New York',
        'ny': 'US - New York',
        'manhattan': 'US - New York',
        'manhattan, ny': 'US - New York',
        'brooklyn': 'US - New York',
        'brooklyn, ny': 'US - New York',
        'new york, united states': 'US - New York',
        'new york, us': 'US - New York',
        'new york, usa': 'US - New York',
        # Jersey City
        'jersey city': 'US - Jersey City',
        'jersey city, nj': 'US - Jersey City',
        'jersey city, new jersey': 'US - Jersey City',
        # Other US cities
        'albany': 'US - Albany',
        'albany, ny': 'US - Albany',
        'atlanta': 'US - Atlanta',
        'atlanta, ga': 'US - Atlanta',
        'atlanta, georgia': 'US - Atlanta',
        'boston': 'US - Boston',
        'boston, ma': 'US - Boston',
        'boston, massachusetts': 'US - Boston',
        'charlotte': 'US - Charlotte',
        'charlotte, nc': 'US - Charlotte',
        'charlotte, north carolina': 'US - Charlotte',
        'chicago': 'US - Chicago',
        'chicago, il': 'US - Chicago',
        'chicago, illinois': 'US - Chicago',
        'dallas': 'US - Dallas',
        'dallas, tx': 'US - Dallas',
        'dallas, texas': 'US - Dallas',
        'denver': 'US - Denver',
        'denver, co': 'US - Denver',
        'denver, colorado': 'US - Denver',
        'detroit': 'US - Detroit',
        'detroit, mi': 'US - Detroit',
        'detroit, michigan': 'US - Detroit',
        'houston': 'US - Houston',
        'houston, tx': 'US - Houston',
        'houston, texas': 'US - Houston',
        'los angeles': 'US - Los Angeles',
        'los angeles, ca': 'US - Los Angeles',
        'los angeles, california': 'US - Los Angeles',
        'la': 'US - Los Angeles',
        'menlo park': 'US - Menlo Park',
        'menlo park, ca': 'US - Menlo Park',
        'miami': 'US - Miami',
        'miami, fl': 'US - Miami',
        'miami, florida': 'US - Miami',
        'minneapolis': 'US - Minneapolis',
        'minneapolis, mn': 'US - Minneapolis',
        'minneapolis, minnesota': 'US - Minneapolis',
        'newport beach': 'US - Newport Beach',
        'newport beach, ca': 'US - Newport Beach',
        'philadelphia': 'US - Philadelphia',
        'philadelphia, pa': 'US - Philadelphia',
        'philadelphia, pennsylvania': 'US - Philadelphia',
        'pittsburgh': 'US - Pittsburgh',
        'pittsburgh, pa': 'US - Pittsburgh',
        'pittsburgh, pennsylvania': 'US - Pittsburgh',
        'richardson': 'US - Richardson',
        'richardson, tx': 'US - Richardson',
        'salt lake city': 'US - Salt Lake City',
        'salt lake city, ut': 'US - Salt Lake City',
        'salt lake city, utah': 'US - Salt Lake City',
        'san francisco': 'US - San Francisco',
        'san francisco, ca': 'US - San Francisco',
        'san francisco, california': 'US - San Francisco',
        'sf': 'US - San Francisco',
        'seattle': 'US - Seattle',
        'seattle, wa': 'US - Seattle',
        'seattle, washington': 'US - Seattle',
        'stamford': 'US - Stamford',
        'stamford, ct': 'US - Stamford',
        'stamford, connecticut': 'US - Stamford',
        'washington': 'US - Washington D.C.',
        'washington, dc': 'US - Washington D.C.',
        'washington, d.c.': 'US - Washington D.C.',
        'washington d.c.': 'US - Washington D.C.',
        'washington dc': 'US - Washington D.C.',
        'dc': 'US - Washington D.C.',
        'd.c.': 'US - Washington D.C.',
        'west palm beach': 'US - West Palm Beach',
        'west palm beach, fl': 'US - West Palm Beach',
        'wilmington': 'US - Wilmington',
        'wilmington, de': 'US - Wilmington',
        'wilmington, delaware': 'US - Wilmington',
        # Country-level US
        'united states': 'US',
        'united states of america': 'US',
        'usa': 'US',
        'us': 'US',

        # === Hong Kong ===
        'hong kong': 'China - Hong Kong',
        'hong kong sar': 'China - Hong Kong',
        'hong kong, china': 'China - Hong Kong',
        'hong kong sar, china': 'China - Hong Kong',
        'hk': 'China - Hong Kong',
        'hkg': 'China - Hong Kong',
        'central': 'China - Hong Kong',
        'central, hong kong': 'China - Hong Kong',
        'wan chai': 'China - Hong Kong',
        'kowloon': 'China - Hong Kong',
        'admiralty': 'China - Hong Kong',
        'quarry bay': 'China - Hong Kong',

        # === China ===
        'beijing': 'China - Beijing',
        'beijing, china': 'China - Beijing',
        'shanghai': 'China - Shanghai',
        'shanghai, china': 'China - Shanghai',
        'shenzhen': 'China - Shenzhen',
        'shenzhen, china': 'China - Shenzhen',
        'mainland china': 'China',
        'china': 'China',

        # === Singapore ===
        'singapore': 'Singapore',
        'sg': 'Singapore',

        # === Japan ===
        'tokyo': 'Japan - Tokyo',
        'tokyo, japan': 'Japan - Tokyo',
        'minato-ku': 'Japan - Tokyo',
        'minato': 'Japan - Tokyo',
        'japan': 'Japan',

        # === South Korea ===
        'seoul': 'South Korea - Seoul',
        'seoul, south korea': 'South Korea - Seoul',
        'south korea': 'South Korea',
        'korea': 'South Korea',

        # === Australia ===
        'sydney': 'Australia - Sydney',
        'sydney, nsw': 'Australia - Sydney',
        'sydney, nsw, australia': 'Australia - Sydney',
        'sydney, australia': 'Australia - Sydney',
        'melbourne': 'Australia - Melbourne',
        'melbourne, vic': 'Australia - Melbourne',
        'melbourne, australia': 'Australia - Melbourne',
        'perth': 'Australia - Perth',
        'brisbane': 'Australia - Brisbane',
        'australia': 'Australia',

        # === New Zealand ===
        'auckland': 'New Zealand - Auckland',
        'new zealand': 'New Zealand',

        # === India ===
        'mumbai': 'India - Mumbai',
        'mumbai, india': 'India - Mumbai',
        'bangalore': 'India - Bangalore',
        'bengaluru': 'India - Bangalore',
        'pune': 'India - Pune',
        'india': 'India',

        # === United Kingdom ===
        'london': 'UK - London',
        'london, uk': 'UK - London',
        'london, united kingdom': 'UK - London',
        'london, england': 'UK - London',
        'birmingham': 'UK - Birmingham',
        'birmingham, uk': 'UK - Birmingham',
        'edinburgh': 'UK - Edinburgh',
        'edinburgh, uk': 'UK - Edinburgh',
        'glasgow': 'UK - Glasgow',
        'manchester': 'UK - Manchester',
        'united kingdom': 'UK',
        'uk': 'UK',
        'england': 'UK',

        # === Europe ===
        'paris': 'France - Paris',
        'paris, france': 'France - Paris',
        'france': 'France',
        'frankfurt': 'Germany - Frankfurt',
        'frankfurt, germany': 'Germany - Frankfurt',
        'frankfurt am main': 'Germany - Frankfurt',
        'munich': 'Germany - Munich',
        'berlin': 'Germany - Berlin',
        'germany': 'Germany',
        'zurich': 'Switzerland - Zurich',
        'zürich': 'Switzerland - Zurich',
        'zurich, switzerland': 'Switzerland - Zurich',
        'geneva': 'Switzerland - Geneva',
        'switzerland': 'Switzerland',
        'amsterdam': 'Netherlands - Amsterdam',
        'amsterdam, netherlands': 'Netherlands - Amsterdam',
        'netherlands': 'Netherlands',
        'dublin': 'Ireland - Dublin',
        'dublin, ireland': 'Ireland - Dublin',
        'ireland': 'Ireland',
        'madrid': 'Spain - Madrid',
        'spain': 'Spain',
        'milan': 'Italy - Milan',
        'milano': 'Italy - Milan',
        'rome': 'Italy - Rome',
        'italy': 'Italy',
        'luxembourg': 'Luxembourg',
        'brussels': 'Belgium - Brussels',
        'belgium': 'Belgium',
        'lisbon': 'Portugal - Lisbon',
        'stockholm': 'Sweden - Stockholm',
        'oslo': 'Norway - Oslo',
        'copenhagen': 'Denmark - Copenhagen',
        'warsaw': 'Poland - Warsaw',
        'prague': 'Czech Republic - Prague',
        'vienna': 'Austria - Vienna',

        # === Middle East ===
        'dubai': 'UAE - Dubai',
        'dubai, uae': 'UAE - Dubai',
        'abu dhabi': 'UAE - Abu Dhabi',
        'uae': 'UAE',
        'united arab emirates': 'UAE',
        'riyadh': 'Saudi Arabia - Riyadh',
        'doha': 'Qatar - Doha',
        'bahrain': 'Bahrain',

        # === Canada ===
        'toronto': 'Canada - Toronto',
        'toronto, on': 'Canada - Toronto',
        'toronto, ontario': 'Canada - Toronto',
        'toronto, canada': 'Canada - Toronto',
        'calgary': 'Canada - Calgary',
        'calgary, ab': 'Canada - Calgary',
        'calgary, alberta': 'Canada - Calgary',
        'montreal': 'Canada - Montreal',
        'montreal, qc': 'Canada - Montreal',
        'vancouver': 'Canada - Vancouver',
        'canada': 'Canada',

        # === Latin America ===
        'sao paulo': 'Brazil - Sao Paulo',
        'são paulo': 'Brazil - Sao Paulo',
        'mexico city': 'Mexico - Mexico City',
        'buenos aires': 'Argentina - Buenos Aires',
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
        'poland', 'czech republic', 'austria', 'argentina',
    }

    country_display = {
        'united states': 'US', 'united states of america': 'US',
        'usa': 'US', 'us': 'US',
        'australia': 'Australia', 'canada': 'Canada',
        'united kingdom': 'UK', 'uk': 'UK', 'england': 'UK',
        'france': 'France', 'germany': 'Germany', 'switzerland': 'Switzerland',
        'netherlands': 'Netherlands', 'ireland': 'Ireland', 'spain': 'Spain',
        'italy': 'Italy', 'japan': 'Japan', 'china': 'China', 'india': 'India',
        'singapore': 'Singapore', 'south korea': 'South Korea',
        'hong kong': 'China', 'new zealand': 'New Zealand',
        'brazil': 'Brazil', 'mexico': 'Mexico',
        'uae': 'UAE', 'united arab emirates': 'UAE',
        'qatar': 'Qatar', 'bahrain': 'Bahrain', 'saudi arabia': 'Saudi Arabia',
        'luxembourg': 'Luxembourg', 'belgium': 'Belgium', 'portugal': 'Portugal',
        'sweden': 'Sweden', 'norway': 'Norway', 'denmark': 'Denmark',
        'poland': 'Poland', 'czech republic': 'Czech Republic', 'austria': 'Austria',
        'argentina': 'Argentina',
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
            return f"{display_country} - {city}"

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
            return f"US - {part0}"

        # "City, Full State Name" (e.g. "Chicago, Illinois")
        if part1_lower in us_state_names:
            city_key = part0_lower
            if city_key in city_to_country:
                return city_to_country[city_key]
            return f"US - {part0}"

        # "City, Country" (e.g. "London, UK" or "Sydney, Australia")
        if part1_lower in country_display:
            display_country = country_display[part1_lower]
            city_key = part0_lower
            if city_key in city_to_country:
                return city_to_country[city_key]
            return f"{display_country} - {part0}"

        # "Country, City" (already in our format — just normalize the country)
        if part0_lower in country_display:
            display_country = country_display[part0_lower]
            city_key = part1_lower
            if city_key in city_to_country:
                return city_to_country[city_key]
            return f"{display_country} - {part1}"

    # Single part: check if it's just a state name (e.g. "New York" the state vs city)
    if len(parts) == 1 and loc_lower in us_state_names and loc_lower not in city_to_country:
        return "US"

    # If nothing matched, return cleaned-up original
    return location
