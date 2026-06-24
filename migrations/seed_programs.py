"""Seed curated early-career and women/diversity programs across banks.

These are inserted as Job rows tagged source_website='curated-program' so they
appear in the tracker, carry a program_type, and are NEVER auto-expired by the
import job. Researched from official bank pages (2026-2027 cycle); no
application deadlines are stored because those change yearly.

Idempotent: upsert by (company, title, location) hash.
"""
from datetime import datetime

from migrations._dbapp import create_db_app
from models.database import db
from models.job import Job

CURATED_SOURCE = "curated-program"

_REGION_TO_LOCATION = {
    "US": "United States",
    "UK": "United Kingdom",
    "HK": "Hong Kong",
    "Global": "Global",
}

# (bank, program_name, program_type, region, url, note)
PROGRAMS = [
    # --- Bulge bracket ---
    ("Goldman Sachs", "Virtual Insight Series", "early", "US", "https://www.goldmansachs.com/careers/students/programs-and-internships/americas/undergrad-virtual-insight-series", "Multi-part virtual program for early undergrads"),
    ("Goldman Sachs", "Emerging Leaders Series", "early", "US", "https://www.goldmansachs.com/careers/students/programs-and-internships/americas/emerging-leaders-series", "For second-year undergraduates"),
    ("Goldman Sachs", "Possibilities Series (Summits)", "early,diversity", "US", "https://www.goldmansachs.com/careers/students/programs-and-internships/americas/possibilities-series", "Women's, Black, Hispanic/Latinx, Pride, Veterans, HBCU summits"),
    ("Goldman Sachs", "Women's Possibilities Summit", "diversity", "US", "https://www.goldmansachs.com/careers/students/programs-and-internships/americas/possibilities-series", "For undergraduate women"),
    ("Morgan Stanley", "Early Insights Program", "early,diversity", "US", "https://www.morganstanley.com/people-opportunities/students-graduates", "Freshmen/sophomores; women and underrepresented groups"),
    ("Morgan Stanley", "Spring Insight Programme", "early", "UK", "https://www.morganstanley.com/people-opportunities/emea-early-insight-faq", "First-year insight, London and Glasgow"),
    ("Morgan Stanley", "Step In, Step Up", "diversity", "UK", "https://www.morganstanley.com/people-opportunities/emea-early-insight-faq", "Three-day insight for female students"),
    ("JPMorgan", "Spring Insight", "early", "UK", "https://www.jpmorganchase.com/careers/explore-opportunities/programs", "First-year pre-internship insight program"),
    ("JPMorgan", "Winning Women", "early,diversity", "US", "https://www.jpmorganchase.com/careers/explore-opportunities/programs/winning-women-ba", "Early insight for female undergraduates"),
    ("JPMorgan", "Proud To Be", "early,diversity", "US", "https://www.jpmorganchase.com/careers/explore-opportunities/programs", "Early insight for LGBT+ undergraduates"),
    ("JPMorgan", "Advancing Black Pathways Fellowship", "early,diversity", "US", "https://www.jpmorganchase.com/impact/diversity-equity-and-inclusion/advancing-black-pathways", "Early exposure for Black undergraduate sophomores"),
    ("JPMorgan", "Advancing Hispanics & Latinos", "early,diversity", "US", "https://www.jpmorganchase.com/careers/explore-opportunities/programs", "Early insight for Hispanic/Latino undergraduates"),
    ("Bank of America", "Sophomore Summer Analyst Program", "early,diversity", "US", "https://careers.bankofamerica.com/en-us/students/programs", "Sophomores, focus on underrepresented groups"),
    ("Bank of America", "Spring Insight Program", "early", "UK", "https://careers.bankofamerica.com/en-us/students/programs", "First-year insight, London and Chester"),
    ("Citi", "Freshman Discovery Program", "early,diversity", "US", "https://jobs.citi.com/early-careers", "First-year students, virtual"),
    ("Citi", "Early ID Leadership Program", "early,diversity", "US", "https://jobs.citi.com/early-careers", "Sophomore virtual leadership with inclusion tracks"),
    ("Citi", "Black Heritage Leadership Program (Early ID)", "early,diversity", "US", "https://jobs.citi.com/early-careers", "Sophomores who self-identify as Black"),
    # --- Other large banks ---
    ("Barclays", "Spring Internship (Spring Week)", "early", "UK", "https://search.jobs.barclays/early-careers", "1-week first-year spring insight, London"),
    ("Barclays", "Discovery Programme", "diversity", "UK", "https://search.jobs.barclays/discovery", "Early insight up to two years from graduation"),
    ("Deutsche Bank", "Spring into Banking", "early", "UK", "https://careers.db.com/students-graduates/insight-programmes/uk-and-ireland/spring-into-banking", "First-year spring insight programme"),
    ("Deutsche Bank", "GROW", "early,diversity", "UK", "https://careers.db.com/students-graduates/insight-programmes/uk-and-ireland/grow-uk", "Four-day programme for first-year women"),
    ("Deutsche Bank", "dbAchieve / Develop", "diversity", "US", "https://careers.db.com/students-graduates/insight-programmes/us/develop", "Sophomore diverse-students pipeline programme"),
    ("UBS", "Tomorrow's Talent (Spring Insight)", "early", "UK", "https://www.ubs.com/global/en/careers/early-careers/tomorrows-talent-program.html", "Spring insight for pre-internship students"),
    ("HSBC", "Spring Insight Programme", "early", "UK", "https://www.hsbc.com/careers/students-and-graduates/insight-programmes", "First/second-year insight programme"),
    ("HSBC", "Women in Banking Spring Insight Programme", "early,diversity", "UK", "https://www.hsbc.com/careers/students-and-graduates/insight-programmes", "Spring insight for female students"),
    ("BNP Paribas", "Spring Insights", "early", "UK", "https://careers.bnpparibas.co.uk/spring-insights/", "Four-day first-year insight programme"),
    ("BNP Paribas", "MixCity (Diversity & Inclusion)", "diversity", "UK", "https://earlycareers.bnpparibas.com/about-us/diversity/", "Gender-equality early-careers D&I initiative"),
    ("RBC", "Women's Advisory Program", "early,diversity", "Global", "https://www.rbccm.com/en/careers/womens-advisory-program.page", "First-year women pipeline; CA/US/UK"),
    ("RBC", "RBC Amplify", "early", "Global", "https://jobs.rbc.com/ca/en/early-tech-talent", "Summer innovation program for students"),
    ("RBC", "RBC Pathways", "early,diversity", "Global", "https://www.rbccm.com/en/careers/pathways.page", "Diversity award + internship; CA/US/AUS"),
    ("Wells Fargo", "Sophomore Discovery Fellowship Program", "early,diversity", "US", "https://www.wellsfargojobs.com/en/early-careers/undergraduate-programs/", "Sophomore summer fellowship, diverse backgrounds"),
    ("Nomura", "Women's Immersion Programme", "early,diversity", "UK", "https://www.nomura.com/careers/early-careers/insight-programs/", "First-year women, two-week April insight"),
    ("Nomura", "SEO / Explore Nomura", "diversity", "UK", "https://www.nomura.com/careers/early-careers/insight-programs/", "Diverse-students early insight programme"),
    ("Macquarie", "Early Insight Days", "early,diversity", "US", "https://www.macquarie.com/us/en/careers/students-and-graduates.html", "Two-day sophomore underrepresented-students program"),
    ("Macquarie", "Women in Business Series", "early,diversity", "UK", "https://www.macquarie.com/uk/en/careers/graduates-and-interns/our-programmes.html", "Penultimate-year women development series"),
    ("Mizuho", "Sophomore Women in Banking Program", "early,diversity", "US", "https://www.mizuhogroup.com/americas/careers/campus-recruiting", "Three-day sophomore women banking program"),
    # --- Elite boutiques / mid-market ---
    ("Evercore", "Sophomore Diversity Seminar (IB Simulation)", "early,diversity", "US", "https://www.evercore.com/careers/students-graduates/students-graduates-u-s/", "Sophomore diversity day, IB simulation"),
    ("Evercore", "Rising Junior Diversity Scholarship", "diversity", "US", "https://www.evercore.com/careers/students-graduates/students-graduates-u-s/", "Scholarship plus IB summer internship"),
    ("Lazard", "Early Insights Program", "early,diversity", "US", "https://www.lazard.com/careers/students/", "First-year/sophomore diversity early insight"),
    ("Lazard", "Women's Leadership Network", "diversity", "Global", "https://www.lazard.com/careers/inclusion/", "Women's development and advancement network"),
    ("Centerview Partners", "Early Insights Program", "early,diversity", "US", "https://www.centerviewpartners.com/careers.aspx", "First-year/sophomore diverse student program"),
    ("Centerview Partners", "Women's Leadership Program", "diversity", "US", "https://www.centerviewpartners.com/careers.aspx", "Women's leadership initiative"),
    ("Moelis & Company", "Young Leaders Diversity Program", "early,diversity", "US", "https://www.moelis.com/cultureofinclusion/", "Sophomore diversity early insight day"),
    ("Moelis & Company", "Leadership Development Program (LDP)", "diversity", "US", "https://www.moelis.com/careers/", "Diversity program for summer analyst candidates"),
    ("PJT Partners", "PJT Forward", "early,diversity", "US", "https://pjtpartners.wd1.myworkdayjobs.com/Students", "Sophomore underrepresented backgrounds program"),
    ("PJT Partners", "Women's Insight Program", "diversity", "US", "https://pjtpartners.wd1.myworkdayjobs.com/Students", "Women's advisory insight, first/second year"),
    ("Perella Weinberg Partners", "Advisory Prep Program", "early,diversity", "US", "https://pwpartners.com/careers/intern-graduate-recruitment/", "Diversity prep program for sophomores"),
    ("Perella Weinberg Partners", "Women's Prep Program", "diversity", "Global", "https://pwpartners.com/careers/intern-graduate-recruitment/", "Women's advisory prep program"),
    ("Jefferies", "Investment Banking Diversity Symposium", "early,diversity", "US", "https://www.jefferies.com/careers/students-and-graduates/", "Sophomore diversity symposium, fast-track"),
    ("Jefferies", "Jefferies Women's Initiative Network (jWIN)", "diversity", "Global", "https://www.jefferies.com/about/diversity-equity-inclusion/inclusive-development-growth/", "Women's network, mentorship and recruiting"),
    ("Houlihan Lokey", "Investment Banking Women's Insight Day", "diversity", "US", "https://hl.com/careers/for-students/", "Sophomore/junior women's insight day"),
    ("Houlihan Lokey", "IB First Look: Diversity Information Session", "early,diversity", "US", "https://hl.com/careers/early-careers/", "Early diversity information session"),
    ("Guggenheim Securities", "IB Sophomore Diversity Internship Program", "early,diversity", "US", "https://guggenheim.wd1.myworkdayjobs.com/Guggenheim_Careers_Campus", "10-week sophomore diversity internship"),
    ("Greenhill & Co", "Women's Insight Day (Sophomore Women in Banking)", "early,diversity", "US", "https://www.greenhill.com/en/careers", "Sophomore women, guaranteed first-round interview"),
    ("Rothschild & Co", "Sophomore Women's Program (US GA)", "early,diversity", "US", "https://www.rothschildandco.com/en/careers/students-and-graduates/early-insights/", "Sophomore women January immersion, NY"),
    ("Rothschild & Co", "Sophomore Leadership Program (US GA)", "early,diversity", "US", "https://www.rothschildandco.com/en/careers/students-and-graduates/early-insights/", "Sophomore diversity leadership immersion, NY"),
]


def seed():
    app = create_db_app()
    created, updated = 0, 0
    with app.app_context():
        now = datetime.utcnow()
        for bank, name, ptype, region, url, note in PROGRAMS:
            location = _REGION_TO_LOCATION.get(region, "Global")
            job_hash = Job.generate_job_hash(bank, name, location)
            job = Job.query.filter_by(job_hash=job_hash).first()
            if job is None:
                db.session.add(Job(
                    job_hash=job_hash,
                    company=bank,
                    title=name,
                    location=location,
                    description=note,
                    program_type=ptype,
                    source_website=CURATED_SOURCE,
                    job_url=url,
                    status="active",
                    is_ai_proof=True,
                    first_seen=now,
                    last_seen=now,
                    last_updated=now,
                ))
                created += 1
            else:
                job.program_type = ptype
                job.source_website = CURATED_SOURCE
                job.job_url = url
                job.description = note
                job.status = "active"
                job.last_seen = now
                updated += 1
        db.session.commit()
        print(f"OK: Curated programs seeded: {created} created, {updated} updated.")


if __name__ == "__main__":
    seed()
