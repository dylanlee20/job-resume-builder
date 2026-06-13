# NewWhale Career v2 - Project Context

## Overview
AI-Proof Industries Job Tracker with Resume Assessment and Revision Services

## Tech Stack
- **Backend**: Python 3.11, Flask, SQLAlchemy
- **Database**: SQLite (MVP), PostgreSQL (future)
- **Frontend**: Bootstrap 5, jQuery
- **Payments**: Stripe
- **LLM**: OpenAI GPT-4o-mini (configurable)
- **Scraping**: Selenium

## Project Structure
```
job-tracker-v2/
├── models/          # SQLAlchemy models
├── routes/          # Flask blueprints
├── services/        # Business logic layer
├── utils/           # Utility functions
├── scrapers/        # Job scrapers
├── templates/       # Jinja2 templates
├── static/          # CSS, JS
├── uploads/         # Resume files
└── tests/           # Unit and integration tests
```

## Core Features

### 1. AI-Proof Job Classification
- Filters jobs into AI-resistant categories
- Includes: Investment Banking, Sales & Trading, Portfolio Management, Risk Management, M&A Advisory, Private Equity
- Excludes: Accounting, Audit, Back Office, Basic Data Science, Compliance Reporting

### 2. Free Resume Assessment
- Upload PDF/DOCX resumes
- AI-powered analysis using LLM
- Scoring (0-100) + strengths/weaknesses
- Industry compatibility ratings
- Rate limited: 3 assessments/day for free tier

### 3. Paid Resume Revision (Premium)
- Template-based suggestions using successful resumes
- Section-by-section comparisons
- Before/after score projections
- Requires premium subscription

### 4. Subscription Tiers
- **Free**: Job listings, 3 resume assessments/day
- **Premium**: Unlimited assessments, resume revisions, priority support
- Payment via Stripe ($19/mo or $149/yr suggested)

## Database Models

### User
- username, email, password_hash
- tier ('free' | 'premium')
- stripe_customer_id
- Relationships: resumes, assessments, subscriptions

### Job
- company, title, location, description
- ai_proof_category, is_ai_proof (NEW)
- category, industry
- status, first_seen, last_seen

### Resume
- user_id, original_filename, stored_filename
- extracted_text
- status ('uploaded' | 'parsed' | 'assessed' | 'error')

### ResumeAssessment
- resume_id, user_id
- overall_score, strengths (JSON), weaknesses (JSON)
- industry_compatibility (JSON)
- assessment_type ('free' | 'premium')

### ResumeTemplate (Admin-uploaded)
- industry, company, role_level
- extracted_text, key_elements (JSON)
- is_active

### Subscription
- user_id, stripe_subscription_id
- plan, status, current_period_start/end

### Payment
- Audit trail for all transactions
- stripe_payment_intent_id, amount, currency, status

## Key Services

### JobService
- `get_jobs(filters)` - Query jobs with AI-proof filtering
- `process_scraped_job(data)` - Classify and store jobs
- `get_statistics()` - Dashboard metrics

### ResumeParserService (Phase 3)
- Parse PDF/DOCX to extract text
- Section detection (Education, Experience, Skills)

### ResumeAssessmentService (Phase 3)
- Call LLM API with resume text
- Parse structured output
- Rate limiting for free tier

### ResumeRevisionService (Phase 5)
- Match user resume with successful templates
- Generate section-by-section suggestions
- Premium-only feature

### PaymentService (Phase 4)
- Create Stripe Checkout sessions
- Handle webhooks (checkout.session.completed, etc.)
- Sync subscription status

## Environment Variables
See `.env.example` for all required variables:
- SECRET_KEY, DATABASE_URL
- STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET
- OPENAI_API_KEY or ANTHROPIC_API_KEY
- UPLOAD_MAX_SIZE_MB, FREE_TIER_DAILY_ASSESSMENTS

## Development Commands
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run app
python app.py

# Run tests
pytest tests/ -v --cov=. --cov-report=html
```

## Deployment
- VPS: 164.90.134.159 (hostname `rebuilt-ssh-newwhale`), app at `/opt/app`, systemd service `newwhale`
- This is the `/` app of a 3-app site; `/macro` and `/competitions` are separate apps on the same droplet
- Domain: newwhaletech.com (behind Cloudflare)
- Port: 5002 (gunicorn bound 127.0.0.1:5002, behind nginx)
- Auto-deploy: push to `master` -> GitHub Actions (`.github/workflows/deploy.yml`) SSHes in, `git reset --hard origin/master`, runs `scripts/deploy.sh`
- (Old IPs 167.71.209.9 and 165.227.103.197 are stale/dead; do not use)

## Testing Strategy
- Unit tests for all models (target 85%+ coverage)
- Integration tests for resume pipeline
- E2E tests for critical user flows
- Mock Stripe and LLM APIs in tests

## Security
- CSRF protection enabled
- Password hashing with Werkzeug
- No secrets in source code (.env only)
- File upload validation (MIME type + size)
- UUID-based filenames for uploads
- Stripe webhook signature verification

## Immutability Pattern
All services return new objects, never mutate in place:
```python
# GOOD
def update_user_tier(user, new_tier):
    user.tier = new_tier
    return user

# BAD
def update_user_tier(user, new_tier):
    user.tier = new_tier  # Mutates without returning
```

## Curriculum Module (slides + companion artifacts)

The site hosts the NewWhale Career interview-prep curriculum. PNGs and companion files are served from `slides_data/` and produced by a sibling repo.

### How it fits together
- **Source of truth for slides:** `dylanlee20/NewWhale-Career-Slides` (the "Banking Slides" repo). JSON specs render to PPTX and PNG via a frozen v1.3 Python engine. Read its `STATUS.md` and `docs/QM-SERIES-PLAYBOOK.md` before adding decks.
- **Live serving:** this repo. `services/slides_service.py` auto-discovers any deck dropped into `slides_data/decks/<section_slug>/<deck_slug>/slide_NNN.png` (3-digit, `slide_` prefix). 5-minute in-process cache.

### Folder layout under `slides_data/`
```
slides_data/
├── decks/
│   ├── 01-behavioral-and-fit/         B01-B10
│   ├── 02-technical-generalist/       N01-N13 (IB technical)
│   ├── 03-industry-specific/          I01-I18
│   ├── 04-sales-and-trading/          s01-s12
│   ├── 05-quant/                      q01-q15 (concept decks)
│   ├── 07-modeling-quant/             qm01+ (hands-on Quant Modeling, in progress)
│   │   └── qm01-strategy-concepts/
│   │       ├── slide_001.png
│   │       └── ...slide_NNN.png
│   └── 08-consulting/                 c01-c13 (Consulting Technical Curriculum, 234 slides)
└── files/
    ├── 07-modeling-quant/             companion artifacts per deck
    │   └── qm01-strategy-card.pdf
    └── 08-consulting/                 consulting companion PDFs (drills, structuring bank, worked case, econ card)
```

### Slug conventions
- Section slug: `NN-words-with-dashes` (e.g. `07-modeling-quant`). Display title is overridden in `SECTION_TITLE_OVERRIDES` (`services/slides_service.py`); falls back to slug humanization.
- Deck slug: `<prefix><N>-words-with-dashes` (e.g. `qm01-strategy-concepts`). Prefix is 1-3 lowercase letters followed by 1-3 digits, validated by `_humanize` regex `[a-z]{1,3}\d{1,3}`. Display title becomes `QM01 Strategy Concepts`.
- Slide filenames: `slide_NNN.png` (3-digit, `slide_` prefix). The Banking Slides engine emits `page_NN.png`; rename on deploy.

### Routes (all auth-required)
- `/curriculum/behavioral` - section 01 only
- `/curriculum/technical` - sections 02-07
- `/curriculum/<deck_slug>/<n>` - deck viewer (any deck, any section)
- `/curriculum/<deck_slug>/<n>/image.png` - watermarked PNG stream
- `/curriculum/files/<section_slug>/<filename>` - companion artifact download (PDF, ipynb, csv, xlsx, py, md, txt only; path-traversal blocked; max one subdirectory)

### Adding a new deck
1. Author the spec in the Banking Slides repo (`spec/<CODE>.json`)
2. Render and QA there (`python -m engine.render spec/<CODE>.json`, then inspect)
3. Copy the resulting PNGs into `slides_data/decks/<section>/<deck-slug>/`, renaming `page_NN.png` to `slide_NNN.png`
4. Drop companion artifacts (if any) into `slides_data/files/<section>/`
5. If the section is new, add a `SECTION_TITLE_OVERRIDES` entry in `services/slides_service.py`
6. Commit and push to `master`. GitHub Action auto-deploys to VPS.

### Companion file discovery
Companion files in `slides_data/files/<section_slug>/` are now auto-surfaced in the curriculum index as a "Companion resources" row per section (via `slides_service.list_section_files()` + `curriculum_index.html`). Drop an allowlisted file into the section's files folder and it appears as a download chip. No per-deck wiring needed.

### Watermarking
PNGs are watermarked per-request with the viewer's email and client IP via `render_watermarked_png()`. Companion files are not watermarked (they are meant to be carryable references). Treat PDFs as low-IP-risk material; do not put answer keys or model solutions in the companion file path.

## Current Status
✅ Phase 1: Foundation complete
✅ Phase 2: AI-Proof filtering complete (core logic)
✅ Phase 3: Resume assessment (basic upload + parse + LLM assessment working)
✅ Phase 4: Payment integration (Stripe checkout, webhooks, subscription management)
⏳ Phase 5: User experience overhaul (in progress)
⏳ Phase 6: Resume builder 3-mode system
⏳ Phase 7: Cold email outreach (annual plan)
⏳ Phase 8: UI polish & deployment

## Active Development Goals

### Goal 1: Smooth Registration & Public Landing Page
- Public landing page showing all features BEFORE requiring login
- Smooth email-based registration with real-time validation
- Auto-login after registration
- Guest can browse jobs, see pricing, understand features without account

### Goal 2: 3-Mode Resume System
- **Mode 1 - Build from Scratch**: Guided form where user enters info (education, experience, skills, etc.) and AI generates a professional resume
- **Mode 2 - Format Draft**: User pastes unformatted resume text, AI reformats it professionally
- **Mode 3 - Improve Existing**: User uploads existing resume
  - FREE: AI assessment with score + recommendations
  - PAID: Direct AI-powered improvements with highlighted before/after comparisons

### Goal 3: Cold Email Outreach (Annual Plan Only)
- Input: company name, contact email, email template, preloaded resume
- Bulk send personalized cold emails
- Track opens and replies
- Annual plan exclusive feature

### Pricing
- **Free**: Job listings, 3 resume assessments/day, resume builder (basic)
- **Premium Monthly ($30/mo)**: Unlimited assessments, AI resume revision with before/after, resume builder (all modes)
- **Premium Annual ($252/yr)**: Everything in monthly + Cold Email outreach system, career coaching (coming)
