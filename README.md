# Gigwise

A freelance marketplace where clients post projects and freelancers apply. Every freelancer gets a 0–100 match score for each project, with a plain-English reason.

This repo holds two apps:

| App | Where | What it is |
|---|---|---|
| **Gigwise** | `gigwise/` | The current app, built from the product requirements. Frontend in `gigwise/frontend/`, backend (not built yet) in `gigwise/backend/`. |
| **Demo Gigwise** | `demo-gigwise.html` | The earlier single-file demo, kept for reference. |

Both run in the browser with no install or server. Open the HTML file in any browser.

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

- Both are front-end demos. The other side is simulated and replies within seconds.
- No real accounts or payments. Data is saved in your browser only. Use **Reset demo data** in each app to start over.
