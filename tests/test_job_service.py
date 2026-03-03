"""Tests for job service filtering, sorting, and option providers."""
from datetime import datetime, timedelta

from models.database import db
from models.job import Job
from services.job_service import JobService


def _create_job(
    *,
    company,
    title,
    location,
    is_ai_proof=True,
    ai_proof_category='Investment Banking',
    seniority='Full Time',
    first_seen=None,
    description='',
    is_important=False,
):
    """Create and persist a job row for tests."""
    normalized_first_seen = first_seen or datetime.utcnow()
    job_hash = Job.generate_job_hash(company, title, location)
    job = Job(
        job_hash=job_hash,
        company=company,
        title=title,
        location=location,
        description=description,
        source_website='UnitTest Source',
        job_url=f'https://example.com/{job_hash}',
        status='active',
        is_ai_proof=is_ai_proof,
        ai_proof_category=ai_proof_category,
        seniority=seniority,
        is_important=is_important,
        first_seen=normalized_first_seen,
        last_seen=normalized_first_seen,
        last_updated=normalized_first_seen,
    )
    db.session.add(job)
    db.session.commit()
    return job


class TestJobService:
    def test_job_to_dict_includes_seniority(self, app, db):
        with app.app_context():
            job = _create_job(
                company='Goldman Sachs',
                title='Summer Analyst',
                location='US - New York',
                seniority='Internship',
            )
            payload = job.to_dict()
            assert 'seniority' in payload
            assert payload['seniority'] == 'Internship'

    def test_get_jobs_filters_search_country_city_job_type(self, app, db):
        with app.app_context():
            _create_job(
                company='Goldman Sachs',
                title='Investment Banking Summer Analyst',
                location='US - New York',
                seniority='Internship',
                description='M&A summer internship role',
            )
            _create_job(
                company='JPMorgan',
                title='Risk Manager',
                location='UK - London',
                seniority='Full Time',
                description='Market risk management role',
            )
            _create_job(
                company='Citi',
                title='Operations Analyst',
                location='US - New York',
                is_ai_proof=False,
                ai_proof_category='EXCLUDED',
                seniority='Full Time',
                description='Back office operations',
            )

            result = JobService.get_jobs(
                filters={
                    'q': 'summer',
                    'country': 'US',
                    'city': 'New York',
                    'job_type': 'Internship',
                    'ai_proof_only': True,
                },
                page=1,
                per_page=20,
            )

            assert result['total'] == 1
            assert len(result['jobs']) == 1
            assert result['jobs'][0]['company'] == 'Goldman Sachs'
            assert result['jobs'][0]['seniority'] == 'Internship'

    def test_get_jobs_sorting_variants(self, app, db):
        with app.app_context():
            now = datetime.utcnow()
            _create_job(
                company='B Company',
                title='Analyst',
                location='US - New York',
                first_seen=now - timedelta(days=2),
            )
            _create_job(
                company='A Company',
                title='Associate',
                location='US - New York',
                first_seen=now - timedelta(days=1),
            )
            _create_job(
                company='C Company',
                title='VP',
                location='US - New York',
                first_seen=now,
            )

            newest = JobService.get_jobs(filters={'sort_by': 'newest'}, page=1, per_page=20)
            assert [job['company'] for job in newest['jobs']] == ['C Company', 'A Company', 'B Company']

            oldest = JobService.get_jobs(filters={'sort_by': 'oldest'}, page=1, per_page=20)
            assert [job['company'] for job in oldest['jobs']] == ['B Company', 'A Company', 'C Company']

            company_asc = JobService.get_jobs(filters={'sort_by': 'company_asc'}, page=1, per_page=20)
            assert [job['company'] for job in company_asc['jobs']] == ['A Company', 'B Company', 'C Company']

            company_desc = JobService.get_jobs(filters={'sort_by': 'company_desc'}, page=1, per_page=20)
            assert [job['company'] for job in company_desc['jobs']] == ['C Company', 'B Company', 'A Company']

    def test_get_country_city_job_type_options(self, app, db):
        with app.app_context():
            _create_job(
                company='Goldman Sachs',
                title='Summer Analyst',
                location='US - New York',
                seniority='Internship',
            )
            _create_job(
                company='JPMorgan',
                title='Risk Manager',
                location='UK - London',
                seniority='Full Time',
            )
            _create_job(
                company='Citi',
                title='Operations Analyst',
                location='Japan - Tokyo',
                is_ai_proof=False,
                ai_proof_category='EXCLUDED',
                seniority='Full Time',
            )

            countries_default = JobService.get_all_countries()
            assert countries_default == ['UK', 'US']

            countries_all = JobService.get_all_countries(include_excluded=True)
            assert countries_all == ['Japan', 'UK', 'US']

            us_cities = JobService.get_all_cities(country='US')
            assert us_cities == ['New York']

            all_cities = JobService.get_all_cities(include_excluded=True)
            assert all_cities == ['London', 'New York', 'Tokyo']

            job_types = JobService.get_all_job_types(include_excluded=True)
            assert job_types == ['Internship', 'Full Time']
