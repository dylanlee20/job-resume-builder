"""Create sample jobs to showcase Bloomberg theme"""
from app import create_app
from models.job import Job
from models.database import db
from datetime import datetime, timedelta

sample_jobs = [
    # AI-Proof Investment Banking Jobs
    {
        "company": "Goldman Sachs",
        "title": "Investment Banking Summer Analyst - M&A",
        "location": "New York, NY",
        "description": "Summer internship for undergraduate students in our M&A team",
        "is_ai_proof": True,
        "ai_proof_category": "Investment Banking",
        "seniority": "Student/Grad",
        "job_url": "https://example.com/gs1"
    },
    {
        "company": "JPMorgan",
        "title": "Sales & Trading Summer Intern - Equities",
        "location": "Hong Kong",
        "description": "Summer internship trading equities in Asia markets",
        "is_ai_proof": True,
        "ai_proof_category": "Sales & Trading",
        "seniority": "Student/Grad",
        "job_url": "https://example.com/jpm1"
    },
    {
        "company": "Morgan Stanley",
        "title": "Portfolio Manager - Fixed Income",
        "location": "London, UK",
        "description": "Manage fixed income portfolios",
        "is_ai_proof": True,
        "ai_proof_category": "Asset & Wealth Management",
        "seniority": "Professional",
        "job_url": "https://example.com/ms1"
    },
    {
        "company": "Citigroup",
        "title": "Risk Management VP - Market Risk",
        "location": "Singapore",
        "description": "Oversee market risk analytics",
        "is_ai_proof": True,
        "ai_proof_category": "Risk Management",
        "seniority": "Professional",
        "job_url": "https://example.com/citi1"
    },
    {
        "company": "Barclays",
        "title": "M&A Advisory Director",
        "location": "New York, NY",
        "description": "Lead M&A advisory engagements",
        "is_ai_proof": True,
        "ai_proof_category": "Investment Banking",
        "seniority": "Professional",
        "job_url": "https://example.com/barc1"
    },
    {
        "company": "Blackstone",
        "title": "Private Equity Graduate Program",
        "location": "Los Angeles, CA",
        "description": "Graduate rotational program analyzing private equity investments",
        "is_ai_proof": True,
        "ai_proof_category": "Private Equity",
        "seniority": "Student/Grad",
        "job_url": "https://example.com/blk1"
    },
    {
        "company": "Deutsche Bank",
        "title": "Structuring VP - Derivatives",
        "location": "Frankfurt, Germany",
        "description": "Structure complex derivatives products",
        "is_ai_proof": True,
        "ai_proof_category": "Structuring",
        "seniority": "Professional",
        "job_url": "https://example.com/db1"
    },
    {
        "company": "UBS",
        "title": "Investment Banking Analyst - Healthcare",
        "location": "San Francisco, CA",
        "description": "Work with healthcare banking team",
        "is_ai_proof": True,
        "ai_proof_category": "Investment Banking",
        "seniority": "Professional",
        "job_url": "https://example.com/ubs1"
    },
    {
        "company": "HSBC",
        "title": "Trading Desk Head - FX",
        "location": "Shanghai, China",
        "description": "Manage FX trading desk",
        "is_ai_proof": True,
        "ai_proof_category": "Sales & Trading",
        "seniority": "Professional",
        "job_url": "https://example.com/hsbc1"
    },
    {
        "company": "BNP Paribas",
        "title": "Structured Products Sales Intern",
        "location": "Paris, France",
        "description": "Summer internship selling structured products to institutions",
        "is_ai_proof": True,
        "ai_proof_category": "Structuring",
        "seniority": "Student/Grad",
        "job_url": "https://example.com/bnp1"
    },

    # Excluded Jobs (for contrast)
    {
        "company": "Goldman Sachs",
        "title": "Financial Accountant",
        "location": "New York, NY",
        "description": "Handle financial reporting",
        "is_ai_proof": False,
        "ai_proof_category": "Accounting",
        "seniority": "Professional",
        "job_url": "https://example.com/gs2"
    },
    {
        "company": "JPMorgan",
        "title": "Data Science Analyst",
        "location": "Chicago, IL",
        "description": "Analyze data and create reports",
        "is_ai_proof": False,
        "ai_proof_category": "Data Science",
        "seniority": "Professional",
        "job_url": "https://example.com/jpm2"
    },
    {
        "company": "Morgan Stanley",
        "title": "Compliance Officer",
        "location": "New York, NY",
        "description": "Ensure regulatory compliance",
        "is_ai_proof": False,
        "ai_proof_category": "Compliance",
        "seniority": "Professional",
        "job_url": "https://example.com/ms2"
    },
]

def create_samples():
    app, _ = create_app()

    with app.app_context():
        print("Creating sample jobs...")

        for job_data in sample_jobs:
            # Check if already exists
            existing = Job.query.filter_by(job_url=job_data['job_url']).first()
            if not existing:
                job_hash = Job.generate_job_hash(
                    job_data['company'],
                    job_data['title'],
                    job_data['location']
                )

                job = Job(
                    job_hash=job_hash,
                    company=job_data['company'],
                    title=job_data['title'],
                    location=job_data['location'],
                    description=job_data['description'],
                    is_ai_proof=job_data['is_ai_proof'],
                    ai_proof_category=job_data['ai_proof_category'],
                    seniority=job_data.get('seniority', 'Professional'),
                    job_url=job_data['job_url'],
                    source_website="Sample Data",
                    status='active',
                    post_date=datetime.utcnow() - timedelta(days=1),
                    first_seen=datetime.utcnow() - timedelta(days=1)
                )
                db.session.add(job)

                category_type = "AI-PROOF" if job_data['is_ai_proof'] else "EXCLUDED"
                print(f"✓ {category_type} [{job_data['ai_proof_category']}]: {job_data['title']}")

        db.session.commit()

        total = Job.query.count()
        ai_proof = Job.query.filter_by(is_ai_proof=True).count()
        excluded = Job.query.filter_by(is_ai_proof=False).count()

        print(f"\n{'='*60}")
        print(f"Sample jobs created successfully!")
        print(f"Total jobs in database: {total}")
        print(f"  AI-proof: {ai_proof}")
        print(f"  Excluded: {excluded}")
        print(f"{'='*60}")
        print(f"\n✨ Visit http://127.0.0.1:5002 to see the Bloomberg theme!")

if __name__ == '__main__':
    create_samples()
