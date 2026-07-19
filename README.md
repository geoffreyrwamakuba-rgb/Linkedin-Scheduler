# LinkedIn Scheduler

Server-side scheduled posting to Geoffrey's LinkedIn profile via the official
Share on LinkedIn API. Runs on GitHub Actions every 30 minutes — no laptop needed.

## How it works

1. Post text goes in `posts/<slug>.txt` (clean plain text, no markdown), image in `images/`.
2. An entry is added to `queue.json` with the publish time (Europe/London) and `status: "pending"`.
3. The Actions workflow (`.github/workflows/dispatch.yml`) runs hourly on the hour
   (daytime, London), publishes anything due, and commits the status update back.

Schedule posts **on the hour** (e.g. 11:00) — they'll land within ~10 minutes.
Only `pending` items ever fire; `posted`/`failed`/`missed` never re-fire, and an
empty queue run is a no-op. Anything more than 48h late is marked `missed`,
never posted stale. End-to-end verified 2026-07-19 (queued → Actions → live post
→ status committed back).

## Secrets (Settings → Secrets and variables → Actions)

- `LINKEDIN_ACCESS_TOKEN` — from `.env` in the Exec Assistant folder (re-auth every ~60 days
  with `tools/linkedin_auth.py`, then update this secret and `token_expires` in queue.json)
- `LINKEDIN_MEMBER_URN` — `urn:li:person:...`, same source

## Rules

- Repo is deliberately **public** (Geoff's call 2026-07-19): drafts are LinkedIn-bound
  anyway, the token lives only in GitHub Secrets, and public repos get unlimited free
  Actions minutes. Don't put anything here that isn't destined for LinkedIn.
- Never queue a post that's also scheduled in LinkedIn's native scheduler.
- Managed by the Exec Assistant workflow: `workflows/linkedin_post.md`.
