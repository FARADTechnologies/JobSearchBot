# ROADMAP.md — JobSearchBot / Startup Roadmap

> Living document. Vision: [VISION.md](VISION.md) · Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
> Last updated: 2026-08-15

## 🎯 CURRENT FOCUS: the founder's personal job-finding system (startup deferred)

The startup / multi-user / CV-pool side is **intentionally deferred**. The only goal right
now is a personal system that finds jobs for the founder. There are two live flows:

- **🔔 Azerbaijan jobs** (jobsearch.az → robotics/STEAM matching) → DM, 5x a day
- **🌍 Global remote jobs** (Adzuna + 4 free boards → LLM judge → score + "why it fits")
  → a dedicated remote-jobs Telegram group, hourly

### To do (priority order)

0. **VERIFY (this first):** trigger the RemoteJobs workflow, check whether the group is
   receiving LLM-selected scored jobs, whether the quality is good, whether US-only was
   dropped — look at the real output. Don't build on top of it if it's bad.
1. **TUNE:** adjust the profile spec, score threshold, volume, and salary floor based on the output.
2. **👍/👎 feedback** (a focused task): send high-score jobs individually with buttons →
   handle the tap → `data/remote_feedback.json` → feed the disliked patterns into the LLM prompt (moat).
3. **Grow the pool:** Jooble (60+ countries, free key on request) + Careerjet + The Muse.
4. **Auto-apply (LLM-targeted):** email-based first, then web form/ATS filling.
5. **Application tracker** (together with auto-apply).

### Done (in these sessions)
Adzuna pool · Gemini LLM judge (batch, retry, score + why-fits) · separate group routing ·
hourly remote workflow · geo-eligibility (LLM) · dedup · salary filter · digest mode ·
security scan (repo public, clean).

---

## Status snapshot (startup — DEFERRED)

| Layer | Status |
|---|---|
| Scraper (jobsearch.az, full pagination + retry) | ✅ Live, stable for 3+ weeks |
| GitHub Actions (5x a day, free) | ✅ Live |
| Legacy single-user notification (the founder's profile) | ✅ Live |
| Phase 1 multi-user foundation (Supabase schema, onboarding, CV, per-user matching) | 🟡 **Code ready**, awaiting rollout |
| — Running the Supabase schema SQL | ⛔ User will do it (SQL Editor) |
| — GitHub Secrets (SUPABASE_URL/KEY) | ⛔ User will add them |
| — Groq key (CV profile extraction) | ⛔ Account issue → heuristic for now |
| AI-native matching engine (embedding→rerank→LLM-judge) | ⬜ Designed, not coded |
| Phase 2 auto-apply | ⬜ |
| Phase 3 CV pool (employer revenue) | ⬜ |

## Phases (order)

**Phase 1 — Multi-user smart notifications** (currently here)
1. Rollout: schema + secrets + (optional) Groq
2. AI-native matching engine: each listing/CV goes through the LLM once for English
   structured extraction + BGE-M3 embedding → pgvector → hard filter → hybrid retrieval → rerank → LLM judge
3. **New: remote/part-time/internship search** (separate section below)
4. Multi-source (separate section below)
5. Measurement: golden set + nDCG + online CTR/retention

**Phase 2 — Automatic applications** (trust ladder: notify → one-tap → autonomous)

**Phase 3 — CV pool** (opt-in, employers search candidates with AI, **the real revenue**)

---

## NEW FEATURE: remote / part-time / paid-internship search

### Problem
Sites' structured `job_type` filter often **misses** these, because:
1. The employer fills the structured field incorrectly/incompletely
2. The "remote / part-time" information is often only in the **listing text**
3. In Azerbaijan, "internship (təcrübə)" listings are sometimes **paid** and can be
   remote/part-time — but you have to read the description to know

### Solution — this is exactly the job of the AI-native extraction engine
No separate system is needed. The LLM already reads each listing once (ARCHITECTURE.md);
we add these fields to the extraction schema:
- `work_mode`: remote | hybrid | onsite | unknown
- `employment_type`: full_time | part_time | contract | internship | unknown
- `is_paid`: true | false | unknown   (critical for internship listings)
- `remote_eligibility`: "AZ-only" | "global" | unknown

Then the user selects these as **hard filters** (SQL WHERE). The "NLP" the user wants is
exactly this extraction stage.

### Two levels
- **Fast (no LLM, doable today):** a multilingual keyword net over title+description:
  `remote, uzaqdan, distant, work from home, evdən, onlayn, part-time, part time,
  yarım ştat, natamam iş günü, natamam iş vaxtı, saatlıq, freelance, təcrübə, staj,
  internship, ödənişli`. Imperfect but works immediately for the founder's personal need.
- **Correct (LLM extraction):** the structured fields above. Consistent across sources,
  and it also catches mislabeled listings.

### The founder's personal profile (the first test user of this feature)
- Looking for: **part-time OR remote** (both is ideal), field does not matter
- If remote: jobs doable with AI assistance also count (i.e., out-of-field is accepted too)
- Paid internships included

---

## MULTI-SOURCE: Azerbaijan job sites (most to least popular)

| # | Site | Type | Note |
|---|---|---|---|
| 1 | **HelloJob.az** | Own HR clients | Claims "Azerbaijan #1", high volume |
| 2 | **JobSearch.az** | Own clients | ✅ Already integrated (API solved) |
| 3 | **BirJob.com** | **Aggregator — OFFICIAL API!** | ⭐⭐ Deduplicates 91 sources into one API, ~12,257 listings. See below. |
| 4 | **Boss.az** | Aggregator | Large |
| 5 | **Jooble.az** | Aggregator | The AZ arm of the global Jooble |
| 6 | **AZJOB.az** | Listing site | |
| 7 | **İşəQəbul.az** | Listing site | "from real companies" |
| 8 | **JobU.az / isbu.az** | Listing site | Smaller |

**Remote-specific (global, heavy ToS):** LinkedIn, We Work Remotely, Remote.co, Arc.dev,
Himalayas, DailyRemote, Workana. These are valuable for the user's personal remote flow
(remote work he can do with AI assistance), but scraping them is risky — a later stage.

### ⭐ BirJob API — a game changer (discovered 2026-08)
`https://www.birjob.com/api/v1` — an official developer API (Bearer token, auto-issued key
at `/developers/keys`). Instead of us writing 8 adapters, it provides **91 sources,
deduplicated, through a single integration**. Crucially, the response fields are exactly what
we want — `employment_type` (Full/Part-time/Contract/Internship/Freelance), `work_type`
(Onsite/Hybrid/Remote) + `is_remote`, `salary_from/to`, `description_text`,
`requirements_text`, `apply_link`, `source`, `deadline_at`, `contact_email/phone`.
Incremental sync via `from_id`. Scraped 3x a day via a GitHub Actions cron.

**This nearly solves the structured side of the remote/part-time feature** (is_remote /
employment_type fields). The LLM is only needed for listings where these are missing/wrong.

**Risks:**
- **Paid/quota-based** (monthly "unit" quota, plan-dependent; a free tier is not clearly
  stated — check at signup). /v1/jobs = 1 unit (search = 5). A full sync is ~123 requests;
  cheap with `from_id`.
- **Single point of dependency** + BirJob is itself an AZ job platform (iOS app) = a
  potential competitor. If it cuts us off, multi-source collapses.
- **Mitigation:** use BirJob as coverage expansion + validation, keep our own jobsearch.az
  scraper as primary/backup, and long-term build our own adapters for the biggest 2-3 sites.

### Strategy (current)
- **Phase A:** add the BirJob API as a source adapter (if the free quota is enough) →
  instantly 91 sources + structured remote/part-time fields.
- **Phase B:** our own direct adapters for the biggest sites (HelloJob, Boss) (reducing dependency).
- **Dedup is mandatory** (BirJob deduplicates internally, but when we combine it with
  jobsearch.az it's needed again): fingerprint/embedding.
- **ToS/legal:** the BirJob API is official (green); direct scraping is slow + robots.txt.

---

## NEW (MANDATORY) FEATURE: fraud / fake-listing filter

**Why mandatory:** Remote job fraud is exploding (~$521M in losses in 2026, a 1000% spike
between May and July). Remote/part-time in particular = the highest fraud density. It is
**more critical** for us than for a normal user, because Phase 2 has **auto-apply** —
automatically applying to a fake listing = sending the user's CV/personal data to a scammer.

**Red flags (to add to the LLM judge / rules layer):**
- Requests upfront payment / a "registration fee"
- Unrealistically high salary, an overly vague job description, urgency pressure
- Redirects only to WhatsApp/Telegram, personal gmail instead of a corporate email
- Requests a passport/bank/ID early on
- The company name can't be verified / no careers page

**Implementation:** add a `fraud_risk`: low|medium|high field to the extraction stage;
high-risk ones are not notified or are notified with a "⚠️ suspicious" tag; auto-apply
**never** applies to high-risk ones.

**Is BirJob itself safe?** Yes — BirJob is a pass-through aggregator: it lists the posting
from its source, shows the source, and the application happens **on the original site**; it
does not collect CVs. So BirJob is not the party stealing data. The risk is in the fake
listings inside the underlying 91 sources — the filter above handles that.

---

## Idea pool (backlog, unordered)

- **Automatic email** (planned-email-feature): Telegram + email for suitable jobs
- **A "why it fits" explanation** on every match (builds trust → reduces churn)
- **User feedback** (👍/👎 buttons) → `matches` feedback → data flywheel → moat
- **CV quality/gap warning** (parsing ~75-85%, a "check your profile" step for the user)
- **Multiple profiles**: one user has a separate filter for their field and for "remote AI work"
- **Salary range extraction** (hidden in most listings; estimate from text)
- **Notification digest**: an optional daily/weekly single-digest mode (notification fatigue)
- **Language normalization**: translate the extraction to English (bypasses the Azerbaijani
  low-resource risk)
- **Employer-side MVP** (Phase 3): a company says "I'm looking for someone like this" → the AI ranks candidates
- **Web/mobile interface** (after Telegram)
- **Key rotation**: the Supabase secret + Telegram token were pasted into chat → rotate them

## Known technical debt / risks
- GitHub Actions occasionally "runner not acquired" (infrastructure, self-heals — not code)
- Single-source dependency (multi-source will reduce this)
- Groq account blocked → CV profile is heuristic for now (quality improves once on the LLM)
- CV = personal data → privacy/data-protection (legal advice before Phase 3)
