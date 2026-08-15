# JobSearchBot

A bot that scans **all active listings** on JobSearch.az and notifies the user on
Telegram about jobs matching their profile. Vision and roadmap: [VISION.md](VISION.md) ·
Technical architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

## How it works

- **GitHub Actions** runs it 5 times a day (Baku 09/12/15/18/21) — no local machine
  is required.
- The scraper paginates the site's JSON API and pulls all ~2700 listings
  (with retry/backoff).
- There are two flows:
  - **Legacy (single user):** rule-based classification (`jobbot/classifier.py`) for
    the `TELEGRAM_CHAT_ID` in `.env`/Secrets.
  - **Phase 1 (multi-user, Supabase):** users send `/start` to the bot and upload a CV
    (PDF); each user receives matches based on their own profile. The listing corpus is
    shared across all users and is analyzed once, then cached.

## Setup (development)

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env   # fill in the values
.\.venv\Scripts\python.exe -m jobbot --dry-run
```

## Phase 1 setup (multi-user)

1. Create a Supabase project → run the contents of `supabase/migrations/001_init.sql`
   in the SQL Editor.
2. Add to `.env` (local) and GitHub Actions Secrets:
   - `SUPABASE_URL`, `SUPABASE_SECRET_KEY`
   - `GROQ_API_KEY` (optional — without it, the CV profile is extracted heuristically)
3. When the bot runs, it processes incoming `/start` + CV uploads on every cron cycle.

Privacy rule: **CVs are personal data** — they are only sent to providers that do not
train on the data (Groq/Cohere). Details: [ARCHITECTURE.md](ARCHITECTURE.md).

## GitHub Secrets (Actions)

| Secret | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | BotFather token |
| `TELEGRAM_CHAT_ID` | ✅ | Legacy single-user chat id |
| `SUPABASE_URL` | For Phase 1 | Project URL |
| `SUPABASE_SECRET_KEY` | For Phase 1 | service_role secret key |
| `GROQ_API_KEY` | optional | CV profile extraction (LLM) |
| `OPENAI_API_KEY` | optional | Legacy AI classification |
