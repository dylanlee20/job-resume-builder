"""Deploy-time migration runner.

scripts/deploy.sh invokes this whenever files under migrations/ change.
Each step is idempotent, so re-runs are safe. Keep ordering: schema changes
first, then data seeds that depend on them.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from migrations import (
    add_student_columns,
    seed_student_roster,
    create_session_records,
    add_job_program_type,
    add_job_link_kind,
    seed_programs,
    seed_question_bank,
)
from migrations._dbapp import masked_target


def main():
    print(f"== migrations: target DB = {masked_target()} ==")
    print("== migrations: add_student_columns ==")
    add_student_columns.migrate()
    print("== migrations: create_session_records ==")
    create_session_records.migrate()
    # Column-adds must run before any migration that ORM-queries `jobs`
    # (a Job query selects every mapped column, including these new ones).
    print("== migrations: add_job_link_kind ==")
    add_job_link_kind.migrate()
    print("== migrations: add_job_program_type ==")
    add_job_program_type.migrate()
    print("== migrations: seed_programs ==")
    seed_programs.seed()
    print("== migrations: seed_student_roster ==")
    seed_student_roster.seed()
    print("== migrations: backfill_member_numbers ==")
    seed_student_roster.backfill_member_numbers()
    print("== migrations: seed_question_bank ==")
    seed_question_bank.migrate()
    print("== migrations: done ==")


if __name__ == "__main__":
    main()
