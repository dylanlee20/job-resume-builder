"""Backfill front-office classification + job type onto existing job rows.

Earlier ingests stored postings with no `is_ai_proof` / `ai_proof_category`
signal (the column default left every row flagged front-office) and no
`seniority`, so the tracker could neither hide back-office roles nor tell
internships from full-time seats. This pass runs every active row through the
shared classifier so the freshness counts, the Division facet and the
Full-Time/Internship split are correct for legacy data too.

Curated program rows (source_website='curated-program') are always kept
front-office; only their job type is inferred if missing.

Idempotent: classification is deterministic, so re-runs converge.
"""
import os
from datetime import datetime

from migrations._dbapp import create_db_app
from models.database import db
from models.job import Job
from utils.ai_proof_filter import classify_ai_proof_role
from utils.seniority_classifier import classify_job_type
from utils.job_utils import normalize_location

CURATED_SOURCE = "curated-program"
_BATCH = 500

# One-time completion marker. This pass is a legacy backfill — new rows are
# already classified on insert (JobService.process_scraped_job) — but it scans
# the full ~28k-row jobs table, which on every deploy is slow enough to brush
# the SSH command_timeout and contend for the SQLite write lock. Gate it so it
# runs to completion once, then is skipped on subsequent deploys. Delete the
# marker file (or pass force=True) to re-run intentionally.
_MARKER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".backfill_front_office.done",
)


def migrate(force: bool = False):
    if not force and os.path.exists(_MARKER):
        print("backfill_front_office: marker present — legacy backfill already applied, skipping")
        return
    app = create_db_app()
    with app.app_context():
        jobs = Job.query.all()
        reclassified = 0
        typed = 0
        relocated = 0
        for job in jobs:
            description = job.description or ""

            if job.source_website == CURATED_SOURCE:
                # Programs are curated front-office entries by definition.
                if job.is_ai_proof is not True:
                    job.is_ai_proof = True
                    reclassified += 1
            else:
                is_fo, division = classify_ai_proof_role(job.title, description)
                if job.is_ai_proof != is_fo or job.ai_proof_category != division:
                    reclassified += 1
                job.is_ai_proof = is_fo
                job.ai_proof_category = division
                job.category = division if is_fo else None

            new_type = classify_job_type(job.title, description, job.seniority or "")
            if job.seniority != new_type:
                job.seniority = new_type
                typed += 1

            # Clean any legacy raw location strings ("United States", "Americas-US-NY").
            cleaned = normalize_location(job.location or "Unknown")
            if cleaned and cleaned != job.location:
                job.location = cleaned
                relocated += 1

            if (reclassified + typed + relocated) % _BATCH == 0:
                db.session.commit()

        db.session.commit()
        print(
            f"backfill_front_office: {len(jobs)} rows | "
            f"reclassified={reclassified} retyped={typed} relocated={relocated}"
        )
    # Only stamped after a full, committed pass, so a run interrupted mid-scan
    # (e.g. a killed deploy) re-runs next time instead of being skipped.
    try:
        with open(_MARKER, "w") as fh:
            fh.write(datetime.utcnow().isoformat() + "Z\n")
        print(f"backfill_front_office: wrote completion marker {_MARKER}")
    except OSError as exc:
        print(f"backfill_front_office: WARN could not write marker: {exc}")


if __name__ == "__main__":
    migrate()
