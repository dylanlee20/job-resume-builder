"""Tests for the front-office and job-type classifiers."""
from utils.ai_proof_filter import classify_ai_proof_role, EXCLUDED
from utils.seniority_classifier import classify_job_type, INTERNSHIP, FULL_TIME


class TestFrontOfficeClassifier:
    def test_front_office_titles_are_kept_with_division(self):
        cases = {
            "Investment Banking Analyst": "Investment Banking",
            "M&A Associate": "Investment Banking",
            "Equity Sales Trader": "Sales & Trading",
            "Fixed Income Trader": "Sales & Trading",
            "Equity Research Associate": "Equity Research",
            "Portfolio Manager, Multi-Asset": "Asset & Wealth Management",
            "Private Equity Associate": "Private Equity & VC",
            "Quantitative Researcher": "Quant",
            "Market Risk Analyst": "Risk",
            "Derivatives Structuring Associate": "Structuring",
        }
        for title, expected in cases.items():
            is_fo, category = classify_ai_proof_role(title)
            assert is_fo is True, title
            assert category == expected, (title, category)

    def test_back_and_middle_office_are_excluded(self):
        for title in [
            "Software Engineer, Trading Systems",
            "Data Engineer",
            "Operations Analyst",
            "Settlements Associate",
            "Compliance Officer",
            "KYC Analyst",
            "Internal Auditor",
            "Staff Accountant",
            "Human Resources Business Partner",
            "Bank Teller",
            "Personal Banker",
            "Branch Manager",
            "Recruiting Coordinator",
        ]:
            is_fo, category = classify_ai_proof_role(title)
            assert is_fo is False, title
            assert category == EXCLUDED, title

    def test_tech_title_beats_finance_description(self):
        is_fo, category = classify_ai_proof_role(
            "Software Engineer", "Build systems for our equity trading desk and M&A team"
        )
        assert is_fo is False
        assert category == EXCLUDED

    def test_front_office_title_survives_ops_description(self):
        is_fo, category = classify_ai_proof_role(
            "Equity Trader", "Support settlement and reconciliation processes"
        )
        assert is_fo is True
        assert category == "Sales & Trading"

    def test_empty_title_excluded(self):
        assert classify_ai_proof_role("") == (False, EXCLUDED)


class TestJobTypeClassifier:
    def test_internship_titles(self):
        for title in [
            "Investment Banking Summer Analyst",
            "Summer Associate",
            "2026 Internship - Global Markets",
            "Off-Cycle Intern",
            "Spring Week Insight Programme",
            "Sales & Trading Co-op",
        ]:
            assert classify_job_type(title) == INTERNSHIP, title

    def test_full_time_titles(self):
        for title in [
            "Investment Banking Analyst",
            "Vice President, M&A",
            "Graduate Analyst Programme",
            "Portfolio Manager",
        ]:
            assert classify_job_type(title) == FULL_TIME, title

    def test_scraper_hint_marks_internship(self):
        assert classify_job_type("Analyst", hint="intern") == INTERNSHIP
        assert classify_job_type("Analyst", hint="Internship") == INTERNSHIP

    def test_title_wins_over_fulltime_hint(self):
        assert classify_job_type("Summer Analyst", hint="Full Time") == INTERNSHIP
