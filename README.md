# Gigwise

A freelance marketplace demo where clients hire and freelancers get hired, matched by AI.
Everything runs in a single file, `gigwise.html`. Open it in any browser; no install or server needed.

## What you can do

**Clients**
- Post a job in 4 short steps (AI drafts the post and suggests a fair budget), fixed price or hourly
- Buy ready-made services with Basic, Standard and Premium packages
- Browse freelancers, invite them, compare applicants, book a call and hire
- Pay safely through Safe Pay: approve each part of the work, or approve hourly timesheets weekly
- Track a monthly budget and see where the money goes

**Freelancers**
- Find jobs ranked by fit, apply in a minute with an AI-drafted message
- Accept, counter or decline offers
- Deliver work in parts, or track time with the built-in timer on hourly contracts
- Sell your own service packages
- Track monthly revenue, goals and transactions on the Earnings page, and withdraw earnings

## Notes

- This is a front-end demo. The other side (clients or freelancers) is simulated and replies within seconds.
- No real accounts or payments. Data is saved in your browser only. Use **Reset demo data** in the account menu to start over.

## How to run locally

Open `gigwise.html` in a browser. Or serve the folder and open http://localhost:8765/gigwise.html:

```bash
python3 -m http.server 8765
```

## Change history

Every change is logged in [CHANGELOG.md](CHANGELOG.md), with who made it, why, and what changed. Each version is a git tag and a [GitHub release](https://github.com/aiteam27-maker/matchwork-byop-start/releases), so any version can be compared or restored.

Before you make a change, read [CLAUDE.md](CLAUDE.md). It has the code map and the rules for documenting, committing, tagging and releasing.
