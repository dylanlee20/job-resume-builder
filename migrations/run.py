"""Deploy-time migration runner.

scripts/deploy.sh invokes this whenever files under migrations/ change.
Each step is idempotent, so re-runs are safe. Keep ordering: schema changes
first, then data seeds that depend on them.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from migrations import add_student_columns, seed_student_roster
from migrations._dbapp import masked_target


def main():
    print(f"== migrations: target DB = {masked_target()} ==")
    print("== migrations: add_student_columns ==")
    add_student_columns.migrate()
    print("== migrations: seed_student_roster ==")
    seed_student_roster.seed()
    print("== migrations: done ==")


if __name__ == "__main__":
    main()
