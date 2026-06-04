# Tee Time Checker

A personal tool that polls the ForeUp booking API for available tee times and sends email alerts when new slots appear.

## Architecture & Data Flow

```
cron-job.org (every 5 min)
    │  HTTP POST (workflow_dispatch)
    ▼
GitHub Actions (check_tee_times.yml)
    │  restores cache: last_sent_*.txt, foreup_jwt.json
    │  sets env: EMAIL_SENDER, EMAIL_PASSWORD, FOREUP_EMAIL, FOREUP_PASSWORD, CONFIG
    ▼
fore_up_checker.py
    │  reads CONFIG (JSON from GH Actions variable)
    │  for each slot → GET foreupsoftware.com/index.php/api/booking/times
    │  if requiresAuth → POST /api/booking/users/login → caches JWT in foreup_jwt.json
    │  compares results against last_sent_{courseId}-{slotId}-{date}.txt
    │  if new times found → sends email via Gmail SMTP
    │  saves updated seen-keys back to file
    ▼
GitHub Actions cache
    │  saves: last_sent_*.txt, foreup_jwt.json
    │  key: last-sent-{run_id}, restore prefix: last-sent-
```

## Key Files

| File | Purpose |
|---|---|
| `fore_up_checker.py` | Main script — polls API, deduplicates, sends alerts |
| `docs/index.html` | Web UI for managing config (served via GitHub Pages) |
| `docs/enums.json` | Course definitions (IDs, booking classes, schedule IDs) |
| `.github/workflows/check_tee_times.yml` | GH Actions workflow triggered by cron-job.org |

## Configuration

Config lives in a **GitHub Actions repository variable** named `CONFIG` (JSON string). The web UI at `docs/index.html` reads/writes this via the GitHub API using a personal access token stored in localStorage.

Example CONFIG shape:
```json
{
  "emailReceivers": "a@example.com,b@example.com",
  "slots": [
    {
      "id": "friday-morning-2",
      "day": "friday",
      "time": "morning",
      "players": 2,
      "courseId": "XXXXX",
      "courseName": "Course A",
      "bookingClass": "XXXXX",
      "scheduleId": "XXXX",
      "scheduleIds": "XXXX,XXXX",
      "requiresAuth": false,
      "recipients": []
    }
  ]
}
```

`recipients` on a slot overrides the top-level `emailReceivers`. Empty array means all recipients.

## Secrets (GitHub Actions)

| Secret | Purpose |
|---|---|
| `EMAIL_SENDER` | Gmail address used to send alerts |
| `EMAIL_PASSWORD` | Gmail app password |
| `FOREUP_EMAIL` | ForeUp account email (for courses requiring auth) |
| `FOREUP_PASSWORD` | ForeUp account password |

## Deduplication

Seen tee times are stored in `last_sent_{courseId}-{slotId}-{date}.txt` (JSON array of keys). The key format is `{time}|{course_name}|{holes}`. Files are persisted across runs via the GH Actions cache with a restore prefix so every run picks up the latest saved state regardless of run ID.

## Adding a New Course

1. Add an entry to `docs/enums.json` under `COURSES` with the course's `courseId`, `bookingClass`, `scheduleId`, `scheduleIds`, and `requiresAuth`.
2. The course key (e.g. `"smith"`) is only used by the UI for display; the Python script uses the resolved fields from CONFIG.
3. If `requiresAuth: true`, the script will call the ForeUp login endpoint and attach a Bearer JWT. The JWT is cached in `foreup_jwt.json` and reused until it expires (with a 5-minute buffer).

## Local Development

```bash
pip install -r requirements.txt
cp .env.example .env  # fill in credentials
# Set CONFIG as an env var or add to .env as a JSON string
python fore_up_checker.py
```

The UI (`docs/index.html`) can be opened directly in a browser — it talks to `api.github.com` and `api.cron-job.org` from the browser using credentials stored in localStorage.
