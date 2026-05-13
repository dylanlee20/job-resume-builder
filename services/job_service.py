"""Job service for business logic and data access"""
from datetime import datetime
import logging

from sqlalchemy import or_, func, case

from models.database import db
from models.job import Job
from utils.job_utils import normalize_location, parse_country_city

logger = logging.getLogger(__name__)


class JobService:
    """Service layer for job operations"""

    @staticmethod
    def _split_location(location):
        """Split any location string into (country, city) using robust parser."""
        country, city = parse_country_city(location)
        return (country or "", city or "")
    
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
        query = Job.query.filter_by(status='active')

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
        
        if filters.get('category'):
            query = query.filter_by(category=filters['category'])

        if filters.get('is_important'):
            query = query.filter_by(is_important=True)
        
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
    def process_scraped_job(job_data):
        """Insert a job from the WhaleStreet CSV (idempotent on (company, title, location) hash)."""
        job_hash = Job.generate_job_hash(
            job_data['company'],
            job_data['title'],
            job_data.get('location', 'Unknown'),
        )

        existing_job = Job.query.filter_by(job_hash=job_hash).first()
        if existing_job:
            existing_job.last_seen = datetime.utcnow()
            db.session.commit()
            return existing_job

        new_job = Job(
            job_hash=job_hash,
            company=job_data['company'],
            title=job_data['title'],
            location=normalize_location(job_data.get('location', 'Unknown')),
            description=job_data.get('description'),
            description_hash=Job.generate_description_hash(job_data.get('description')),
            post_date=job_data.get('post_date'),
            deadline=job_data.get('deadline'),
            source_website=job_data['source_website'],
            job_url=job_data['job_url'],
            status='active',
        )
        db.session.add(new_job)
        db.session.commit()
        logger.info(f"Created new job: {new_job.title} @ {new_job.company}")
        return new_job
    
    @staticmethod
    def get_statistics():
        """Get job statistics (immutable pattern)"""
        total_active = Job.query.filter_by(status='active').count()

        company_stats = db.session.query(
            Job.company,
            func.count(Job.id).label('total'),
            func.sum(
                case(
                    (Job.seniority == 'Internship', 1),
                    else_=0,
                )
            ).label('internship_count'),
        ).filter_by(status='active').group_by(Job.company).order_by(func.count(Job.id).desc()).all()

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
    def get_all_companies():
        rows = db.session.query(Job.company).filter_by(status='active').distinct().all()
        return sorted([c[0] for c in rows if c[0]])

    @staticmethod
    def get_all_locations():
        rows = db.session.query(Job.location).filter_by(status='active').distinct().all()
        return sorted([l[0] for l in rows if l[0]])

    @staticmethod
    def get_all_countries():
        rows = db.session.query(Job.location).filter_by(status='active').distinct().all()
        locations = [l[0] for l in rows if l[0]]
        countries = set()
        for loc in locations:
            country, _ = JobService._split_location(loc)
            if country and country not in {'Global', 'Unknown'}:
                countries.add(country)
        return sorted(countries)

    @staticmethod
    def get_all_cities(country=None):
        rows = db.session.query(Job.location).filter_by(status='active').distinct().all()
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
    def get_all_job_types():
        rows = db.session.query(Job.seniority).filter_by(status='active').distinct().all()
        values = {row[0] for row in rows if row[0]}
        ordered_defaults = [v for v in ('Internship', 'Full Time') if v in values]
        remaining = sorted(values - set(ordered_defaults))
        return ordered_defaults + remaining
