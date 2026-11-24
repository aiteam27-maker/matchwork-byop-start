# Gigwise – project guide

Read this first. It gives the context a new teammate or Claude chat needs, and the
rules every change must follow. The full change history is in `CHANGELOG.md`.
Read its latest entries before you start work.

## What this is

Gigwise is a front-end-only demo of a freelance marketplace. Clients post jobs or buy
ready-made services. Freelancers apply, deliver work in parts, or log hours. Payments
go through a simulated "Safe Pay". The whole app is one file, `gigwise.html` (HTML +
CSS + vanilla JS, no build step, no dependencies except Google Fonts). The other side
of every conversation is simulated in the browser. Data is saved in `localStorage`
under the key `gigwise-app-v3`.

- Repo: https://github.com/aiteam27-maker/matchwork-byop-start (branch `main`)
- Push with the GitHub CLI (`gh`), which is logged in as `aiteam27-maker`.

## Running it

- Quickest: open `gigwise.html` in a browser.
- With a local server (needed for page navigation in Claude's preview pane):
  `python3 -m http.server 8765`, then open http://localhost:8765/gigwise.html.
  `.claude/launch.json` sets this up as the `gigwise` preview.

## Code map of `gigwise.html`

Line numbers drift, so search for the section comments (`/* ===== name ===== */`).

| Section | What's there |
|---|---|
| `<style>` top | Design tokens on `:root` (colours, fonts, radius), with a dark theme via `prefers-color-scheme` and `[data-theme]` |
| `<style>` body | Components: top bar, buttons, inputs, chips, cards, wizard, messages, sheets, charts |
| `UI polish (v1.1)` | Shadows, hover states and animations, layered on top of the base styles |
| `helpers` | `$`, `esc` (HTML escaping, use it for all user text), money/time formatting, SVG icons `IC` |
| `data` | Seed freelancers `F0`, categories, keyword-to-skill rules, `seed()`, `load()`, `save()`, `resetDemo()` |
| `matching` | `match()` and `fitList()`: skill and budget fit scoring |
| `shell` | `toast()`, `sheet()` (modal), `nav()` (hash routing `#/page/id/tab`), `render()` and its route table `V` |
| `welcome` | Role picker shown when no role is chosen |
| `CLIENT` | Client home, job wizard (`cPost`), job page, applicants, hiring and offers |
| `contract (shared)` | Milestone contract view, deliver, approve and revise |
| `FREELANCER` | Find jobs, apply, my work, profile |
| `badges, services marketplace, talent` | Service packages and talent search |
| `hourly contracts` | Timesheets and timer |
| `money tracking` | Freelancer earnings and client budget charts |
| `messages` | Chat threads |
| `simulation of the other side` | Fake replies, offers and deliveries |
| `start` | Boot code |

Conventions: views are functions that return HTML strings. State changes then call
`render()`. Always pass user-entered text through `esc()`. Use the CSS tokens
(`var(--ac)` etc.), not raw colours, so dark mode keeps working.

## Rules for every change (required)

Every change pushed to this repo must be documented so teammates and future chats
can see what changed, why, and how to undo it.

1. **Before starting:** `git pull --ff-only origin main` and read the top of
   `CHANGELOG.md`.
2. **Make the change**, then check it in a browser (light and dark, phone and desktop
   widths) if it affects the UI.
3. **Update `CHANGELOG.md`** in the same commit. Add a new entry at the top using
   the existing format:
   - `## [vX.Y] – YYYY-MM-DD · Short title`
   - **By:** who made it (GitHub user, plus "with Claude Code" if Claude helped)
   - **Why:** the reason or request behind it
   - **Added / Changed / Removed / Fixed:** plain-language bullets a non-developer
     can follow
   - **Where:** files touched, and for `gigwise.html` the section or CSS block
   - Fill in the **Commit:** hash of the previous entry if it's missing.
4. **Bump the version:** next minor (`v1.2` → `v1.3`) for features and visible
   changes. Use a patch (`v1.3.1`) for small fixes and doc-only edits.
5. **Update `README.md`** if what users can do, or how to run it, has changed. Update
   this file if the code map or rules changed.
6. **Commit** with a clear subject (`Add …`, `Fix …`, `Polish …`) and a body listing
   the main changes. One logical change per commit.
7. **Tag and release:**
   ```bash
   git tag -a vX.Y -m "Short title"
   git push origin main vX.Y
   gh release create vX.Y --title "vX.Y – Short title" --notes "<the changelog entry>"
   ```
8. **Never** force-push `main` or rewrite pushed history. To undo something, use
   `git revert` and log the revert in the changelog as a new version.
9. Don't commit `.DS_Store`, `.claude/settings.local.json`, secrets or personal data.
