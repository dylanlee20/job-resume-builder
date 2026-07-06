"""Front-office finance role classification.

The tracker only surfaces *front-office* finance roles — the client-facing,
revenue-generating, judgement-heavy seats (banking, markets, research,
investing) that are also the roles most resistant to AI automation. Everything
else (technology, operations/back office, middle office, compliance, legal,
audit, accounting, HR, marketing, retail/consumer banking, admin) is tagged
EXCLUDED and hidden from the default view.

`classify_ai_proof_role(title, description)` returns
`(is_front_office: bool, category: str)` where `category` is one of the
front-office divisions below or the literal string ``'EXCLUDED'``.

The historical column names on the Job model are `is_ai_proof` /
`ai_proof_category`; "AI-proof" and "front office" are the same concept here,
so we keep those names to avoid a schema churn.
"""
import re

# Front-office division labels (also used as the UI "Division" facet).
IB = "Investment Banking"
ST = "Sales & Trading"
RESEARCH = "Equity Research"
AWM = "Asset & Wealth Management"
PE = "Private Equity & VC"
QUANT = "Quant"
RISK = "Risk"
STRUCTURING = "Structuring"

FRONT_OFFICE_CATEGORIES = [IB, ST, RESEARCH, AWM, PE, QUANT, RISK, STRUCTURING]
EXCLUDED = "EXCLUDED"


# Technology / engineering titles — checked against the TITLE ONLY so that a
# "Software Engineer, Trading Systems" is excluded even though its description
# is full of trading keywords.
_TECH_TITLE = [
    "software engineer", "software developer", "developer", "programmer",
    "sre", "site reliability", "devops", "platform engineer",
    "infrastructure engineer", "cloud engineer", "backend engineer",
    "frontend engineer", "front end engineer", "full stack", "fullstack",
    "data engineer", "machine learning engineer", "ml engineer",
    "ai engineer", "systems engineer", "network engineer",
    "security engineer", "solutions architect", "cloud architect",
    "systems architect", "web developer", "mobile developer",
    "ios developer", "android developer", "qa engineer", "test engineer",
    "automation engineer", "engineering manager", "scrum master",
    "product owner", "product manager", "ux designer", "ui designer",
    "designer", "database administrator", "dba", "it support",
    "help desk", "helpdesk", "technical support", "support engineer",
]

# Retail / consumer banking titles — high-volume branch roles that would
# otherwise swamp the tracker. Checked against the TITLE only.
_RETAIL_TITLE = [
    "teller", "personal banker", "branch manager", "branch",
    "relationship banker", "financial center", "financial centre",
    "consumer banker", "retail banker", "bank teller", "customer service",
    "call center", "call centre", "contact center", "client service associate",
    "member service", "loan officer", "mortgage advisor", "mortgage loan",
    "financial solutions advisor", "personal financial",
]

# Divisions and the keywords that identify them. Lower-cased; matched against
# the title first (strongest signal) then title+description.
_FRONT_OFFICE = {
    IB: [
        "investment banking", "investment banker", "m&a", "m & a",
        "mergers and acquisitions", "mergers & acquisitions",
        "capital markets", "ecm", "dcm", "equity capital markets",
        "debt capital markets", "leveraged finance", "levfin",
        "corporate finance", "financial sponsors", "sponsor coverage",
        "industry coverage", "coverage banker", "restructuring",
        "financial advisory", "strategic advisory", "corporate development",
        "corporate broking", "syndicate", "origination", "pitchbook",
        "fairness opinion", "valuation advisory",
    ],
    ST: [
        "sales and trading", "sales & trading", "sales trader",
        "equity sales", "fixed income sales", "credit sales", "rates sales",
        "fx sales", "forex sales", "commodities sales", "derivatives sales",
        "institutional sales", "prime brokerage", "prime services",
        "market maker", "market making", "flow trading", "prop trading",
        "proprietary trading", "execution services", "execution trader",
        "agency trading", "delta one", "cash equities", "electronic trading",
        "rates trader", "credit trader", "equity trader", "commodity trader",
        "fx trader", "forex trader", "options trader", "futures trader",
        "bond trader", "trading desk", "trader", "securities sales",
        "global markets",
    ],
    RESEARCH: [
        "equity research", "credit research", "fixed income research",
        "macro research", "economic research", "investment research",
        "research analyst", "research associate", "sell-side research",
        "buy-side research", "sector analyst", "equity analyst",
        "securities research", "strategy research", "quantitative research analyst",
    ],
    AWM: [
        "portfolio management", "portfolio manager", "investment management",
        "investment manager", "fund manager", "asset management",
        "asset manager", "wealth management", "wealth manager",
        "wealth advisor", "wealth adviser", "private wealth", "private bank",
        "private banker", "relationship manager", "family office",
        "alternative investments", "hedge fund", "multi-asset",
        "equity portfolio", "fixed income portfolio", "investment advisory",
        "investment counselor", "investment strategist", "client portfolio",
        "discretionary portfolio",
    ],
    PE: [
        "private equity", "buyout", "growth equity", "venture capital",
        "principal investing", "principal investment", "direct investment",
        "co-investment", "fund investing", "infrastructure investment",
        "real estate investment", "real assets", "secondaries",
        "credit investing", "distressed investing", "special situations",
    ],
    QUANT: [
        "quantitative research", "quantitative researcher", "quant research",
        "quant researcher", "quant trader", "quantitative trader",
        "quantitative analyst", "quantitative strategist", "quant strategist",
        "systematic trading", "systematic strategies", "quant developer",
        "quantitative developer", "algorithmic trading", "algo trading",
        "statistical arbitrage",
    ],
    RISK: [
        "market risk", "credit risk", "counterparty risk", "trading risk",
        "risk management", "risk manager", "risk analytics", "quantitative risk",
        "model risk", "liquidity risk", "enterprise risk", "portfolio risk",
        "var", "value at risk", "cva", "xva", "stress testing",
    ],
    STRUCTURING: [
        "structuring", "structured products", "structured finance",
        "structured credit", "structured rates", "derivatives structuring",
        "equity structuring", "credit structuring", "rates structuring",
        "fx structuring", "commodity structuring",
    ],
}

# Roles susceptible to automation / clearly outside the front office.
_EXCLUDED_KEYWORDS = [
    # Accounting / tax / controllers
    "accountant", "accounting", "bookkeeping", "accounts payable",
    "accounts receivable", "general ledger", "financial reporting",
    "statutory reporting", "tax reporting", "tax analyst", "tax associate",
    "controller", "fp&a", "financial planning and analysis",
    # Audit / assurance
    "audit", "auditor", "internal audit", "external audit", "assurance",
    "sarbanes-oxley", "sox ",
    # Back / middle office & operations
    "back office", "middle office", "settlement", "reconciliation",
    "trade support", "operations analyst", "operations associate",
    "operations manager", "transaction processing", "clearing", "custody",
    "fund administration", "fund accounting", "transfer agency",
    "collateral management", "corporate actions", "trade lifecycle",
    "client onboarding", "kyc", "aml", "know your customer",
    # Compliance / regulatory / legal
    "compliance", "regulatory reporting", "sanctions", "surveillance",
    "financial crime", "legal counsel", "attorney", "paralegal",
    "regulatory affairs",
    # Data-entry / reporting analysts / BI
    "data entry", "data analyst", "reporting analyst", "reporting coordinator",
    "business intelligence", "data visualization", "management information",
    # Corporate functions
    "human resources", "recruiter", "recruiting", "talent acquisition",
    "talent management", "learning and development", "marketing",
    "communications", "public relations", "brand ", "content ",
    "administrative", "executive assistant", "office manager", "receptionist",
    "facilities", "procurement", "vendor management", "real estate facilities",
    "investor relations", "corporate communications",
]

# Titles that read as senior / strategic front-office leadership keep their
# front-office status even if an EXCLUDED keyword appears in the description.
_SENIOR_STRATEGIC = [
    "head of", "global head", "chief", "managing director", "partner",
    "director of", "vp of", "vice president of",
]


def _title_hit(title_lower, keywords):
    return any(kw in title_lower for kw in keywords)


def classify_ai_proof_role(title, description=""):
    """Classify a posting as front-office finance or EXCLUDED.

    Returns ``(is_front_office: bool, category: str)``.
    """
    if not title or not title.strip():
        return (False, EXCLUDED)

    title_lower = title.lower()
    text = f"{title} {description}".lower()
    text = re.sub(r"\s+", " ", text)

    # 1. Hard title guards — a tech or retail/consumer title is never front office.
    if _title_hit(title_lower, _TECH_TITLE):
        return (False, EXCLUDED)
    if _title_hit(title_lower, _RETAIL_TITLE):
        return (False, EXCLUDED)

    is_senior_strategic = any(term in title_lower for term in _SENIOR_STRATEGIC)

    # 2. Excluded functions (unless a senior-strategic front-office title).
    if not is_senior_strategic and any(kw in text for kw in _EXCLUDED_KEYWORDS):
        # A front-office title keyword still rescues an otherwise-excluded desc
        # (e.g. "Equity Trader — Operations rotation" stays Sales & Trading).
        for category, keywords in _FRONT_OFFICE.items():
            if _title_hit(title_lower, keywords):
                return (True, category)
        return (False, EXCLUDED)

    # 3. Front-office match: title first (strong), then title+description.
    for category, keywords in _FRONT_OFFICE.items():
        if _title_hit(title_lower, keywords):
            return (True, category)
    for category, keywords in _FRONT_OFFICE.items():
        if any(kw in text for kw in keywords):
            return (True, category)

    # 4. No signal -> conservatively exclude.
    return (False, EXCLUDED)


# Backwards-compatible alias for older call sites.
classify_front_office = classify_ai_proof_role
