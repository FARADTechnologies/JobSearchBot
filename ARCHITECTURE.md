# ARCHITECTURE.md — Matching Engine Architecture (locked: 2026-07-14)

> Two independent research passes (Claude Code + Claude Research) converged on the same
> architecture. This document fixes the decisions. Changes are made only with golden-set
> measurement. For the vision: [VISION.md](VISION.md)

## Core principles

1. **Analyze once, store it.** Every listing and every CV passes through the LLM exactly
   ONCE (structured JSON extraction + embedding), and the result is stored in the DB.
   Listing analyses are shared across ALL users — this is what saves the economics.
2. **Staged pipeline.** Start cheap and wide, finish expensive and narrow. The LLM never
   touches 2700 listings; it only touches the shortlist.
3. **Don't change without measuring.** Every pipeline change is scored on the golden set.
   "It feels like it works" is not data.

## Pipeline

```
[Stage 0 — Intake (each document once)]
  Listing → LLM extraction (JSON: title, skills, experience, language, location, salary; English)
          → BGE-M3 embedding → Supabase pgvector (jobs table)
  CV      → parse (PDF; OCR fallback for image-based PDFs) → LLM extraction (JSON, English)
          → BGE-M3 embedding → Supabase pgvector (cvs table)
          → a "check your profile" step for the user (parsing error ~15-25%)

[Stage 1 — Retrieval (cheap, over all listings)]
  SQL hard filter: location, language, min experience, salary (BEFORE embedding)
  → hybrid search: vector (cosine) + BM25, RRF fusion → top-50
  (measure BM25's contribution on the golden set — it sometimes hurts)

[Stage 2 — Reranking (medium cost, over top-50)]
  Cohere Rerank (free tier) or BGE-reranker-v2-m3 → top-10

[Stage 3 — LLM judge (expensive, over top-10)]
  Real fit decision + a "why it fits" explanation + a quality threshold
  Feed Azerbaijani/Russian text directly to the LLM (it understands it better than embeddings)

[Stage 4 — Notification]
  Only those above the threshold; batched; each match with an explanation + application deadline
```

## Technology decisions

| Layer | Decision | Why |
|---|---|---|
| DB + vector | **Supabase Postgres + pgvector** | Free, no card; metadata+vector in one place; standard under 10M vectors. A daily cron also prevents the 7-day pause |
| Embedding | **BGE-M3** (Cloudflare Workers AI free / self-host) | 100+ languages, stable on low-resource languages, dense+sparse, cross-lingual |
| Rerank | **Cohere Rerank free tier** (1000/month) → self-host BGE-reranker if exceeded | Rerank = the single highest-impact quality gain |
| LLM (listings) | **Gemini Flash free** | Listings are public data — using them for training is not a concern; the quota is generous |
| LLM (CVs) | **Groq (Llama 3.3 70B) / Cohere / Cerebras** | 🔴 These do NOT train on the data. A CV is personal data — it is NEVER sent to free Gemini (Google trains on prompts in the free tier) |
| Runtime | GitHub Actions cron (batch) + Supabase Edge Functions (webhook) | Free; the notification job does not need real time |
| Failover | Multiple providers (OpenRouter as backup) | Free quotas change without notice (Gemini cut 50-80% in December 2025) |

## Language strategy (Azerbaijani = low-resource risk)

1. **First:** BGE-M3 multilingual, as-is (cross-lingual: AZ CV ↔ EN listing works)
2. JSON extractions are already produced in English (no extra cost, the LLM already reads it)
3. If the golden set shows **nDCG@10 < 0.7** → add a translate-then-embed pivot
4. The LLM judge stage reads AZ/RU directly — the last line of defense
5. Don't trust general benchmarks: Azerbaijani is barely present in MTEB; measure on your own set

## Measurement (without it, everything is a guess)

- **Golden set:** 50-100 hand-labeled (CV, listing, fit/no-fit) pairs — the first task
- **Offline:** nDCG@10, recall@k — on every pipeline change
- **LLM-as-judge:** validate against human labels (target 75-90% agreement); binary
  pass/fail first, then a score; explanation required (improves agreement)
- **Online (the real truth):** notification CTR, save/apply rate, 3-7 day retention
- **Feedback table from day 1:** clicked/saved/applied/dismissed → labeled data for future
  fine-tuning = the moat

## What we will NOT do (popular but wrong for us)

- ❌ Vector search alone (no reranker) — weak precision
- ❌ Feeding everything to the LLM on every match — expensive, doesn't scale
- ❌ Graph DB / knowledge graph as the main engine — needless complexity
- ❌ Starting with Pinecone/Qdrant — pgvector is enough (revisit at 100K+ listings)
- ❌ Fine-tuning / our own model up front — no labeled data; after the flywheel (Phase 2+)
- ❌ Sending a CV to free Gemini — a privacy violation
- ❌ Real-time matching — batch is enough and much cheaper

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Scraping legal/ToS (hiQ $500K, Proxycurl shut down) | Slow scraping, robots.txt, don't go behind login; long-term partnerships with site owners |
| Notification fatigue (52% of people who turn off push abandon the app) | Quality threshold + batch + explanation; few but on-point |
| CV parsing error (~15-25% skill error) | OCR fallback + a user confirmation step + parsing-error tracking |
| Multi-source duplication | Dedup by fingerprint/embedding |
| Free-tier quotas are variable | Multi-provider failover; don't depend on a single model |
| Azerbaijan data-protection law (cross-border data) | Opt-in mandatory; legal advice required (before Phase 3) |
| Competitor: semantic platforms such as "Expertini" | Competitive analysis to be done (task) |

## Transition thresholds

- nDCG@10 < 0.7 → add the translation pivot
- Listing count 100K+ → evaluate Qdrant
- If the free quota is exceeded → paid Gemini Flash ($0.15/1M — still cheap)
- When feedback data accumulates → ConFit-style fine-tuning (Phase 2+)
