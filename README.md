# MatchGuard

**Problem.** According to the assessment brief, about 35% of profiles rejected by clients
are rejected for reasons already covered by the client's stated preferences or
deal-breakers, which means matchmakers are sending profiles that conflict with what the
client has told them.

**Solution.** An internal tool for The Date Crew. Before a matchmaker sends a candidate profile to a
client, MatchGuard checks the candidate against the client's known preferences and returns
**PASS**, **REVIEW** or **BLOCK**, with a plain-language reason for every conflict.

It can also turn a client's free-text rejection feedback ("Nice profile but I don't want a
smoker.") into structured reasons and save them to the client's rejection history. See
[AI usage](#ai-usage).

## Live Demo

- Frontend: https://date-crew-matchguard.vercel.app/
- Demo Video: https://youtu.be/lGuYglGJ2v0
- GitHub: https://github.com/lvanish/date-crew-matchguard
- Backend API: https://date-crew-matchguard.onrender.com
- Swagger: https://date-crew-matchguard.onrender.com/docs

The live prototype runs on Vercel + Render and uses Supabase PostgreSQL. Gemini is used for
structured rejection-feedback extraction.

## Assessment Demo

Live prototype:
https://date-crew-matchguard.vercel.app/

Demo video:
https://youtu.be/lGuYglGJ2v0

Suggested flow:

1. **Check Match** → Rahul → Ananya → **PASS**
2. **Check Match** → Rahul → Ishita → **BLOCK**
3. **Check Match** → Rahul → Kavya → **REVIEW** (missing data)
4. **Analyze Rejection** → use the multi-reason example: "The profile looks good, but I
   definitely don't want someone who smokes and I cannot move to Bangalore."
5. **Impact** → show the assessment baseline and the 19 deterministic demo checks

How to read the numbers on the Impact tab:

- **Assessment-provided baseline:** the monthly figures from the assessment brief
  (1,000 profiles shared, 690 rejected, 35% preference-related, ~242 estimated). MatchGuard
  did not measure these.
- **Deterministic demo activity:** the PASS / REVIEW / BLOCK and conflict counts come from
  19 designed demo scenarios plus any checks run by hand. They show the tool working, not
  real matchmaking.
- **Actual production business results:** none yet. MatchGuard has not been used in real
  matchmaking, and there is no evidence that it has improved the preference-violation
  rejection rate or any other business metric.

## Architecture

```
React + TypeScript (Vite)      frontend/          http://localhost:5173
        ↓  fetch, JSON
FastAPI                        backend/app/api/   http://localhost:8000
        ↓
MatchEngine                    backend/app/services/match_engine.py
        ↓  (the API loads/saves data around the engine)
PostgreSQL via SQLAlchemy      backend/app/models/, docker-compose.yml
```

- **Frontend** is a single page. It only talks to the API and has no hardcoded client or
  profile data.
- **API** loads the client, their preferences and the candidate from PostgreSQL, hands
  them to the engine, stores the result, and returns it.
- **MatchEngine** is pure Python with deterministic rules. It never touches the database,
  HTTP or an LLM.
  - BLOCK only for a verified deal-breaker violation.
  - REVIEW for any other conflict, missing data, or a preference it can't check.
  - PASS otherwise.
- **Feedback extractor** (`backend/app/services/`) turns rejection feedback into
  structured reasons. It is separate from the engine and never produces a decision.

See [`backend/README.md`](backend/README.md) for the API, the rules and the database schema.

## Prerequisites

- Docker Desktop (for PostgreSQL and the API)
- Node.js 20+ and npm (for the frontend)
- Python 3.11+ only if you want to run the backend or its tests outside Docker

## Start the backend

From the project root:

```powershell
docker compose up -d --build
docker compose exec api python seed.py
docker compose exec api python demo_checks.py
```

This starts PostgreSQL on port 5432 and the API on port 8000. `seed.py` creates the tables
and loads the demo clients and candidates. `demo_checks.py` saves match checks for the 19
demo scenarios, so the Impact tab has something to show. Both are safe to re-run (see
[Demo data](#demo-data)).

Check it: http://localhost:8000/health should return `{"status": "ok"}`, and the
interactive API docs are at http://localhost:8000/docs.

To run the API outside Docker instead, see [`backend/README.md`](backend/README.md).

### Demo data

- **`seed.py`** creates 5 clients, 16 candidate profiles and 27 preferences.
- **`demo_checks.py`** runs the real MatchEngine on 19 client/candidate pairings that were
  designed to cover every outcome: PASS, REVIEW and BLOCK, missing data, soft and hard
  conflicts, deal-breakers and multiple conflicts. It saves each result as a `match_checks`
  row with its `match_conflicts` rows, exactly like a check made in the UI. No decisions
  are hardcoded; the script prints whatever the engine returns:

  ```
  Demo checks created
  -------------------
  Total: 19
  PASS: 5
  REVIEW: 7
  BLOCK: 7
  Conflicts: 30
  ```

- Re-running `demo_checks.py` first deletes only its own 19 checks and their conflicts
  (they have fixed IDs), then recreates them. Clients, profiles, preferences, rejection
  feedback and any checks you ran by hand are kept. Re-running `seed.py` deletes every
  check attached to the demo records, so run `demo_checks.py` again after it.

**The resulting analytics are demonstration data only.** They come from deterministic,
intentionally designed scenarios and must not be read as The Date Crew's actual business
metrics. The Impact tab labels them "Demo activity — generated from 19 deterministic
scenarios". Checks you run by hand are added to those counts.

## Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The API address comes from `VITE_API_BASE_URL` and defaults to
`http://localhost:8000`; copy `frontend/.env.example` to `frontend/.env` to change it.

## Use the demo

The page has three tabs: **Check Match**, **Analyze Rejection** and **Impact**.

### Check Match

1. Pick a **client**. Their preferences appear with their type (Deal-breaker, Hard, Soft).
2. Pick a **candidate**. Their age, location, lifestyle and background are shown.
3. Click **Check match**.

The result shows the decision. Conflicts are grouped into preference conflicts, missing
candidate information, and preferences that could not be checked. Preferences that passed
are listed after them.

Pairings worth trying (each client has at least one of each outcome):

| Client | PASS | REVIEW | BLOCK |
|---|---|---|---|
| Rahul | Ananya | Meera (soft conflict), Kavya (missing smoking data) | Ishita (smoker), Riya (6 conflicts) |
| Priya | Aditya | Rohan (soft conflict), Nikhil (missing education and occupation) | Vikram (smoker) |
| Arjun | Divya | Neha (location) | Sana (religion deal-breaker) |
| Sneha | Harpreet | Siddharth (missing drinking data) | Rohan (drinks), Amit (4 conflicts) |
| Karan | Sana | Tanvi (3 conflicts) | Divya (wants children) |

Every check is saved in the `match_checks` and `match_conflicts` tables.

### Analyze Rejection

1. Pick the **client** and the **candidate** they turned down.
2. Paste what the client said into **Rejection feedback**.
3. Click **Analyze feedback**.

The result lists each structured reason (`attribute`, `value`, `preference_type`, `kind`,
`explanation`) and the
raw feedback. If anything was ambiguous, a **⚠ Needs review** banner asks the matchmaker
to confirm with the client. Each analysis is saved in the `rejection_feedback` table.

### Impact

Shows three things, reloaded every time you open the tab:

1. **Assessment baseline.** The monthly numbers from the assessment brief, clearly labelled
   as assessment-provided: 1,000 profiles shared, 690 rejected, 35% of rejections
   preference-related, so an estimated ~242 preference-related rejections a month (derived
   from the brief, not measured).
2. **MatchGuard activity.** Real counts from `GET /api/analytics/summary`: checks
   performed, PASS / REVIEW / BLOCK counts and shares, and conflict types.
3. **How we would measure success.** The primary metric, its baseline (35%), and
   "After launch: Not measured yet".

## Analytics / Measurement

**Primary business metric: preference-violation rejection rate.** This is the share of
rejected profiles where the client's rejection reason was already covered by an explicit
client preference or deal-breaker. Assessment baseline: 35% of rejected profiles were
reported as preference-related. Estimated avoidable rejection events: about 242 a month
(690 rejected × 35%). That figure is derived from the assessment's numbers, not observed by
MatchGuard. The goal is to reduce this rate materially once MatchGuard is in use.

**Leading indicators** (measured now, from `match_checks` and `match_conflicts`):

- preference conflicts caught before a profile is sent (`VIOLATION` conflicts)
- deal-breakers caught before a profile is sent (`VIOLATION` on a `DEAL_BREAKER`, which is
  what produces BLOCK)
- missing profile information (`MISSING_DATA` conflicts)

**Business outcome:** whether the client accepts or rejects a profile after it is shared,
and why.

MatchGuard is designed to catch these conflicts before a profile is shared. **Post-launch
impact is not yet measured, and the current counts are not proof of business impact:**

- They come from demo data and manual testing, not real matchmaking.
- Every check is counted, including repeat checks of the same pair.
- A caught conflict only shows that MatchGuard flagged something. It doesn't show that the
  profile would have been rejected, or that the matchmaker then acted differently.
- There's no comparison group and no data on what happened after a profile was shared.

To measure the outcome, each profile-check event needs to be linked to the eventual
profile outcome (accepted or rejected) and the rejection reason. The rejection feedback
saved by **Analyze Rejection** is a first step toward recording those reasons. Then the
preference-violation rejection rate can be compared before and after launch, ideally
across matchmakers or in a staged rollout.

The baseline numbers live in one place, `backend/app/core/assessment.py`.

## AI usage

AI is used for one narrow job: **reading free-text rejection feedback and extracting
structured reasons** from it. It does not make matchmaking decisions. It never returns
PASS, REVIEW or BLOCK, match scores or compatibility scores, and its output does not
change what the MatchEngine decides. The engine stays deterministic.

Each reason has:

| Field | Values |
|---|---|
| `attribute` | `age`, `location`, `smoking`, `drinking`, `wants_children`, `religion`, `education`, `occupation`, `other` |
| `value` | What the feedback mentioned (`true`, `"Bangalore"`, `{"min": null, "max": 35}`), or `null` |
| `preference_type` | `DEAL_BREAKER`, `HARD`, `SOFT`, `UNCLEAR` |
| `kind` | `VIOLATION`, `PREFERENCE`, `UNCLEAR` |
| `explanation` | A short neutral sentence based only on the feedback |

`needs_review` is forced to `true` by the backend whenever a reason is `UNCLEAR`, falls
back to `other`, or nothing could be extracted. The model can't hide uncertainty.

Example: "Nice profile but I don't want a smoker." becomes

```json
{
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
```

The attribute is Smoking, the preference type is DEAL_BREAKER, and the kind is VIOLATION.

### AI Providers

The provider can be changed through `FEEDBACK_EXTRACTOR` without changing the rest of the
application. All three return the same `StructuredFeedback` shape, so the API, database and
React app are unaffected.

| `FEEDBACK_EXTRACTOR` | What it does |
|---|---|
| `demo` | Local deterministic fallback. No API key required. **Not AI.** Keyword rules (`demo_feedback_extractor.py`) for smoking, drinking, location, children and age; anything else goes to review. Works offline. |
| `gemini` (default) | Primary prototype AI provider using Gemini structured output. Uses the official `google-genai` SDK with the `StructuredFeedback` Pydantic model as the response schema, so the SDK returns a validated object; there is no free-text parsing. Prototype only, not production-ready. |
| `openai` | Optional alternative provider. Calls OpenAI's Responses API with Structured Outputs against the same schema. |

Both AI providers use the same system prompt (`feedback_prompt.py`). Missing keys,
timeouts, network errors, rejected keys, rate limits and malformed output all return a
clean `503` with no SDK details.

Example configuration:

```
FEEDBACK_EXTRACTOR=gemini
GEMINI_MODEL=gemini-3.5-flash-lite
```

### Environment variables

Set these in `backend/.env` (copy `backend/.env.example`). Docker Compose reads the same
file if it exists.

| Variable | Default | Purpose |
|---|---|---|
| `FEEDBACK_EXTRACTOR` | `gemini` | `demo`, `gemini` or `openai` |
| `GEMINI_API_KEY` | empty | Only needed for `gemini` |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model used by the `gemini` provider |
| `OPENAI_API_KEY` | empty | Only needed for `openai` |
| `OPENAI_MODEL` | `gpt-6-luna` | Model used by the `openai` provider |
| `DATABASE_URL` | local PostgreSQL | See `backend/README.md` |

With the default `gemini` provider and no `GEMINI_API_KEY`, the app still starts but feedback
analysis returns 503. Set `FEEDBACK_EXTRACTOR=demo` to run without any key.

To use an AI provider with Docker, put `FEEDBACK_EXTRACTOR` and the matching key in
`backend/.env`, then run `docker compose up -d --build`.

### Security

- API keys only live in `backend/.env`, which is gitignored (`.gitignore` ignores
  every `.env*` except `.env.example`). `.env.example` contains placeholders only.
- Docker Compose passes `backend/.env` to the API container at runtime; the file is never
  copied into the image (`backend/.dockerignore` excludes it).
- The browser never sees any key. The React app only calls the FastAPI backend
  (`POST /api/feedback/analyze`); only the backend talks to Gemini or OpenAI.
- Keys are hidden from the settings `repr`. Provider errors are logged with safe fields
  only (provider, model, exception class, HTTP status, error code; OpenAI also logs its
  request ID and an error message with keys redacted), never keys, headers or the raw SDK
  exception. OpenAI requests also use `store=False`.
- The system prompt tells the model to treat the feedback as data and ignore any
  instructions inside it. Even so, the output can only take the shape of the schema.

## Tests

```powershell
cd backend
python -m pytest        # needs the backend virtual environment, see backend/README.md

cd ../frontend
npm test
npm run build
```

Neither test suite needs PostgreSQL, a running API or any AI provider key. The Gemini and
OpenAI providers are tested against fake clients, so no real API calls are made.

## Not built yet

Authentication, ranking, outcome tracking after a profile is shared, viewing past
rejection feedback, using it in match checks, and create/edit screens for clients,
preferences and profiles.
