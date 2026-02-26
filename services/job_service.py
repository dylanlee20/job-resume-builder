"""Job service for business logic and data access"""
from models.database import db
from models.job import Job
from utils.job_utils import categorize_and_classify_job, normalize_location
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func, case
import logging

logger = logging.getLogger(__name__)


class JobService:
    """Service layer for job operations"""
    
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
        
        # Only filter to AI-proof jobs when explicitly requested via checkbox
        if filters.get('ai_proof_only'):
            query = query.filter_by(is_ai_proof=True)
        
        # Apply filters
        if filters.get('company'):
            query = query.filter_by(company=filters['company'])
        
        if filters.get('location'):
            query = query.filter_by(location=filters['location'])
        
        if filters.get('category'):
            query = query.filter_by(category=filters['category'])
        
        if filters.get('ai_proof_category'):
            query = query.filter_by(ai_proof_category=filters['ai_proof_category'])
        
        if filters.get('is_important'):
            query = query.filter_by(is_important=True)
        
        # Sorting
        sort_by = filters.get('sort_by', 'first_seen')
        if sort_by == 'first_seen':
            query = query.order_by(Job.first_seen.desc())
        elif sort_by == 'company':
            query = query.order_by(Job.company.asc())
        
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
        """
        Process a scraped job and classify it as AI-proof or excluded
        
        Args:
            job_data: Dict with job information
        
        Returns:
            Job object or None if duplicate
        """
        # Generate job hash for deduplication
        job_hash = Job.generate_job_hash(
            job_data['company'],
            job_data['title'],
            job_data.get('location', 'Unknown')
        )
        
        # Check if job already exists
        existing_job = Job.query.filter_by(job_hash=job_hash).first()
        
        if existing_job:
            # Update last_seen timestamp
            existing_job.last_seen = datetime.utcnow()
            db.session.commit()
            logger.debug(f"Updated existing job: {existing_job.title}")
            return existing_job
        
        # Classify the job as AI-proof or excluded
        classification = categorize_and_classify_job(
            job_data['title'],
            job_data.get('description', '')
        )
        
        # Normalize location
        normalized_location = normalize_location(job_data.get('location', 'Unknown'))
        
        # Create new job
        new_job = Job(
            job_hash=job_hash,
            company=job_data['company'],
            title=job_data['title'],
            location=normalized_location,
            category=classification['category'],
            ai_proof_category=classification['ai_proof_category'],
            is_ai_proof=classification['is_ai_proof'],
            description=job_data.get('description'),
            description_hash=Job.generate_description_hash(job_data.get('description')),
            post_date=job_data.get('post_date'),
            deadline=job_data.get('deadline'),
            source_website=job_data['source_website'],
            job_url=job_data['job_url'],
            status='active'
        )
        
        db.session.add(new_job)
        db.session.commit()
        
        logger.info(f"Created new job: {new_job.title} [AI-Proof: {new_job.is_ai_proof}]")
        return new_job
    
    @staticmethod
    def get_statistics():
        """Get job statistics (immutable pattern)"""
        total_active = Job.query.filter_by(status='active').count()
        total_ai_proof = Job.query.filter_by(status='active', is_ai_proof=True).count()
        total_excluded = Job.query.filter_by(status='active', is_ai_proof=False).count()

        # Category breakdown
        category_stats = db.session.query(
            Job.ai_proof_category,
            func.count(Job.id).label('count')
        ).filter_by(
            status='active',
            is_ai_proof=True
        ).group_by(Job.ai_proof_category).all()

        # Per-company statistics
        company_stats = db.session.query(
            Job.company,
            func.count(Job.id).label('total'),
            func.sum(func.cast(Job.is_ai_proof, db.Integer)).label('ai_proof'),
            func.sum(
                case(
                    (Job.seniority == 'Internship', 1),
                    else_=0
                )
            ).label('student_grad')
        ).filter_by(
            status='active'
        ).group_by(Job.company).order_by(func.count(Job.id).desc()).all()

        company_list = [
            {
                'company': company,
                'total': total,
                'ai_proof': ai_proof or 0,
                'student_grad': student_grad or 0
            }
            for company, total, ai_proof, student_grad in company_stats
        ]

        return {
            'total_active_jobs': total_active,
            'total_ai_proof_jobs': total_ai_proof,
            'total_excluded_jobs': total_excluded,
            'ai_proof_percentage': round((total_ai_proof / total_active * 100) if total_active > 0 else 0, 1),
            'category_breakdown': {cat: count for cat, count in category_stats},
            'companies': company_list,
        }
    
    @staticmethod
    def get_all_companies(include_excluded=False):
        """Get list of all companies"""
        query = db.session.query(Job.company).filter_by(status='active')
        if not include_excluded:
            query = query.filter_by(is_ai_proof=True)
        companies = query.distinct().all()
        return sorted([c[0] for c in companies if c[0]])

    @staticmethod
    def get_all_locations(include_excluded=False):
        """Get list of all locations"""
        query = db.session.query(Job.location).filter_by(status='active')
        if not include_excluded:
            query = query.filter_by(is_ai_proof=True)
        locations = query.distinct().all()
        return sorted([l[0] for l in locations if l[0]])

    @staticmethod
    def get_all_categories(include_excluded=False):
        """Get list of all categories"""
        from utils.ai_proof_filter import get_ai_proof_category_list, get_excluded_category_list
        categories = list(get_ai_proof_category_list())
        if include_excluded:
            categories.extend(get_excluded_category_list())
            categories.append('EXCLUDED')
        return sorted(set(categories))
