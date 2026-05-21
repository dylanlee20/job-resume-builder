"""Tests for JobService freshness filtering, tab counts, and last-updated lookup."""
from datetime import datetime, timedelta

from models.database import db
from models.job import Job
from models.scraper_run import ScraperRun
from services.job_service import FRESHNESS_WINDOWS, JobService


def _make_job(*, suffix, first_seen):
    job = Job(
        job_hash=f'fresh-{suffix}',
        company='Acme',
        title=f'Title {suffix}',
        location='US - New York',
        source_website='test',
        job_url=f'https://example.com/{suffix}',
        status='active',
        first_seen=first_seen,
        last_seen=first_seen,
        last_updated=first_seen,
    )
    db.session.add(job)
    return job


class TestFreshness:
    def test_window_constants_cover_required_buckets(self):
        assert set(FRESHNESS_WINDOWS) == {'24h', '3d', '7d'}
        assert FRESHNESS_WINDOWS['24h'] == timedelta(hours=24)
        assert FRESHNESS_WINDOWS['3d'] == timedelta(days=3)
        assert FRESHNESS_WINDOWS['7d'] == timedelta(days=7)

    def test_get_freshness_counts_buckets_correctly(self, app, db):
        with app.app_context():
            now = datetime.utcnow()
            for hours, suffix in [(1, 'a'), (12, 'b'), (36, 'c'), (96, 'd'), (200, 'e')]:
                _make_job(suffix=suffix, first_seen=now - timedelta(hours=hours))
            db.session.commit()

            counts = JobService.get_freshness_counts()
            assert counts['all'] == 5
            assert counts['24h'] == 2
            assert counts['3d'] == 3
            assert counts['7d'] == 4

    def test_get_jobs_filters_by_freshness_window(self, app, db):
        with app.app_context():
            now = datetime.utcnow()
            for hours, suffix in [(1, 'a'), (12, 'b'), (36, 'c'), (200, 'd')]:
                _make_job(suffix=suffix, first_seen=now - timedelta(hours=hours))
            db.session.commit()

            assert JobService.get_jobs(filters={'freshness': '24h'}, page=1, per_page=10)['total'] == 2
            assert JobService.get_jobs(filters={'freshness': '3d'}, page=1, per_page=10)['total'] == 3
            assert JobService.get_jobs(filters={'freshness': '7d'}, page=1, per_page=10)['total'] == 3
            assert JobService.get_jobs(filters={}, page=1, per_page=10)['total'] == 4

    def test_get_jobs_ignores_unknown_freshness_value(self, app, db):
        with app.app_context():
            now = datetime.utcnow()
            _make_job(suffix='a', first_seen=now)
            _make_job(suffix='b', first_seen=now - timedelta(days=400))
            db.session.commit()

            assert JobService.get_jobs(filters={'freshness': 'forever'}, page=1, per_page=10)['total'] == 2

    def test_get_last_updated_at_returns_latest_completed(self, app, db):
        with app.app_context():
            now = datetime.utcnow()
            db.session.add(ScraperRun(
                started_at=now - timedelta(hours=2),
                completed_at=now - timedelta(hours=1),
                status='completed',
                trigger='manual',
                duration_seconds=3600,
            ))
            db.session.add(ScraperRun(
                started_at=now - timedelta(minutes=20),
                completed_at=now - timedelta(minutes=5),
                status='completed',
                trigger='scheduled',
                duration_seconds=900,
            ))
            db.session.add(ScraperRun(
                started_at=now - timedelta(minutes=2),
                completed_at=None,
                status='running',
                trigger='manual',
            ))
            db.session.commit()

            last = JobService.get_last_updated_at()
            assert last is not None
            assert (now - last).total_seconds() < 600

    def test_get_last_updated_at_none_when_no_completed_runs(self, app, db):
        with app.app_context():
            assert JobService.get_last_updated_at() is None
