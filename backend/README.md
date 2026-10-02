# MatchGuard Backend

MatchGuard is an internal tool for The Date Crew. It helps matchmakers check whether a
candidate profile conflicts with a client's known preferences before the profile is sent.

Current state: FastAPI app with a deterministic matching engine, SQLAlchemy models,
PostgreSQL, and deterministic demo data. Endpoints:

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | API name |
| GET | `/health` | Liveness check (does not touch the database) |
| GET | `/api/clients` | All clients: `id`, `name` |
| GET | `/api/clients/{client_id}` | One client with their preferences (sorted by attribute); 404 if unknown |
| GET | `/api/profiles` | All candidate profiles with the fields used for matching |
| POST | `/api/matches/check` | Check one profile against one client and record the result |
| POST | `/api/feedback/analyze` | Turn free-text rejection feedback into structured reasons and save it |
| GET | `/api/analytics/summary` | Read-only counts from saved match checks, plus the assessment baseline |

There are no create/update/delete endpoints yet, and no auth. AI is used only for feedback
extraction, never for match decisions.

## Architecture

```
React + TypeScript   ../frontend, http://localhost:5173 (CORS allowed)
        ↓
FastAPI              app/main.py, app/api/routes/
        ↓                     ↘
SQLAlchemy 2.x       app/models/    MatchEngine (pure Python, app/services/)
        ↓
PostgreSQL           via psycopg 3
```

The route loads rows from the database, converts them to Pydantic inputs
(`app/schemas/matching.py`), calls `MatchEngine.check()`, then saves the result. The engine
itself never touches the database, HTTP, or an LLM.

## Match check

`POST /api/matches/check` with `{"client_id": "<uuid>", "profile_id": "<uuid>"}` returns:

```json
{
  "decision": "BLOCK",
  "conflicts": [
    {
      "kind": "VIOLATION",
      "attribute": "smoking",
      "candidate_value": true,
      "expected_value": false,
      "preference_type": "DEAL_BREAKER",
      "reason": "Candidate smokes, while smoking is marked as a client deal-breaker."
    }
  ]
}
```

Each call stores a `match_checks` row and one `match_conflicts` row per conflict,
including its `kind`.
Unknown client or profile returns 404; database errors roll back and return 500.

Supported preference attributes and value formats:

| Attribute | Value format | Comparison |
|---|---|---|
| `age` | `{"min": 28, "max": 35}` (either bound optional) | Inclusive range |
| `smoking`, `drinking`, `wants_children` | `true` / `false` | Exact |
| `location`, `religion`, `education`, `occupation` | `"Hindu"` or `["Delhi NCR", "Noida"]` | Case-insensitive, trimmed, any of the list |

Every conflict has a `kind`:

| Kind | Meaning |
|---|---|
| `VIOLATION` | The candidate's value was compared and does not satisfy the preference |
| `MISSING_DATA` | The candidate has no value for an attribute the client cares about |
| `INVALID_PREFERENCE` | The client's preference value is in an unsupported format |
| `UNSUPPORTED_ATTRIBUTE` | The preference is for an attribute the engine does not know |

Decision rules:

1. **BLOCK** if any conflict is a `VIOLATION` of a `DEAL_BREAKER` preference.
2. **REVIEW** otherwise, if there is any conflict at all.
3. **PASS** if nothing was flagged.

So `HARD`/`SOFT` violations and every non-`VIOLATION` kind (including missing data on a
deal-breaker) go to a matchmaker for review; they never block.

## Rejection feedback analysis

`POST /api/feedback/analyze` with

```json
{"client_id": "<uuid>", "profile_id": "<uuid>", "raw_feedback": "Nice profile but I don't want a smoker."}
```

returns the saved row:

```json
{
  "id": "<uuid>",
  "client_id": "<uuid>",
  "profile_id": "<uuid>",
  "raw_feedback": "Nice profile but I don't want a smoker.",
  "structured_feedback": {
    "reasons": [
      {
        "attribute": "smoking",
        "value": true,
        "preference_type": "DEAL_BREAKER",
        "kind": "VIOLATION",
        "explanation": "Feedback explicitly rules out a partner who smokes (\"don't want\")."
      }
    ],
    "needs_review": false
  }
}
```

1. Unknown client or profile returns 404. This is checked before any extraction runs.
2. Blank feedback, feedback over 5,000 characters, or an invalid payload returns 422.
   Leading and trailing whitespace is stripped.
3. The configured extractor turns the text into a `StructuredFeedback`
   (`app/schemas/feedback.py`).
4. `raw_feedback` and the validated JSON are stored in the existing `rejection_feedback`
   table.
5. If the extractor is unavailable (AI provider selected but no key, timeout, network error,
   rate limit, rejected key or unusable output), the API returns 503 with a short message.
   Nothing is saved and no SDK details are exposed.

The output has no decision or score fields. `needs_review` is forced to `true` by a
validator when a reason is `UNCLEAR`, uses `other`, or no reasons were found.

Extractors are chosen with `FEEDBACK_EXTRACTOR`. All implement the `FeedbackExtractor`
protocol, and `create_feedback_extractor()` in `app/services/feedback_extractor.py` maps the
value to a class. Unknown values fail at startup (in `Settings`) and in the factory; there
is no silent fallback. The provider can be changed through `FEEDBACK_EXTRACTOR` without
changing the rest of the application.

- **`demo`**: `demo_feedback_extractor.py`. Local deterministic fallback, no API key
  required. **Not AI.** Keyword rules for smoking, drinking, location, children and age.
  The rules are deliberately simple: anything they don't recognise becomes an
  `other` / `UNCLEAR` reason that needs review.
- **`gemini`** (default): `gemini_feedback_extractor.py`. Primary prototype AI provider
  using Gemini structured output; not production-ready. Uses the official `google-genai`
  SDK: `genai.Client(api_key=...).models.generate_content()` with
  `response_mime_type="application/json"` and `response_schema=StructuredFeedback`, so the
  SDK returns a validated `StructuredFeedback` in `response.parsed`; output that does not
  match the schema becomes a 503. It sends the system prompt from `feedback_prompt.py` as
  `system_instruction` and uses thinking level `MINIMAL` for low latency. No tools,
  grounding or function calling. 30-second timeout, 3 attempts. The model comes from
  `GEMINI_MODEL` (default `gemini-3.5-flash-lite`). Failures are logged with provider,
  model, exception class, HTTP status and error status only.
- **`openai`**: optional alternative provider. `openai_feedback_extractor.py`. Calls `client.responses.parse()` with
  `text_format=StructuredFeedback`, which uses Structured Outputs, so the SDK validates the
  response against the Pydantic model. It sends the system prompt from
  `feedback_prompt.py` as `instructions` and uses `temperature=0` with reasoning effort
  `none` for low variance. It also sets `store=False`, a 30-second timeout and 2 retries.
  The model comes from `OPENAI_MODEL` (default `gpt-6-luna`). The client can be injected,
  which is how tests use a fake one.

## Analytics summary

`GET /api/analytics/summary` aggregates the saved `match_checks` and `match_conflicts`
rows with `GROUP BY` queries (`app/services/analytics.py`). It writes nothing. After
`seed.py` and `demo_checks.py` (demo data only) it returns:

```json
{
  "total_checks": 19,
  "decisions": {"pass": 5, "review": 7, "block": 7},
  "decision_rates": {"pass": 0.2632, "review": 0.3684, "block": 0.3684},
  "conflicts": {
    "violations": 26,
    "deal_breaker_violations": 9,
    "missing_data": 4,
    "unsupported_attributes": 0,
    "invalid_preferences": 0
  },
  "assessment_baseline": {
    "profiles_shared": 1000,
    "rejected_profiles": 690,
    "preference_violation_rejection_rate": 0.35,
    "estimated_preference_violation_rejections": 241.5,
    "...": "other figures from the brief"
  }
}
```

- Rates are `count / total_checks`, rounded to 4 decimals, and `0.0` when there are no
  checks.
- `violations` counts every `VIOLATION` conflict. `deal_breaker_violations` counts only
  those on a `DEAL_BREAKER`; missing data on a deal-breaker is counted under
  `missing_data`.
- Every saved check is counted, including repeat checks of the same pair.
- `assessment_baseline` comes from `app/core/assessment.py`. These are the monthly numbers
  supplied by the assessment brief, **not measured by MatchGuard**.
  `estimated_preference_violation_rejections` is 690 × 0.35 = 241.5 (shown as "~242"), a
  derived estimate rather than an observed result.

## Demo data

`seed.py` loads 5 clients (Rahul, Priya, Arjun, Sneha, Karan), 16 candidate profiles and
27 preferences. From `backend/`:

```powershell
python seed.py
```

It creates the tables if needed, then deletes and recreates only the demo records (they have
fixed UUIDs, so IDs stay the same between runs; any match checks attached to demo records
are removed too). Other data is left alone. It prints counts plus the intended demo
pairings, which cover PASS, REVIEW and BLOCK for every client, missing data, multiple
conflicts, deal-breakers and soft conflicts. The pairings are listed in `SCENARIOS` in
`seed.py`, and `tests/test_seed.py` checks each one.

To save checks for those 19 pairings (so analytics and the Impact tab have data), run
after `seed.py`:

```powershell
python demo_checks.py
# or, with Docker:
docker compose exec api python seed.py
docker compose exec api python demo_checks.py
```

`demo_checks.py` loads each demo client's preferences and candidate from the database, runs
the real `MatchEngine`, and saves a `match_checks` row plus its `match_conflicts` (with
`kind`), the same way `POST /api/matches/check` does. Nothing is hardcoded: it prints the
engine's totals and warns if a decision differs from the expectation in `SCENARIOS`.

Each scenario check has a fixed ID (`demo_id("check", "Client:Profile")`), so a re-run
deletes only those 19 checks and their conflicts before recreating them. Clients, profiles,
preferences, rejection feedback and other match checks, including manual checks of the
same pairs, are kept. If the demo clients or profiles don't exist, it stops and asks you to
run `seed.py` first. `tests/test_demo_checks.py` covers this.

These are deterministic demo scenarios. The resulting analytics are demonstration data,
not The Date Crew's business metrics.

## Project structure

```
date-crew-matchguard/
├── docker-compose.yml          # postgres + api services
└── backend/
    ├── app/
    │   ├── main.py             # FastAPI app, CORS, / and /health, router registration
    │   ├── api/routes/         # clients.py, profiles.py, matches.py, feedback.py, analytics.py
    │   ├── core/assessment.py  # Baseline figures from the assessment brief (not measured)
    │   ├── core/config.py      # Settings loaded from environment / .env
    │   ├── core/enums.py       # PreferenceType, Decision, ConflictKind (no dependencies)
    │   ├── db/base.py          # DeclarativeBase, JSON column type
    │   ├── db/database.py      # Engine, session factory, get_db, init_db
    │   ├── models/             # One file per table; __init__ imports all of them
    │   ├── schemas/matching.py # Pydantic inputs/outputs for matching
    │   ├── schemas/directory.py  # Client and profile list responses
    │   ├── schemas/feedback.py # Structured feedback schema and request/response
    │   ├── schemas/analytics.py  # Analytics summary response
    │   └── services/
    │       ├── match_engine.py               # Deterministic MatchEngine
    │       ├── analytics.py                  # Read-only aggregates over saved checks
    │       ├── feedback_extractor.py         # FeedbackExtractor protocol, errors, provider choice
    │       ├── feedback_prompt.py            # System prompt shared by the AI providers
    │       ├── gemini_feedback_extractor.py  # Gemini (google-genai) + structured output
    │       ├── openai_feedback_extractor.py  # OpenAI Responses API + Structured Outputs
    │       └── demo_feedback_extractor.py    # Local keyword rules (not AI)
    ├── seed.py                 # Deterministic demo data
    ├── demo_checks.py          # Saves real engine checks for the 19 demo scenarios
    ├── tests/
    │   ├── conftest.py         # In-memory SQLite database wired into the app
    │   ├── test_health.py      # /health endpoint
    │   ├── test_models.py      # Models against in-memory SQLite
    │   ├── test_match_engine.py  # Pure engine rules and explanations
    │   ├── test_matches_api.py # Match-check endpoint
    │   ├── test_directory_api.py  # Client and profile list endpoints
    │   ├── test_seed.py        # Seed counts, repeatability and demo scenarios
    │   ├── test_config.py      # Settings defaults, env parsing, keys hidden from repr
    │   ├── test_feedback_api.py  # Feedback endpoint (demo/fake extractors, no live AI calls)
    │   ├── test_feedback_extractor.py  # Demo rules and schema validation
    │   ├── test_gemini_feedback_extractor.py  # Gemini contract tests with a fake client
    │   ├── test_openai_feedback_extractor.py  # OpenAI contract tests with a fake client
    │   ├── test_analytics_api.py  # Analytics aggregates and assessment baseline
    │   └── test_demo_checks.py # Demo scenario checks: counts, reruns, what is kept
    ├── Dockerfile
    ├── .env.example
    └── requirements.txt
```

## Local Python setup

Run from the `backend/` directory (Python 3.11+; Windows PowerShell shown):

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

On macOS/Linux use `python3 -m venv .venv`, `source .venv/bin/activate` and `cp`.

Settings are read from `.env` (or the environment):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/matchguard` | Database |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated frontend origins allowed by CORS, e.g. `http://localhost:5173,https://example.vercel.app`. `*` is rejected at startup |
| `FEEDBACK_EXTRACTOR` | `gemini` | `demo`, `gemini` or `openai`; any other value fails at startup |
| `GEMINI_API_KEY` | empty | Only needed for `gemini`. The app still starts without it; analysis then returns 503 |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model for the `gemini` provider |
| `OPENAI_API_KEY` | empty | Only needed for `openai`. The app still starts without it; analysis then returns 503 |
| `OPENAI_MODEL` | `gpt-6-luna` | Model for the `openai` provider |

`.env` is gitignored. Put the real key only there, never in `.env.example` or the code.
Docker Compose loads `backend/.env` into the API container if the file exists (its
`DATABASE_URL` is overridden to point at the `postgres` service).

## Docker setup

From the project root (the folder containing `docker-compose.yml`):

```powershell
docker compose up -d --build
docker compose exec api python seed.py
```

The first command starts PostgreSQL (port 5432) and the API (port 8000); the API waits for
the PostgreSQL healthcheck to pass. The second creates the tables and loads demo data
(use `python -m app.db.database` instead to create empty tables only).

To run only PostgreSQL in Docker and the API locally:

```powershell
docker compose up -d postgres
cd backend
python seed.py
```

Stop everything with `docker compose down` (add `-v` to also delete the database volume).

## Running the API

Locally, from `backend/` with the virtual environment active:

```powershell
uvicorn app.main:app --reload
```

- `GET /` returns `{"message": "MatchGuard API"}`
- `GET /health` returns `{"status": "ok"}` (does not touch the database)
- Interactive docs: http://localhost:8000/docs

## Running tests

From `backend/`:

```powershell
python -m pytest
```

Tests do not need PostgreSQL or any AI provider key. Engine tests are pure Python; model and API
tests use an in-memory SQLite database (the API test overrides `get_db`). The feedback API
tests swap in the demo extractor or a fake Gemini client, and the Gemini and OpenAI tests use
fake clients, so no real API calls are made.

## Database schema

Tables are created with `Base.metadata.create_all` (`python -m app.db.database`).
There are no migrations yet, so changing a model on an existing database means dropping
and recreating the tables. The one exception is `match_conflicts.kind`: `init_db()` adds it
to an older table and backfills existing rows from their reason text. After pulling this
change, rebuild and run it once:

```powershell
docker compose up -d --build
docker compose exec api python -m app.db.database
```

| Table | Purpose | Key columns |
|---|---|---|
| `clients` | People the matchmakers work for | `name` |
| `client_preferences` | A client's preference on one attribute | `client_id`, `attribute`, `value` (JSONB), `preference_type` |
| `profiles` | Candidate profiles | `name`, `age`, `location`, `smoking`, `drinking`, `wants_children`, `religion`, `education`, `occupation` (all optional except `name`) |
| `match_checks` | Result of checking a profile against a client | `client_id`, `profile_id`, `decision` |
| `match_conflicts` | Individual conflicts found in a check | `match_check_id`, `attribute`, `candidate_value`, `expected_value`, `preference_type`, `reason` |
| `rejection_feedback` | Why a client rejected a profile | `client_id`, `profile_id`, `raw_feedback`, `structured_feedback` (JSONB) |

Relationships: a client has many preferences, match checks and rejection feedback entries;
a profile has many match checks and rejection feedback entries; a match check has many
conflicts. Deleting a parent deletes its children (`ON DELETE CASCADE`).

Conventions:

- Every table has a UUID `id`, generated in Python with `uuid.uuid4`.
- `created_at` is `TIMESTAMP WITH TIME ZONE`, defaulting to `now()` in the database
  (`match_conflicts` has no `created_at`; it shares its check's timestamp).
- `preference_type` is one of `DEAL_BREAKER`, `HARD`, `SOFT`; `decision` is one of
  `PASS`, `REVIEW`, `BLOCK`. Both are stored as `VARCHAR(20)` and validated by SQLAlchemy.
- JSON columns accept ranges (`{"min": 28, "max": 35}`), booleans, strings and lists.
  Python `None` is stored as SQL `NULL`.
