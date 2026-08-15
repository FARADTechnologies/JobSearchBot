# JobSearchBot — Vision and Startup Idea

> This document holds the project's **purpose, full feature set, and phases**, so nothing
> is forgotten.
> Last updated: 2026-07-14

---

## 1. Purpose

An **AI agent that, on the user's behalf, scans 24/7, understands, selects, and (if
allowed) applies**.

**Problem:** People are job hunting but cannot check every site 24/7. There are many
listings; some people can't see them all, others can't be bothered, and they miss
opportunities.

**Solution:** While the user goes about their own work, the bot watches all active
listings in Azerbaijan for them, finds the ones matching their profile, notifies them,
and — if permitted — applies.

**Opportunity:** There is no local competitor doing this in Azerbaijan.

## 2. Who it serves

- **Job seekers (Azerbaijan)** → the user-acquisition engine (cheap/free)
- **Employers** → the real revenue source (Phase 3)

## 3. Product and features (full list)

### Phase 1 — Multi-user smart notifications (free)
- The user signs in and **uploads a CV**
- **Email association**
- **Manual filters**: job type, working hours, salary, etc.
- **or** setting up filters by **talking to the AI in chat** inside the app
- **or fully autonomous mode**: the AI reads the CV and decides for itself what fits
- **All active listings** in Azerbaijan are scanned (multi-source: jobsearch.az + similar sites)
- **The user chooses the notification frequency** (e.g., every 2-3 hours)
- Every listing includes the **application deadline**

### Phase 2 — Automatic applications
- **Trust ladder**: notify only → one-tap confirmation → fully autonomous
- **Automatic email** to every suitable job
- A **job-specific cover/motivation letter** (written by the AI)
- Sends only the CV if only a CV is requested, or written text if text is requested
- **Fills in web forms** if the site requires it
- Letter-source option: the user writes their own in advance / a **local LLM** / our AI /
  an external API (the user approves)
- Applications go out from the **user's own account** (no detectable pattern)

### Phase 3 — CV Pool (CV House)
- The user places their CV into the pool **of their own will and consent** (like an ad)
- Companies look at the pool when searching for suitable candidates
- The **AI selects/ranks the most suitable candidates**
- **Employers pay** → the real revenue

## 4. Business model

| Side | Price | Role |
|---|---|---|
| Job seeker | cheap/free (e.g., 5 AZN/month) | growth engine |
| Employer | the real fee (candidate access / subscription) | **revenue** |

This is essentially the Indeed/LinkedIn model: **free for job seekers, employers pay.**

## 5. The 2 metrics to measure (everything else is noise)

1. **Phase 1 — retention:** is the user still using it after 3-7 days?
2. **Phase 2 — response rate:** does auto-apply actually produce interviews/responses?

## 6. Risks (don't forget)

- **Success = churn.** A user finds a job in a month and leaves → lifetime value ≈ 1 month.
  Growth happens **only** through a constant stream of new users → design for virality/word of mouth.
- **Two-sided market (Phase 3):** employers won't pay for an empty pool → win the job-seeker
  side first.
- **CV = personal data:** opt-in is mandatory; a leak = a trust and legal disaster.
- **LLM cost** can blow up the unit economics → the user's own key / a local LLM.
- **AI-native alone is not a moat.** The real moat: the CV pool + a **data flywheel** that
  learns from hiring outcomes.
- **Platform/ToS risk:** sites may block us → multiple sources reduce this risk.

## 7. Positioning: AI-native

Remove the AI and the product collapses (understanding CVs, comprehending listings, writing
letters, autonomous applications). Competitors are a **keyword database**; we are an **agent**.
The current code is still rule-based (regex); the move to the AI-native core happens after
real users arrive.

## 8. Current state

A working **single-user** Telegram bot:
- Runs 5 times a day on GitHub Actions (Baku 09/12/15/18/21), free, on nobody's computer
- Scans **all ~2700 listings** on jobsearch.az (API + pagination + retry)
- Matches against the CV profile and sends a **single batched message** to Telegram (with
  application deadlines)

**Next step:** Phase 1 — make the bot multi-user.
