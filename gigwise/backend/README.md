# Gigwise backend

A Python API (FastAPI) that stores Gigwise data in Supabase (PostgreSQL) and runs the match score on the server.

```
Browser (gigwise/frontend)  ->  this API (FastAPI)  ->  Supabase (database)
```

The frontend still runs on its own with browser-only demo data. Connecting it to this API is the next step.

## What's here

| Path | What it is |
|---|---|
| `app/main.py` | The API endpoints |
| `app/matching.py` | The match score: same formula and results as the frontend |
| `app/db.py` | Supabase connection, reads settings from `.env` |
| `sql/schema.sql` | Database tables, to run once in Supabase |
| `seed/` | Demo data and the script that loads it |
| `tests/` | Checks that the Python score matches the frontend |
| `.env.example` | Template for your settings. Your real `.env` is never committed |

## One-time setup

**1. Create the tables.** In Supabase, open **SQL Editor → New query**, paste all of `sql/schema.sql`, and click **Run**.

**2. Add your keys.** Open `gigwise/backend/.env` and fill in:
- `SUPABASE_SERVICE_ROLE_KEY`: in Supabase, go to **Project Settings → API Keys** and copy the **secret** key. Keep it private; it bypasses all security rules.
- `SUPABASE_URL` is already filled in.

Never paste keys into chat, Slack or GitHub. `.env` is listed in `.gitignore`.

**3. Install** (from `gigwise/backend`):
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**4. Load the demo data:**
```bash
.venv/bin/python -m seed.seed
```
Re-run it any time to reset the demo.

## Run the API

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000/docs to see and try every endpoint in the browser. http://localhost:8000/health tells you whether the database is connected.

## Run the tests

```bash
.venv/bin/python -m unittest discover tests
```

## Endpoints

Full details and a "Try it out" button for each one: http://localhost:8000/docs

| Area | Endpoints |
|---|---|
| System | `GET /health`, `GET /me` (the demo client you act as) |
| Freelancers | `GET /freelancers` (filters: q, category, max_rate, min_rating, available), `GET /freelancers/{id}`, `POST /freelancers` (create profile), `PUT /freelancers/{id}` (edit profile) |
| Projects | `GET /projects` (filters), `GET /projects/{id}`, `POST /projects` (fixed or hourly; detects skills if blank; returns matches) |
| Matching | `GET /projects/{id}/matches`, `GET /freelancers/{id}/matches` (reverse matching) |
| Invites | `POST /projects/{id}/invites` |
| Proposals | `GET /projects/{id}/proposals`, `POST /projects/{id}/proposals` (Connects, screening answers), `PATCH /proposals/{id}`, `POST /proposals/{id}/shortlist`, `/decline`, `/withdraw` |
| Offers | `POST /proposals/{id}/offers` (milestones or hourly terms), `GET /offers`, `GET /offers/{id}`, `POST /offers/{id}/accept`, `/decline`, `/withdraw` |
| Contracts | `GET /contracts`, `GET /contracts/{id}`, `POST /contracts/{id}/milestones/{n}/submit`, `/approve`, `/request-changes`, `POST /contracts/{id}/end` |
| Reviews | `POST /contracts/{id}/reviews` (both directions, after the contract ends; updates rating and Job Success) |
| Saved | `GET/PUT/DELETE /freelancers/{id}/saved-jobs/{project_id}`, `GET /saved-freelancers`, `PUT/DELETE /saved-freelancers/{id}` |
| Chat | `GET /threads`, `GET /threads/{id}/messages`, `POST /threads/{id}/messages`, `POST /threads/{id}/read` |
| Notifications | `GET /notifications`, `POST /notifications/read` |

**Coming next:** connecting the frontend; Claude-written explanations; real login (Supabase Auth); live chat (Supabase Realtime).

## Notes

- **No login yet.** As a client you act as the demo client (Pulse Fit). Freelancer actions take a `freelancer_id`. Anyone who can reach the API can act as anyone, so run it locally only for now.
- **Security.** Every table has Row Level Security on with no rules, so the public anon key can't read anything. Only this backend, using the secret key, can.
- **Fairness.** The score never uses name, location or other personal attributes. A test checks this.
- **No payments.** Milestone amounts track the work only.
