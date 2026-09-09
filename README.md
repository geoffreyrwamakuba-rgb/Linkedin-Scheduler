# LinkedIn Scheduler

Server-side scheduled posting to Geoffrey's LinkedIn profile via the official
Share on LinkedIn API. Runs on GitHub Actions — no laptop needed.

## How it works

1. Post text goes in `posts/<slug>.txt` (clean plain text, no markdown), image in `images/`.
2. An entry is added to `queue.json` with the publish time (Europe/London) and `status: "pending"`.
3. The Actions workflow (`.github/workflows/dispatch.yml`) publishes anything due and
   commits the status update back.

## What actually triggers it (measured 2026-09-07 — read this before debugging)

Two independent triggers, and **the GitHub one is not the one doing the work**:

| Trigger | Configured | Actually delivered |
|---|---|---|
| GitHub `schedule` cron (`7,22,37,52 7-19 * * *`) | 52 runs/day | ~5/day, erratic, some outside the 07-19 UTC window |
| **cron-job.org job `8359053`** → `workflow_dispatch` | every 30 min, on `:00`/`:30` | reliable; **91 of the last 100 runs** |

GitHub documents `schedule` as best-effort with no SLA, and it has been silently
skipped for hours at a time here (incidents 2026-07-27 and 2026-08-31). The
cron-job.org job is the de facto scheduler. **If posting stops, check cron-job.org
first, not the GitHub cron.** Nothing currently alerts if that external job stops.

Two triggers is safe by construction, not by luck: `concurrency: group:
linkedin-dispatch` with `cancel-in-progress: false` serialises runs, and an item only
fires while its status is `pending`. The residual risk is a run that publishes but
fails to push its status write-back — that is the 2026-07-27 double-post mode.

Schedule posts **on the hour**, and the standard slot is **09:00 Europe/London**
(Geoff's call, 2026-09-09 — moved up from 10:00; all pending items were shifted, posted
history left as it was). They'll land within ~30 minutes, so a 09:00 item goes out on the
09:00 or 09:30 cron-job.org check.
Only `pending` items ever fire; `posted`/`failed`/`missed` never re-fire, and an
empty queue run is a no-op. **A `failed` item is therefore stuck forever unless
someone resets it to `pending`** — do that inside the 48h grace window or it is lost. Anything more than 48h late is marked `missed`,
never posted stale. End-to-end verified 2026-07-19 (queued → Actions → live post
→ status committed back).

## Secrets (Settings → Secrets and variables → Actions)

- `LINKEDIN_ACCESS_TOKEN` — from `.env` in the Exec Assistant folder (re-auth every ~60 days
  with `tools/linkedin_auth.py`, then update this secret and `token_expires` in queue.json).
  **Never pipe the token into `gh secret set`.** Windows PowerShell 5.1 prepends a UTF-8 BOM
  when piping to a native command, and `requests` encodes headers as latin-1, so a BOM breaks
  every dispatch with `'latin-1' codec can't encode character '﻿' in position 7`
  (position 7 = first char of the token, right after `Bearer `). This happened on 2026-09-05
  and broke the 7 Sep post. Pass it as an argument instead:
  `gh secret set LINKEDIN_ACCESS_TOKEN --body $tok --repo geoffreyrwamakuba-rgb/Linkedin-Scheduler`.
  `dispatcher.py` now strips BOMs defensively, but write it clean anyway.
- `LINKEDIN_MEMBER_URN` — `urn:li:person:...`, same source

## Rules

- Repo is deliberately **public** (Geoff's call 2026-07-19): drafts are LinkedIn-bound
  anyway, the token lives only in GitHub Secrets, and public repos get unlimited free
  Actions minutes. Don't put anything here that isn't destined for LinkedIn.
- Never queue a post that's also scheduled in LinkedIn's native scheduler.
- Managed by the Exec Assistant workflow: `workflows/linkedin_post.md`.
