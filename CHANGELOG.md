# Changelog

Every change to this repo is recorded here, newest first. Each version is a git tag
and a GitHub release, so any version can be viewed or restored (see
[How to roll back](#how-to-roll-back)).

Format for each entry: version and date, who made it, why, what changed, and
which files it touched. See `CLAUDE.md` for the full rules.

---

## [v1.2] – 2026-11-24 · Change documentation and team workflow

**By:** aiteam27-maker, with Claude Code
**Why:** The team asked that every change be documented, so everyone (and new
Claude chats) can see what changed, why, and how to undo it.

**Added**
- `CHANGELOG.md` (this file), with the full history of the repo so far.
- `CLAUDE.md`: project overview, code map of `gigwise.html`, and the rules for
  making, documenting, committing, tagging and releasing changes. Claude Code
  reads it automatically at the start of every chat in this folder.
- `.gitignore`: keeps macOS `.DS_Store` files and personal Claude settings out of git.
- `.claude/launch.json`: starts a local web server (`python3 -m http.server 8765`)
  so the demo can be previewed at http://localhost:8765/gigwise.html.
- GitHub releases for v1.0, v1.1 and v1.2, with release notes taken from this file.

**Changed**
- `README.md`: added "How to run locally" and "Change history" sections.

**App changes:** none. `gigwise.html` is unchanged from v1.1.

---

## [v1.1] – 2026-11-24 · UI polish

**By:** aiteam27-maker, with Claude Code
**Commit:** `9b3c9b6`
**Why:** Make the demo look more finished and feel more responsive.

**Changed (`gigwise.html`, styling only; no text or behaviour changed)**
- Soft shadows on cards, job and service tiles, and panels, tuned separately for
  dark mode.
- Job and service cards lift slightly on hover. Buttons glow on hover and press
  down on click. Inputs, option tiles and filter pills change border on hover.
- Welcome page: role cards ("I want to hire" / "I want to work") get icon badges
  and a green-to-blue accent stripe on hover. The three features below them are
  shown as cards.
- Soft green glow on the page background and the dark hero banner.
- The current page in the top navigation is highlighted in green.
- "Next step" banners get a coloured left edge.
- Pop-up sheets, menus and toasts animate in. Scrollbars are thinner.
- All animations turn off when the device is set to reduce motion.

**Where:** a single block of CSS at the end of the `<style>` tag, under the
comment `/* =============== UI polish (v1.1) =============== */`. Deleting that
block restores the v1.0 look exactly.

---

## [v1.0] – 2026-11-24 · Gigwise marketplace demo

**By:** aiteam27-maker
**Commit:** `f108445`

**Added**
- `gigwise.html`: single-file freelance marketplace demo. Includes job posting
  (fixed price and hourly), ready-made services, talent search, offers, Safe Pay
  milestones, time tracking, a freelancer earnings page and client budget tracking.
- `README.md`: what the demo does and how to use it.

---

## Initial commit – 2026-11-24

**By:** aiteam27-maker
**Commit:** `0fd2a7a`
- Created the repo with a placeholder `README.md`.

---

## How to roll back

Every version has a tag (`v1.0`, `v1.1`, ...). Run these from the repo folder.

- **See what a version changed:** `git show v1.1 --stat`
- **Compare two versions:** `git diff v1.0 v1.1 -- gigwise.html`
- **Undo one version, keeping history** (the safe option for a shared repo):
  `git revert <commit>` then `git push origin main`. Then add a changelog entry
  for the revert.
- **Get one file back from an old version:**
  `git checkout v1.0 -- gigwise.html`, then commit it as a new change.
- **Download any version:** GitHub → Releases → pick a version → Source code.

Never use `git push --force` on `main`, since it rewrites history for everyone.
