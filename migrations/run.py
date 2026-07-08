"""Deploy-time migration runner.

scripts/deploy.sh invokes this whenever files under migrations/ change.
Each step is idempotent, so re-runs are safe. Keep ordering: schema changes
first, then data seeds that depend on them.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from migrations import (
    add_student_columns,
    seed_student_roster,
    create_session_records,
    add_job_program_type,
    add_job_link_kind,
    seed_programs,
    seed_question_bank,
    backfill_front_office,
    remove_offboarded_accounts,
)
from migrations._dbapp import masked_target


def _run(label, fn):
    """Run one idempotent migration step with a timestamped, flushed log so the
    deploy log streams progress (and reveals which step is slow, if any)."""
    print(f"== migrations: {label} ==", flush=True)
    t0 = time.time()
    fn()
    print(f"   -> {label} done in {time.time() - t0:.1f}s", flush=True)


def main():
    # All steps are idempotent, so a re-run after an interrupted deploy safely
    # re-applies. Schema first; then the user-facing roster changes so they land
    # even if a later step stalls; the heavy full-table backfill runs last.
    print(f"== migrations: target DB = {masked_target()} ==", flush=True)

    # Schema (fast no-ops once applied). Column-adds must precede any step that
    # ORM-queries `jobs` (a Job query selects every mapped column).
    _run("add_student_columns", add_student_columns.migrate)
    _run("create_session_records", create_session_records.migrate)
    _run("add_job_link_kind", add_job_link_kind.migrate)
    _run("add_job_program_type", add_job_program_type.migrate)

    # User-facing roster + account changes — small, fast, run early.
    _run("seed_student_roster", seed_student_roster.seed)
    _run("backfill_member_numbers", seed_student_roster.backfill_member_numbers)
    _run("remove_offboarded_accounts", remove_offboarded_accounts.migrate)

    _run("seed_programs", seed_programs.seed)
    _run("seed_question_bank", seed_question_bank.migrate)

    # Heavy full-table backfill: scans the ~28k-row jobs table and runs longer
    # than the SSH deploy command_timeout on this droplet, so it is kept OUT of
    # routine deploys (it was the sole cause of the wedged-deploy loop). New
    # rows already self-classify on insert, so this is a one-time legacy pass —
    # run it deliberately off-peak with a long-lived session:
    #   RUN_HEAVY_BACKFILL=1 /opt/app/venv/bin/python /opt/app/migrations/run.py
    # (or python migrations/backfill_front_office.py). It is marker-gated too.
    if os.environ.get("RUN_HEAVY_BACKFILL") == "1":
        _run("backfill_front_office", backfill_front_office.migrate)
    else:
        print(
            "== migrations: backfill_front_office SKIPPED "
            "(set RUN_HEAVY_BACKFILL=1 to run the one-time legacy pass) ==",
            flush=True,
        )
    print("== migrations: done (all steps idempotent) ==", flush=True)


if __name__ == "__main__":
    main()
