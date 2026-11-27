# Changelog

Every change to Gigwise is recorded here, newest first. Each version has a git tag
(`v2.0`, `v2.1`, ...), so you can always see or restore the site as it was at that
version. How to add an entry is in `CLAUDE.md`.

Versions: a **new feature or redesign** bumps the middle number (`v2.0` → `v2.1`).
A **small fix** bumps the last number (`v2.1` → `v2.1.1`).

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
