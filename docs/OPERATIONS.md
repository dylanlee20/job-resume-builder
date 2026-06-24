# NewWhale Career — Operations & Pipeline

Everything here runs **in the cloud**. There is no dependency on any individual
laptop: code is edited and pushed to GitHub, and GitHub Actions + the production
server do all the running. To operate the system you only need a browser
(GitHub + the admin site).

## Where things run

| Piece | Runs on | Trigger |
|-------|---------|---------|
| Website (newwhaletech.com) | Production VPS, systemd service `newwhale`, gunicorn on `127.0.0.1:5002` behind nginx, app dir `/opt/app` | always on |
| Database | **SQLite** at `/opt/app/data/jobs.db` on the VPS | — |
| Deploy | GitHub Actions `deploy.yml` | every push to `master` |
| Job scraper | GitHub Actions in repo `dylanlee20/job-scraper` (`scrape.yml`) | cron Sun + Wed, or manual |
| Job import | VPS background scheduler (APScheduler) | **daily 06:00**, or manual |
| "Import jobs now" | GitHub Actions `import-now.yml` (SSHes to VPS) | manual (`workflow_dispatch`) |

## Job data pipeline

```
job-scraper repo (GitHub Actions, Sun+Wed)
   scrape 347 career pages -> commit jobs_finance.csv to the repo
        │
        ▼
job-resume-builder importer (VPS, daily 06:00 or manual)
   scraper_runner.run_all_scrapers:
     1. fetch latest jobs_finance.csv from GitHub (JOBS_CSV_URL + JOBS_CSV_TOKEN)
     2. CSVImportService.import_all: upsert rows, tag program_type,
        EXPIRE active jobs not re-seen in 14 days (curated programs exempt)
why     -> tracker shows only what's actually live, refreshed daily
```

### Running an import on demand
- **From the site:** Admin → "Run Scraper" button (`/admin/run-scraper`).
- **From GitHub:** Actions → "Import jobs now" → Run workflow (`import-now.yml`).

Both run `scraper_runner.py manual` on the server: fetch CSV → import → expire.

## Curated programs (early-career + women/diversity)

- `migrations/seed_programs.py` seeds ~56 flagship bank programs (GS Possibilities,
  JPM Winning Women, Spring Weeks, boutique sophomore/diversity programs, …) as
  `Job` rows tagged `source_website='curated-program'`. They are **never expired**.
- `services/program_classifier.py` auto-tags any scraped listing whose title
  matches early/women keywords, so coverage grows on its own.
- Canonical pages: `/early-programs` and `/women-programs` (nav links + section
  tabs on the tracker; rows show Early / Women-Diversity badges).
- To add/edit programs: edit `PROGRAMS` in `migrations/seed_programs.py` and push
  (the seed is idempotent and re-runs on deploy).

## Admin User Management (student roster)

- `/admin/users`: columns ID (6-digit member no.), Name, College, Major, Grad Yr,
  Last Login, Sessions (progress bar + plan badge), Done?, Offers.
- Right-click a row for Access + Actions; ✏️ edits the student profile.
- Roster seeded from the 2028 spreadsheet via `migrations/seed_student_roster.py`
  (display-only, disabled accounts). Re-seeds on schema deploys.
- **Session History** panel (top of page): log a session (student, mentor, type,
  topic, 1-5 stars, feedback) — stored in `session_records`.

## Database migrations

`scripts/deploy.sh` runs `migrations/run.py` whenever files under `migrations/`
change in a push. Every step is idempotent. Migrations build a minimal app via
`migrations/_dbapp.py`, which:
- loads `/opt/app/.env` with `override=True` (the deploy shell can carry a stray
  `DATABASE_URL` pointing at an empty managed-DB `defaultdb` — this forces the
  app's real SQLite DB to win), and
- translates any `mysql://...?ssl-mode=...` URL to pymysql + SSL (not needed for
  the current SQLite DB, but safe if the DB ever moves).

## Secrets (GitHub repo secrets on job-resume-builder)

- `SERVER_HOST`, `DEPLOY_SSH_KEY` — SSH deploy.
- `JOBS_CSV_URL`, `JOBS_CSV_TOKEN` — where/how the importer pulls the scraper CSV.
  These are injected into `/opt/app/.env` by `deploy.yml` on every deploy.

## "I just want to log in and see"

- Jobs + programs: log in at newwhaletech.com → Job Tracker / Early Programs /
  Women & Diversity.
- Roster + sessions: Admin → User Management.
- Pipeline health: GitHub → Actions tab (Deploy, scrape, Import jobs now runs).
