"""End-to-end smoke test for the CSV import -> classification pipeline."""
import csv

from services.csv_import_service import CSVImportService
from services.job_service import JobService


def _write_csv(path):
    fields = ["company_name", "job_title", "job_url", "location", "department",
              "date_posted", "job_type", "seniority_level", "source_url",
              "scrape_timestamp", "scrape_status", "error_message"]
    rows = [
        ["Goldman Sachs", "Investment Banking Summer Analyst", "https://x/1", "New York, NY", "Investment Banking", "2026-07-05", "", "intern", "https://gs.com", "", "success", ""],
        ["Citadel", "Quantitative Researcher", "https://x/2", "Chicago, IL", "Research", "2026-07-06", "Full Time", "", "https://citadel.com", "", "success", ""],
        ["JPMorgan", "Software Engineer", "https://x/3", "London, United Kingdom", "Technology", "2026-07-04", "", "", "https://jpm.com", "", "success", ""],
        ["Morgan Stanley", "Operations Analyst", "https://x/4", "Hong Kong", "Operations", "2026-07-01", "", "", "https://ms.com", "", "success", ""],
        ["Barclays", "Equity Sales Trader", "https://x/5", "New York, NY", "Markets", "2026-07-06", "", "", "https://barclays.com", "", "success", ""],
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(dict(zip(fields, r)))


def test_import_classifies_and_filters(app, db, tmp_path, monkeypatch):
    csv_path = tmp_path / "jobs_finance.csv"
    _write_csv(csv_path)
    monkeypatch.setenv("JOBS_CSV_PATH", str(csv_path))

    with app.app_context():
        stats = CSVImportService.import_all()
        assert stats["ingested"] == 5

        # Software Engineer + Operations Analyst are excluded from the default view.
        visible = JobService.get_jobs(filters={}, page=1, per_page=50)
        companies = sorted(j["company"] for j in visible["jobs"])
        assert companies == ["Barclays", "Citadel", "Goldman Sachs"]

        # Divisions are set for front-office roles.
        divisions = JobService.get_all_categories()
        assert "Investment Banking" in divisions
        assert "Quant" in divisions
        assert "Sales & Trading" in divisions

        # Internship vs Full Time split.
        interns = JobService.get_jobs(filters={"job_type": "Internship"}, page=1, per_page=50)
        assert [j["company"] for j in interns["jobs"]] == ["Goldman Sachs"]

        # Location normalized to "Country - City".
        gs = next(j for j in visible["jobs"] if j["company"] == "Goldman Sachs")
        assert gs["location"] == "US - New York"
        assert gs["seniority"] == "Internship"

        # Excluded rows still exist for the full-feed escape hatch.
        all_companies = JobService.get_all_companies(include_excluded=True)
        assert "JPMorgan" in all_companies and "Morgan Stanley" in all_companies
        assert "JPMorgan" not in JobService.get_all_companies()
