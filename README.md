# NewWhale Career v2

> AI-Proof Industries Job Tracker with Resume Assessment & Revision

## 🎯 Features

- **AI-Proof Job Focus**: Exclusively tracks finance roles resistant to AI automation
  - Investment Banking, Sales & Trading, Portfolio Management
  - Risk Management, M&A Advisory, Private Equity
- **Free Resume Assessment**: AI-powered resume analysis with scoring and feedback
- **Paid Resume Revision**: Template-based suggestions using successful resumes
- **Subscription Tiers**: Free and Premium plans via Stripe

## 🚀 Quick Start

```bash
# Clone repository
git clone <repo-url>
cd job-tracker-v2

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your keys

# Run application
python app.py
```

Access at: `http://localhost:5002`

## 📋 Requirements

- Python 3.11+
- SQLite (development) / PostgreSQL (production)
- Stripe account (for payments)
- OpenAI API key (for resume assessment)
- Chrome/Chromium + `chromedriver` (for job scrapers)

### Scraper Runtime Prerequisites

The scraper uses Selenium and needs both a browser binary and `chromedriver`.

```bash
# macOS (Homebrew)
brew install --cask google-chrome
brew install --cask chromedriver

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y chromium chromium-driver
```

If your browser is not in PATH, set `CHROME_BINARY_PATH` in `.env`.
Optionally set `CHROMEDRIVER_PATH` if driver auto-detection fails.

## 🏗️ Architecture

```
┌─────────────┐
│   Flask     │
│ Application │
└──────┬──────┘
       │
┌──────┴──────────────────────┐
│      Routes (Blueprints)     │
│  auth | web | api | admin   │
│  resume | payment            │
└──────┬──────────────────────┘
       │
┌──────┴──────────────────────┐
│      Services (Logic)        │
│  JobService                  │
│  ResumeAssessmentService     │
│  PaymentService              │
└──────┬──────────────────────┘
       │
┌──────┴──────────────────────┐
│     Models (Database)        │
│  User | Job | Resume         │
│  Subscription | Payment      │
└──────────────────────────────┘
```

## 🔧 Configuration

Key environment variables (see `.env.example`):

```bash
SECRET_KEY=<generate-with-python-secrets>
OPENAI_API_KEY=sk-...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
UPLOAD_MAX_SIZE_MB=10
FREE_TIER_DAILY_ASSESSMENTS=3
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=html

# Open coverage report
open htmlcov/index.html
```

## 📦 Deployment

See `DEPLOYMENT.md` for VPS deployment instructions.

## 🤝 Contributing

This is a private project. Contact admin for access.

## 📄 License

Proprietary - All rights reserved

## 📞 Support

For support, email support@newwhaletech.com
