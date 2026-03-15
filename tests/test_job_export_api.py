from datetime import datetime

from models.database import db
from models.job import Job
from models.scraper_run import ScraperRun


def create_job(**overrides):
    payload = {
        "job_hash": Job.generate_job_hash("Goldman Sachs", "Investment Banking Summer Analyst", "US - New York"),
        "company": "Goldman Sachs",
        "title": "Investment Banking Summer Analyst",
        "location": "US - New York",
        "category": "Investment Banking",
        "industry": "Finance",
        "description": "Investment banking and capital markets internship.",
        "ai_proof_category": "Investment Banking",
        "is_ai_proof": True,
        "seniority": "Internship",
        "source_website": "Goldman Sachs Careers",
        "job_url": "https://example.com/jobs/1",
        "status": "active",
        "first_seen": datetime.utcnow(),
        "last_seen": datetime.utcnow(),
        "last_updated": datetime.utcnow(),
    }
    payload.update(overrides)
    return Job(**payload)


def test_internal_jobs_export_requires_token(app, client, db):
    with app.app_context():
        db.session.add(create_job())
        db.session.commit()

    response = client.get("/api/internal/jobs-export")
    assert response.status_code == 403
    assert response.get_json()["code"] == "INVALID_JOB_EXPORT_TOKEN"


def test_internal_jobs_export_returns_ai_proof_jobs_only(app, client, db):
    with app.app_context():
        db.session.add(create_job())
        db.session.add(
            create_job(
                job_hash=Job.generate_job_hash("ACME", "Operations Analyst", "US - New York"),
                company="ACME",
                title="Operations Analyst",
                description="Back office operations role.",
                ai_proof_category="EXCLUDED",
                is_ai_proof=False,
                job_url="https://example.com/jobs/2",
            )
        )
        db.session.add(
            ScraperRun(
                status="completed",
                trigger="manual",
                total_jobs_scraped=2,
                new_jobs_added=1,
                jobs_updated=0,
                companies_scraped=1,
                companies_failed=0,
                total_companies=1,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
        )
        db.session.commit()

    response = client.get(
        "/api/internal/jobs-export",
        headers={"Authorization": "Bearer test-job-export-token"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 1
    assert data["ai_proof_only"] is True
    assert data["jobs"][0]["title"] == "Investment Banking Summer Analyst"
    assert data["latest_run"]["status"] == "completed"


def test_internal_jobs_export_can_include_non_ai_proof_jobs(app, client, db):
    with app.app_context():
        db.session.add(create_job())
        db.session.add(
            create_job(
                job_hash=Job.generate_job_hash("RiskCo", "Risk Analyst", "US - Chicago"),
                company="RiskCo",
                title="Risk Analyst",
                location="US - Chicago",
                ai_proof_category="EXCLUDED",
                is_ai_proof=False,
                job_url="https://example.com/jobs/3",
            )
        )
        db.session.commit()

    response = client.get(
        "/api/internal/jobs-export?ai_proof_only=0",
        headers={"Authorization": "Bearer test-job-export-token"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 2
    assert {job["title"] for job in data["jobs"]} == {
        "Investment Banking Summer Analyst",
        "Risk Analyst",
    }
