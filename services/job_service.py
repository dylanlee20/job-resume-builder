"""Job service for business logic and data access"""
from datetime import datetime, timedelta
import logging

from sqlalchemy import or_, func, case

from models.database import db
from models.job import Job
from models.scraper_run import ScraperRun
from utils.job_utils import normalize_location, parse_country_city
from utils.ai_proof_filter import classify_ai_proof_role
from utils.seniority_classifier import classify_job_type

logger = logging.getLogger(__name__)


FRESHNESS_WINDOWS = {
    "24h": timedelta(hours=24),
    "3d": timedelta(days=3),
    "7d": timedelta(days=7),
}

# Curated program rows are always front office regardless of their title text.
CURATED_SOURCE = "curated-program"


def _is_truthy(value):
    """Interpret a filter flag that may arrive as a bool or a string."""
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no", "off")
    return bool(value)


class JobService:
    """Service layer for job operations"""

    @staticmethod
    def _split_location(location):
        """Split any location string into (country, city) using robust parser."""
        country, city = parse_country_city(location)
        return (country or "", city or "")

    @staticmethod
    def _front_office_query(include_excluded=False):
        """Base query for active jobs, restricted to front-office roles by default."""
        query = Job.query.filter_by(status='active')
        if not include_excluded:
            query = query.filter(Job.is_ai_proof.is_(True))
        return query
    
    @staticmethod
    def get_jobs(filters=None, page=1, per_page=20):
        """
        Get jobs with filtering (immutable pattern)
        
        Args:
            filters: Dict of filter criteria
            page: Page number
            per_page: Items per page
        
        Returns:
            Dict with jobs list and pagination info
        """
        filters = filters or {}

        # Front-office roles only, unless a caller explicitly opts out. Accept
        # both `ai_proof_only=False` and `include_excluded=True` as the escape.
        include_excluded = _is_truthy(filters.get('include_excluded'))
        if 'ai_proof_only' in filters and not _is_truthy(filters.get('ai_proof_only')):
            include_excluded = True
        query = JobService._front_office_query(include_excluded=include_excluded)

        search_text = (filters.get('q') or filters.get('search') or '').strip()
        if search_text:
            like = f"%{search_text}%"
            query = query.filter(
                or_(
                    Job.company.ilike(like),
                    Job.title.ilike(like),
                    Job.location.ilike(like),
                    Job.description.ilike(like),
                )
            )
        
        # Apply filters
        if filters.get('company'):
            query = query.filter_by(company=filters['company'])

        country = ""
        city = ""
        if filters.get('country'):
            parsed_country, _ = parse_country_city(str(filters['country']).strip())
            country = parsed_country or str(filters['country']).strip()
        if filters.get('city'):
            _, parsed_city = parse_country_city(str(filters['city']).strip())
            city = parsed_city or str(filters['city']).strip()

        # Apply location filters with support for both normalized and legacy formats.
        if country and city:
            conditions = [
                Job.location == f"{country} - {city}",
                Job.location.ilike(f"{country} - {city}%"),
                Job.location.ilike(f"{city}, {country}"),
                Job.location.ilike(f"{city}, {country},%"),
                Job.location.ilike(f"% - {city}"),
                Job.location == city,
            ]
            if country == 'US':
                conditions.append(Job.location.ilike(f"{city}, %"))  # legacy "City, ST"
            query = query.filter(or_(*conditions))
        else:
            if country:
                query = query.filter(
                    or_(
                        Job.location == country,
                        Job.location.ilike(f"{country} - %"),
                        Job.location.ilike(f"%, {country}"),
                        Job.location.ilike(f"%, {country},%"),
                    )
                )

            if city:
                query = query.filter(
                    or_(
                        Job.location == city,
                        Job.location.ilike(f"% - {city}"),
                        Job.location.ilike(f"{city}, %"),
                    )
                )

        if filters.get('location'):
            query = query.filter_by(location=filters['location'])

        if filters.get('job_type'):
            query = query.filter_by(seniority=filters['job_type'])
        
        # "Division" facet maps to the front-office category (ai_proof_category).
        if filters.get('category'):
            query = query.filter(Job.ai_proof_category == filters['category'])

        program = (filters.get('program') or '').strip()
        if program in ('early', 'diversity'):
            query = query.filter(Job.program_type.ilike(f"%{program}%"))

        if filters.get('is_important'):
            query = query.filter_by(is_important=True)

        freshness = (filters.get('freshness') or '').strip()
        if freshness in FRESHNESS_WINDOWS:
            cutoff = datetime.utcnow() - FRESHNESS_WINDOWS[freshness]
            query = query.filter(Job.first_seen >= cutoff)

        # Sorting
        sort_by = filters.get('sort_by', 'newest')
        if sort_by in ('newest', 'first_seen', 'first_seen_desc'):
            query = query.order_by(Job.first_seen.desc())
        elif sort_by in ('oldest', 'first_seen_asc'):
            query = query.order_by(Job.first_seen.asc())
        elif sort_by in ('company', 'company_asc'):
            query = query.order_by(Job.company.asc())
        elif sort_by == 'company_desc':
            query = query.order_by(Job.company.desc())
        elif sort_by == 'post_date_desc':
            query = query.order_by(Job.post_date.desc(), Job.first_seen.desc())
        else:
            query = query.order_by(Job.first_seen.desc())
        
        # Pagination
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'jobs': [job.to_dict() for job in paginated.items],
            'total': paginated.total,
            'pages': paginated.pages,
            'current_page': page,
            'per_page': per_page,
            'has_next': paginated.has_next,
            'has_prev': paginated.has_prev,
        }
    
    @staticmethod
    def classify_job(title, description="", seniority_hint=""):
        """Classify a posting into (is_front_office, division, job_type).

        Shared by the CSV import path and the backfill migration so both stay
        consistent.
        """
        is_front_office, division = classify_ai_proof_role(title, description or "")
        job_type = classify_job_type(title, description or "", seniority_hint or "")
        return is_front_office, division, job_type

    @staticmethod
    def process_scraped_job(job_data):
        """Insert a job from the WhaleStreet CSV (idempotent on (company, title, location) hash)."""
        job_hash = Job.generate_job_hash(
            job_data['company'],
            job_data['title'],
            job_data.get('location', 'Unknown'),
        )

        title = job_data['title']
        description = job_data.get('description') or ''
        seniority_hint = job_data.get('seniority_hint') or ''
        is_front_office, division, job_type = JobService.classify_job(
            title, description, seniority_hint
        )

        existing_job = Job.query.filter_by(job_hash=job_hash).first()
        if existing_job:
            existing_job.last_seen = datetime.utcnow()
            # Re-seeing a previously expired posting reactivates it.
            if existing_job.status != 'active':
                existing_job.status = 'active'
            if job_data.get('program_type') and not existing_job.program_type:
                existing_job.program_type = job_data.get('program_type')
            # Backfill classification for rows ingested before it existed.
            if existing_job.ai_proof_category is None:
                existing_job.is_ai_proof = is_front_office
                existing_job.ai_proof_category = division
                existing_job.category = division if is_front_office else None
            if not existing_job.seniority:
                existing_job.seniority = job_type
            db.session.commit()
            return existing_job

        new_job = Job(
            job_hash=job_hash,
            company=job_data['company'],
            title=title,
            location=normalize_location(job_data.get('location', 'Unknown')),
            category=division if is_front_office else None,
            description=job_data.get('description'),
            description_hash=Job.generate_description_hash(job_data.get('description')),
            is_ai_proof=is_front_office,
            ai_proof_category=division,
            seniority=job_type,
            post_date=job_data.get('post_date'),
            deadline=job_data.get('deadline'),
            source_website=job_data['source_website'],
            job_url=job_data['job_url'],
            program_type=job_data.get('program_type'),
            status='active',
        )
        db.session.add(new_job)
        db.session.commit()
        logger.info(
            f"Created new job: {new_job.title} @ {new_job.company} "
            f"[{division} / {job_type}]"
        )
        return new_job
    
    @staticmethod
    def get_statistics(include_excluded=False):
        """Get job statistics (front-office roles only by default)."""
        base = JobService._front_office_query(include_excluded=include_excluded)
        total_active = base.count()

        company_stats = db.session.query(
            Job.company,
            func.count(Job.id).label('total'),
            func.sum(
                case(
                    (Job.seniority == 'Internship', 1),
                    else_=0,
                )
            ).label('internship_count'),
        )
        company_stats = company_stats.filter(Job.status == 'active')
        if not include_excluded:
            company_stats = company_stats.filter(Job.is_ai_proof.is_(True))
        company_stats = company_stats.group_by(Job.company).order_by(
            func.count(Job.id).desc()
        ).all()

        company_list = [
            {
                'company': company,
                'total': total,
                'internship_count': internship_count or 0,
                'student_grad': internship_count or 0,
            }
            for company, total, internship_count in company_stats
        ]

        return {
            'total_active_jobs': total_active,
            'companies': company_list,
        }

    @staticmethod
    def get_all_companies(include_excluded=False):
        rows = JobService._front_office_query(include_excluded).with_entities(
            Job.company).distinct().all()
        return sorted([c[0] for c in rows if c[0]])

    @staticmethod
    def get_all_locations(include_excluded=False):
        rows = JobService._front_office_query(include_excluded).with_entities(
            Job.location).distinct().all()
        return sorted([l[0] for l in rows if l[0]])

    @staticmethod
    def get_all_categories(include_excluded=False):
        """Distinct front-office divisions present in the active listings."""
        rows = JobService._front_office_query(include_excluded).with_entities(
            Job.ai_proof_category).distinct().all()
        from utils.ai_proof_filter import FRONT_OFFICE_CATEGORIES
        present = {r[0] for r in rows if r[0] and r[0] != 'EXCLUDED'}
        ordered = [c for c in FRONT_OFFICE_CATEGORIES if c in present]
        remaining = sorted(present - set(ordered))
        return ordered + remaining

    @staticmethod
    def get_all_countries(include_excluded=False):
        rows = JobService._front_office_query(include_excluded).with_entities(
            Job.location).distinct().all()
        locations = [l[0] for l in rows if l[0]]
        countries = set()
        for loc in locations:
            country, _ = JobService._split_location(loc)
            if country and country not in {'Global', 'Unknown'}:
                countries.add(country)
        return sorted(countries)

    @staticmethod
    def get_all_cities(country=None, include_excluded=False):
        rows = JobService._front_office_query(include_excluded).with_entities(
            Job.location).distinct().all()
        locations = [l[0] for l in rows if l[0]]
        cities = set()
        country_filter = str(country).strip() if country else ''
        for loc in locations:
            parsed_country, city = JobService._split_location(loc)
            if not city:
                continue
            if country_filter and parsed_country != country_filter:
                continue
            cities.add(city)
        return sorted(cities)

    @staticmethod
    def get_all_job_types(include_excluded=False):
        rows = JobService._front_office_query(include_excluded).with_entities(
            Job.seniority).distinct().all()
        values = {row[0] for row in rows if row[0]}
        ordered_defaults = [v for v in ('Internship', 'Full Time') if v in values]
        remaining = sorted(values - set(ordered_defaults))
        return ordered_defaults + remaining

    @staticmethod
    def get_freshness_counts(include_excluded=False):
        """Front-office active-job counts in each freshness window, plus total."""
        now = datetime.utcnow()
        counts = {'all': JobService._front_office_query(include_excluded).count()}
        for key, delta in FRESHNESS_WINDOWS.items():
            counts[key] = JobService._front_office_query(include_excluded).filter(
                Job.first_seen >= now - delta,
            ).count()
        return counts

    @staticmethod
    def get_program_counts():
        """Active counts of early-career and women/diversity program postings."""
        return {
            'early': Job.query.filter(
                Job.status == 'active', Job.program_type.ilike('%early%')
            ).count(),
            'diversity': Job.query.filter(
                Job.status == 'active', Job.program_type.ilike('%diversity%')
            ).count(),
        }

    @staticmethod
    def get_last_updated_at():
        """Completed_at of the most recent successful scraper run, or None."""
        latest = (
            ScraperRun.query
            .filter(ScraperRun.status == 'completed', ScraperRun.completed_at.isnot(None))
            .order_by(ScraperRun.completed_at.desc())
            .first()
        )
        return latest.completed_at if latest else None
