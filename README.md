# Gigwise

A freelance marketplace where clients post projects and freelancers apply. Every freelancer gets a 0–100 match score for each project, with a plain-English reason.

This repo holds two apps:

| App | Where | What it is |
|---|---|---|
| **Gigwise** | `gigwise/` | The current app, built from the product requirements. Frontend in `gigwise/frontend/`, backend (not built yet) in `gigwise/backend/`. |
| **Demo Gigwise** | `demo-gigwise.html` | The earlier single-file demo, kept for reference. |

Open either HTML file in any browser and it works on its own with demo data. To run Gigwise with its real database (Supabase), start the backend and open http://localhost:8000. See `gigwise/backend/README.md`.

## Gigwise (`gigwise/frontend/index.html`)

**Match score.** Each freelancer is scored per project: skills 45%, profile similarity 20%, budget fit 20%, experience 8%, ratings 7%. Results show matched and missing skills and a reason built only from profile facts. Name, location and other personal attributes are never scored.

**Clients**
- Post a project (fixed price or hourly). Leave skills blank and they're detected from the description
- See ranked matches, invite freelancers and chat
- Compare proposals side by side, send offers, and track contracts by milestone
- Filter and save freelancers, and leave reviews when a contract ends

**Freelancers**
- See open projects ranked by fit, with a "why you fit" note
- Apply with a cover letter, screening answers and links (Connects limit how many proposals you send)
- Accept offers, submit milestone work, and leave reviews for clients

Not included (out of scope): payments and escrow, disputes, video calls, mobile apps, time tracking.

## Demo Gigwise (`demo-gigwise.html`)

The earlier demo, with an AI job-post wizard, service packages, a simulated Safe Pay escrow, time tracking and an earnings page.

## Notes

- The other side of each conversation is simulated and replies within seconds, so you can demo alone.
- No real accounts or payments yet. Gigwise saves to Supabase in live mode, or to your browser in offline mode. Demo Gigwise always saves to your browser. Use **Reset demo data** in each app to start over.

## Live website (Render)

**Live site: https://gigwise-sg.onrender.com** (Render, Singapore region, next to the Supabase database in Seoul).

Gigwise is set up to deploy to [Render](https://render.com) as one website that serves both the app and the API. The settings are in `render.yaml`.

**One-time setup** (the repo owner):
1. Sign in to Render with GitHub and allow access to this repository.
2. Click **New → Blueprint**, pick this repository, and Render reads `render.yaml`.
3. When asked for `SUPABASE_SERVICE_ROLE_KEY`, paste the Supabase **secret** key. It stays private in Render and never goes into GitHub.
4. Click **Apply**. After a few minutes the site is live. Share the link with the team.

**After that:**
- Every change merged into `main` goes live automatically within about 2–5 minutes. Branches and open pull requests don't affect the live site.
- Data people create on the site (projects, proposals, messages) is saved in Supabase straight away and isn't affected by updates.
- If an update breaks something, open the service in Render → **Events** and redeploy the previous version.
- Changes to the database structure (`gigwise/backend/sql/`) must be run in Supabase's SQL Editor by hand. Deploying doesn't do it.
- **Reset demo data** is turned off on the live site, so visitors can't wipe everyone's data. To reset, run `python -m seed.seed` from `gigwise/backend` on your own computer.
- The free plan pauses the site after about 15 minutes without visitors, and the next visit takes 30–60 seconds to wake it.
- There's no login yet, so anyone with the link can act as any user. Share it with your team only.
