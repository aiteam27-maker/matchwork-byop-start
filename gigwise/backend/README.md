# Gigwise backend

A Python API (FastAPI) that stores Gigwise data in Supabase (PostgreSQL) and runs the match score on the server.

```
Browser (gigwise/frontend)  ->  this API (FastAPI)  ->  Supabase (database)
```

The frontend (`gigwise/frontend/index.html`) uses this API when it's running (**live mode**: data saved in Supabase). If the API isn't running, the frontend falls back to its built-in offline demo, with data saved in the browser only.

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

## Run Gigwise (app + API)

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Then open:
- **http://localhost:8000**: the Gigwise app in live mode. The footer shows **● Live data**, and every action is saved in Supabase.
- **http://localhost:8000/docs**: see and try every API endpoint.
- **http://localhost:8000/health**: whether the database is connected.

Press **Ctrl+C** to stop. **Reset demo data** in the app's footer reloads the demo data in the database (turn it off with `DEMO_RESET_ENABLED=false` in `.env`).

Opening `index.html` by double-clicking it still works, in offline mode. The browser blocks a page opened from a file from calling the API.

## Run the tests

```bash
.venv/bin/python -m unittest discover tests
```

## Endpoints

Full details and a "Try it out" button for each one: http://localhost:8000/docs

| Area | Endpoints |
|---|---|
| System | `GET /health` (also says whether AI is on), `GET /me` (the demo client you act as), `GET /taxonomy` (the skill catalog) |
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
| AI (optional) | `POST /ai/explain` (Claude-written match reasons for up to 8 freelancers), `POST /ai/draft-proposal` (cover letter draft) |

**Coming next:** real login (Supabase Auth); live chat (Supabase Realtime).

## Skill catalog

Skills come from one catalog, `gigwise/frontend/taxonomy.js`: 12 categories, 35 specialties and about 240 skills, plus accepted alternative spellings ("ReactJS" is saved as "React"). The frontend and backend both read that file. The API only accepts catalog skills (up to 10 per project, 15 per profile), so clients and freelancers always use the same names, which keeps skill matching accurate. To add a skill, edit that file and deploy.

## Claude-written explanations (optional)

With `ANTHROPIC_API_KEY` set (in `.env` locally, and in Render's Environment for the live site), the app asks Claude (`claude-opus-5-5`) to write the match reasons and proposal drafts:

- Claude only sees the facts behind the score: skills matched and missing, rate vs budget, experience, rating, Job Success, portfolio and bio. **Never names or locations.** It is told to cite only those facts and to be honest about gaps.
- Without a key, or if a call fails or is declined, the app keeps its template text. Nothing depends on AI.
- Results are cached, and calls are capped at 30 a minute per server (`AI_MAX_CALLS_PER_MINUTE`), because without login anyone with the link can trigger them.
- If Claude declines a request, a server-side fallback model is used automatically.

## Notes

- **Live mode details.** The app loads everything with one call (`GET /demo/state`), sends each action to its endpoint, then reloads, so the screen always shows what's saved. It also refreshes every 20 seconds to pick up changes from other browsers. Match scores are calculated in the browser with the same formula as `app/matching.py`; the tests check both give identical results.
- **No login yet.** As a client you act as the demo client (Pulse Fit). Freelancer actions take a `freelancer_id`. Anyone who can reach the API can act as anyone, so run it locally only for now.
- **Security.** Every table has Row Level Security on with no rules, so the public anon key can't read anything. Only this backend, using the secret key, can.
- **Fairness.** The score never uses name, location or other personal attributes. A test checks this.
- **No payments.** Milestone amounts track the work only.
