# Changelog

Every change to Gigwise is recorded here, newest first. Each version has a git tag
(`v2.0`, `v2.1`, ...), so you can always see or restore the site as it was at that
version. How to add an entry is in `CLAUDE.md`.

Versions: a **new feature or redesign** bumps the middle number (`v2.0` → `v2.1`).
A **small fix** bumps the last number (`v2.1` → `v2.1.1`).

---

## v2.2 · 2026-11-27 · Real accounts: email, Google, and a separate investor demo

**By:** aiteam27-maker with Claude Code
**Why:** People need their own accounts, while the team keeps a full demo to show investors.

**Added**
- Sign up and log in with email and password (confirmed by an emailed link) or Google, using
  Supabase Auth. Passwords go straight to Supabase; Gigwise never sees them. Forgot-password included.
- Two separate worlds in the database: **demo** (the sample marketplace, open to anyone through
  **Try the demo**) and **real** (signed-up users). They never see each other.
- Signed-in users act only as their own client and freelancer profiles, and see only their own
  proposals, offers, contracts, messages and notifications. The server checks this on every request.
- First login asks "I'm hiring" or "I'm a freelancer" and sets up that profile.
- A quiet "Demo" bar while exploring the demo, with "Create an account" and "Exit demo".
- `gigwise/backend/sql/002_login.sql` (adds the demo/real split and links profiles to logins),
  `gigwise/backend/app/auth.py`, `GET /state`, `GET /auth/config`, `POST /clients`, `PUT /clients/me`,
  and 7 tests that try to read or change other people's data (`tests/test_login.py`).

**Changed**
- Simulated replies, proposals and the one-click Hire auto-accept now run only in the demo.
- Resetting the demo deletes only demo data, never real accounts.
- `render.yaml` and `.env.example`: new `SUPABASE_ANON_KEY` setting (the public key). Without it,
  the app offers only the demo, as before.

**Setup needed:** run `002_login.sql`, set the Supabase login settings, and add `SUPABASE_ANON_KEY`
on Render. See `gigwise/backend/README.md` → "Login and the investor demo".

---

## v2.1.1 · 2026-11-27 · Home page background video

**By:** a teammate (videos), pushed by aiteam27-maker with Claude Code
**Why:** v2.1 shipped without its video files, so the home page showed a plain dark
background instead of the video.

**Added**
- `gigwise/frontend/hero.mp4` (3.8 MB, wide screens) and
  `gigwise/frontend/hero-portrait.mp4` (0.7 MB, phones), taken from the teammate's
  published Claude artifact. No code changes.

---

## v2.1 · 2026-11-27 · New home page, simpler posting, one-click hire

**By:** a teammate, pushed by aiteam27-maker with Claude Code
**Why:** Make the first impression stronger and the client's path from idea to hire
shorter for demos.

**Changed** (`gigwise/frontend/index.html`)
- Home page: a full-screen opening ("Hire people who get it right") with a search bar
  that types example projects, shows suggestions on focus and filters projects,
  categories and skills as you type. Then a scrolling category strip, a three-step
  "how it works" and a closing call to post. The score breakdown, fairness note,
  featured freelancers and Hire/Work switch were removed from the home page.
- Posting a project: two questions (what you need, your budget) with the detected
  skills and budget hints. Skills, timeline and screening questions moved under
  "More options".
- Proposals: clearer cards tagged Best match / Lowest price / Fastest, and an
  "Our pick" banner.
- One-click Hire: sends an offer with suggested milestones. **Demo behaviour:** the
  freelancer accepts automatically about 4 seconds later, which creates a contract in
  the shared live data. The normal "Send offer" flow still waits for the freelancer.
- Pages fade in, sections reveal on scroll, and menu links are slightly bigger.

**Known gaps**
- The background video files (`hero.mp4`, `hero-portrait.mp4`) aren't in the
  repository yet, so the home page shows a plain dark background instead.
- Unused code remains for an activity wall and a YouTube background; neither is shown.

---

## v2.0 · 2026-11-27 · Editorial design, and a changelog

**By:** the team (design by a teammate, pushed by aiteam27-maker with Claude Code)
**Why:** The team preferred a more distinctive, magazine-like look over the plain
Upwork-style design. With two people now pushing from different computers, the team
also needed a shared record of changes and shared rules for every Claude chat.

**Changed**
- `gigwise/frontend/index.html`: the editorial design (PR #17). Warm paper colours
  with one brick-red accent in day and night mode, Newsreader and Instrument Sans
  fonts, square corners and thin rules instead of boxed cards, a typeset "Gigwise"
  wordmark instead of the logo icon, a magazine-style landing page, and freelancers
  listed as rows. Design only: matching, explanations, data and backend unchanged.

**Added**
- `CHANGELOG.md` (this file) and `CLAUDE.md` (project guide and rules that every
  Claude Code chat in this repository reads automatically).

---

## Before v2.0 · 2026-11-25 · Building Gigwise

Built before this changelog existed. Each item is a merged pull request on GitHub.

- **#1** Gigwise frontend (then called MatchWork): match scores with reasons, and
  Upwork-style features for clients and freelancers.
- **#2** Renamed MatchWork to Gigwise. The older single-file app became `demo-gigwise.html`.
- **#3, #4** Backend: FastAPI + Supabase, with server-side scoring, proposals, offers,
  contracts, milestones, reviews, saved items, messages and profiles.
- **#5** Frontend connected to the backend (live mode, with an offline fallback).
- **#6** Night/day mode.
- **#7, #8, #11, #12** Live website on Render, moved to the Singapore region.
- **#9, #10** Faster loading and actions (reused connections, parallel database calls).
- **#13** Skill catalog with a category picker (`taxonomy.js`), and optional
  Claude-written explanations (off until an Anthropic key with credits is added).
- **#14** Match explanations rewritten to read naturally.
- **#15** Minimal, flat redesign in the spirit of Upwork and Fiverr (replaced in v2.0).

Tags `v1.0`–`v1.2` belong to the earlier demo app and don't describe this version.
