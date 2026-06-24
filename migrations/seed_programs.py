"""Seed curated early-career and women/diversity programs across banks.

Inserted as Job rows tagged source_website='curated-program' so they appear in
the tracker, carry a program_type, and are NEVER auto-expired by the importer.
Each carries a link_kind: 'direct' (the url is a real application/registration
page) or 'site' (a program/company landing page — most programs, since apply
windows open Oct-Dec). Researched from official sources; no deadlines stored.

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

# (bank, program_name, program_type, region, url, link_kind, note)
PROGRAMS = [
    ("Goldman Sachs", "Virtual Insight Series", "early", "US", "https://www.goldmansachs.com/careers/students/programs-and-internships/americas/undergrad-virtual-insight-series", "site", "Program page; applications open in spring"),
    ("Goldman Sachs", "Emerging Leaders Series", "early", "US", "https://www.goldmansachs.com/careers/students/programs-and-internships/americas/emerging-leaders-series", "site", "Program page; apply opens in fall"),
    ("Goldman Sachs", "Possibilities Series (Summits)", "early,diversity", "US", "https://www.goldmansachs.com/careers/students/programs-and-internships/americas/possibilities-series", "site", "Program page; register via events portal in fall"),
    ("Goldman Sachs", "Women's Possibilities Summit", "diversity", "US", "https://www.goldmansachs.com/careers/students/programs-and-internships/americas/possibilities-series", "site", "Women's track within Possibilities Summits page"),
    ("Morgan Stanley", "Early Insights Program", "early,diversity", "US", "https://morganstanley.tal.net/vx/lang-en-GB/mobile-0/brand-2/candidate/so/pm/1/pl/2/opp/20971-2026-Morgan-Stanley-Early-Insights-Series/en-GB", "direct", "tal.net application requisition"),
    ("Morgan Stanley", "Spring Insight Programme", "early", "UK", "https://morganstanley.tal.net/vx/mobile-0/brand-2/candidate/jobboard/vacancy/1/adv/", "site", "Job board; spring reqs open in fall"),
    ("Morgan Stanley", "Step In, Step Up", "diversity", "UK", "https://morganstanley.tal.net/vx/mobile-0/brand-2/candidate/so/pm/1/pl/2/opp/20708-2026-Step-In-Step-Up-Women-in-STEM-Glasgow/en-GB", "direct", "tal.net application requisition"),
    ("JPMorgan", "Spring Insight", "early", "UK", "https://careers.jpmorgan.com/global/en/students/programs/spring-insights", "site", "Program page; apply opens November"),
    ("JPMorgan", "Winning Women", "early,diversity", "US", "https://www.jpmorganchase.com/careers/explore-opportunities/programs/winning-women-ba", "site", "Program page; openings vary by location"),
    ("JPMorgan", "Proud To Be", "early,diversity", "US", "https://www.jpmorganchase.com/impact/people/lgbtq-plus-affairs/careers", "site", "Program landing; events posted seasonally"),
    ("JPMorgan", "Advancing Black Pathways Fellowship", "early,diversity", "US", "https://www.jpmorganchase.com/impact/people/advancing-black-pathways/fellowship-program", "site", "Program page; apply opens December"),
    ("JPMorgan", "Advancing Hispanics & Latinos", "early,diversity", "US", "https://careers.jpmorgan.com/global/en/students/programs/ahl-fellowship", "site", "Fellowship page; apply opens December"),
    ("Bank of America", "Sophomore Summer Analyst Program", "early,diversity", "US", "https://careers.bankofamerica.com/en-us/students/programs", "site", "Programs page; sophomore reqs open in fall"),
    ("Bank of America", "Spring Insight Program", "early", "UK", "https://careers.bankofamerica.com/en-us/students/job-detail/13753/spring-insight-program-2026-x2013-banking-markets-global-payments-solutions-enterprise-credit-x2013-london-london-united-kingdom", "direct", "Job requisition, 2026 London Spring Insight"),
    ("Citi", "Freshman Discovery Program", "early,diversity", "US", "https://jobs.citi.com/early-careers", "site", "Early-careers hub; freshman program opens spring"),
    ("Citi", "Early ID Leadership Program", "early,diversity", "US", "https://jobs.citi.com/early-careers", "site", "Early-careers hub; Early ID applies via Workday in fall"),
    ("Citi", "Black Heritage Leadership Program (Early ID)", "early,diversity", "US", "https://jobs.citi.com/early-careers", "site", "Early-careers hub; Early ID network track"),
    ("Barclays", "Spring Internship (Spring Week)", "early", "UK", "https://search.jobs.barclays/internships", "site", "Internships listing; Spring Week opens November"),
    ("Barclays", "Discovery Programme", "diversity", "UK", "https://search.jobs.barclays/discovery", "site", "Program page; apply on rolling basis in fall"),
    ("Deutsche Bank", "Spring into Banking", "early", "UK", "https://careers.db.com/students-graduates/insight-programmes/uk-and-ireland/spring-into-banking", "site", "Program page; apply opens in fall"),
    ("Deutsche Bank", "GROW", "early,diversity", "UK", "https://careers.db.com/students-graduates/insight-programmes/uk-and-ireland/grow-uk", "site", "Program page; apply opens in fall"),
    ("Deutsche Bank", "dbAchieve / Develop", "diversity", "US", "https://careers.db.com/students-graduates/insight-programmes/us/develop", "site", "Program page; apply in fall"),
    ("UBS", "Tomorrow's Talent (Spring Insight)", "early", "UK", "https://jobs.ubs.com/TGnewUI/Search/home/HomeWithPreLoad?partnerid=25008&siteid=5131&PageType=JobDetails&jobid=335457", "direct", "2026 application requisition on UBS jobs portal"),
    ("HSBC", "Spring Insight Programme", "early", "UK", "https://www.hsbc.com/careers/students-and-graduates/student-opportunities/uk-insight-programme", "site", "Program page; apply via Find a programme in fall"),
    ("HSBC", "Women in Banking Spring Insight Programme", "early,diversity", "UK", "https://www.hsbc.com/careers/students-and-graduates/student-opportunities/uk-women-in-banking-insight-programme", "site", "Program page; apply reopens in fall"),
    ("BNP Paribas", "Spring Insights", "early", "UK", "https://careers.bnpparibas.co.uk/spring-insights/", "site", "Program page; apply opens in fall"),
    ("BNP Paribas", "MixCity (Diversity & Inclusion)", "diversity", "UK", "https://earlycareers.bnpparibas.com/about-us/diversity/", "site", "Gender network; no student application"),
    ("RBC", "Women's Advisory Program", "early,diversity", "Global", "https://www.rbccm.com/en/careers/womens-advisory-program.page", "site", "Program page; apply via Workday in fall"),
    ("RBC", "RBC Amplify", "early", "Global", "https://jobs.rbc.com/ca/en/amplify", "site", "Program page; location postings open seasonally"),
    ("RBC", "RBC Pathways", "early,diversity", "Global", "https://www.rbccm.com/en/careers/pathways.page", "site", "Program page; apply via Workday in fall"),
    ("Wells Fargo", "Sophomore Discovery Fellowship Program", "early,diversity", "US", "https://talent.wellsfargojobs.com/flows/sdfp2026", "direct", "2026 talent-community registration flow"),
    ("Nomura", "Women's Immersion Programme", "early,diversity", "UK", "https://nomuracampus.tal.net/vx/mobile-0/appcentre-ext/brand-4/candidate/so/pm/1/pl/1/opp/1270-2026-Women-s-Immersion-Programme-Global-Markets-Investment-Banking-London/en-GB", "direct", "tal.net application requisition"),
    ("Nomura", "SEO / Explore Nomura", "diversity", "UK", "https://www.nomura.com/careers/early-careers/insight-programs/", "site", "Insight programs page; SEO members get apply link"),
    ("Macquarie", "Early Insight Days", "early,diversity", "US", "https://www.macquarie.com/us/en/careers/students-and-graduates.html", "site", "Students page; 2026 NY Insight Days opens in fall"),
    ("Macquarie", "Women in Business Series", "early,diversity", "UK", "https://www.macquarie.com/uk/en/careers/graduates-and-interns/our-programmes.html", "site", "Programmes page; registration seasonal"),
    ("Mizuho", "Sophomore Women in Banking Program", "early,diversity", "US", "https://www.mizuhogroup.com/americas/careers/campus-recruiting", "site", "Campus recruiting page; apply via university portals"),
    ("Evercore", "Sophomore Diversity Seminar (IB Simulation)", "early,diversity", "US", "https://www.evercore.com/careers/students-graduates/students-graduates-u-s/", "site", "Student careers page; seminar opens in fall"),
    ("Evercore", "Rising Junior Diversity Scholarship", "diversity", "US", "https://www.evercore.com/careers/students-graduates/students-graduates-u-s/", "site", "Student careers page; scholarship not yet open"),
    ("Lazard", "Early Insights Program", "early,diversity", "US", "https://www.lazard.com/careers/students/", "site", "Student careers landing page"),
    ("Lazard", "Women's Leadership Network", "diversity", "Global", "https://www.lazard.com/careers/inclusion/", "site", "Inclusion page; no live posting"),
    ("Centerview Partners", "Early Insights Program", "early,diversity", "US", "https://www.centerviewpartners.com/careers.aspx", "site", "Careers page with resume form"),
    ("Centerview Partners", "Women's Leadership Program", "diversity", "US", "https://www.centerviewpartners.com/womensleadership.aspx", "site", "Program info page, no application"),
    ("Moelis & Company", "Young Leaders Diversity Program", "early,diversity", "US", "https://moelis-careers.tal.net/candidate/jobboard/vacancy/2/adv/", "site", "Student job board; program opens in fall"),
    ("Moelis & Company", "Leadership Development Program (LDP)", "diversity", "US", "https://moelis-careers.tal.net/candidate/jobboard/vacancy/2/adv/", "site", "Student job board; LDP opens in fall"),
    ("PJT Partners", "PJT Forward", "early,diversity", "US", "https://pjtpartners.wd1.myworkdayjobs.com/Students", "site", "Workday students portal; no live PJT Forward req"),
    ("PJT Partners", "Women's Insight Program", "diversity", "US", "https://pjtpartners.wd1.myworkdayjobs.com/Students", "site", "Workday students portal; no live women's req"),
    ("Perella Weinberg Partners", "Advisory Prep Program", "early,diversity", "US", "https://pwpcareers.tal.net/candidate/jobboard/vacancy/1/adv/", "site", "Careers job board; prep program opens in fall"),
    ("Perella Weinberg Partners", "Women's Prep Program", "diversity", "Global", "https://pwpcareers.tal.net/candidate/jobboard/vacancy/1/adv/", "site", "Careers job board; women's prep opens in fall"),
    ("Jefferies", "Investment Banking Diversity Symposium", "early,diversity", "US", "https://jefferies.tal.net/candidate/jobboard/vacancy/2/adv/", "site", "Student job board; symposium opens in fall"),
    ("Jefferies", "Jefferies Women's Initiative Network (jWIN)", "diversity", "Global", "https://www.jefferies.com/about/diversity-equity-inclusion/inclusive-development-growth/", "site", "Network page; no live application"),
    ("Houlihan Lokey", "Investment Banking Women's Insight Day", "diversity", "US", "https://hl.wd1.myworkdayjobs.com/Campus", "site", "Campus Workday portal; women's day opens in fall"),
    ("Houlihan Lokey", "IB First Look: Diversity Information Session", "early,diversity", "US", "https://hl.wd1.myworkdayjobs.com/Campus", "site", "Campus Workday portal; First Look opens in fall"),
    ("Guggenheim Securities", "IB Sophomore Diversity Internship Program", "early,diversity", "US", "https://guggenheim.wd1.myworkdayjobs.com/Guggenheim_Undergraduate_Programs", "site", "Undergrad programs Workday portal (Sophomore FOCUS)"),
    ("Greenhill & Co", "Women's Insight Day (Sophomore Women in Banking)", "early,diversity", "US", "https://greenhill.wd5.myworkdayjobs.com/SearchJobs", "site", "Workday job search; women's day opens in fall"),
    ("Rothschild & Co", "Sophomore Women's Program (US GA)", "early,diversity", "US", "https://rothschildandco.tal.net/candidate/jobboard/vacancy/2/adv/", "site", "Student job board; 2027 cycle opens in fall"),
    ("Rothschild & Co", "Sophomore Leadership Program (US GA)", "early,diversity", "US", "https://rothschildandco.tal.net/candidate/jobboard/vacancy/2/adv/", "site", "Student job board; 2027 cycle opens in fall"),
]


def seed():
    app = create_db_app()
    created, updated = 0, 0
    with app.app_context():
        now = datetime.utcnow()
        for bank, name, ptype, region, url, link_kind, note in PROGRAMS:
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
                    link_kind=link_kind,
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
                job.link_kind = link_kind
                job.source_website = CURATED_SOURCE
                job.job_url = url
                job.description = note
                job.status = "active"
                job.last_seen = now
                updated += 1
        db.session.commit()
        direct = sum(1 for p in PROGRAMS if p[5] == "direct")
        print(f"OK: Curated programs seeded: {created} created, {updated} updated "
              f"({direct} direct apply links, {len(PROGRAMS) - direct} program pages).")


if __name__ == "__main__":
    seed()
