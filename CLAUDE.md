# Gigwise: guide for teammates and Claude Code

Claude Code reads this file at the start of every chat in this repository, on any
computer. Read the top of `CHANGELOG.md` too before starting work.

## What's here

- `gigwise/frontend/index.html`: the whole web app (HTML, CSS and vanilla JS, no build step).
- `gigwise/frontend/taxonomy.js`: the skill catalog, shared by the frontend and backend.
- `gigwise/backend/`: FastAPI + Supabase API. Setup and endpoints are in its README.
- `demo-gigwise.html`: the older demo. **Never change it.**
- **Two worlds:** `demo` (sample data, no login, for presentations) and `real` (signed-up users).
  Every endpoint must keep them apart and must only let signed-in users act as themselves.
  `gigwise/backend/tests/test_login.py` checks this; extend it when you add endpoints.
- Live site: https://gigwise-sg.onrender.com. Render redeploys automatically within
  about two minutes of every merge to `main`.

## Rules for every change

1. **Start from the latest code:** `git pull` on `main` before editing. Two people push
   to this repository, so skipping this can overwrite a teammate's work.
2. **Ask before risky changes.** If a change could break something, explain the risk
   to the user before making it.
3. **Keep matching identical in both places.** Scores and reasons live in the frontend
   JS and in `gigwise/backend/app/matching.py`. Change both, and run the tests:
   `cd gigwise/backend && .venv/bin/python -m unittest discover tests`.
4. **Check it works** in a browser (desktop and phone width, day and night mode)
   before pushing a frontend change.
5. **Never commit secrets** (`.env`, Supabase or Anthropic keys). Search the diff
   before committing.
6. **Record it in `CHANGELOG.md`** in the same pull request: add an entry at the top
   with the version, date, who, why, what changed, and which files.
7. **Push through a pull request:** new branch → commit → pull request → merge →
   delete the branch. Never push straight to `main` and never force-push.
8. **Tag the version** after merging: `git pull`, then
   `git tag -a v2.1 -m "Short title"` and `git push origin v2.1`.

To undo a version, use `git revert` on its merge commit, and log that as a new version.
