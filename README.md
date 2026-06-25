# SERP Research Tool

A full-stack research tool that searches the open web across multiple providers,
extracts clean article text from each result, runs on-demand **entity extraction
(top-10 by salience)**, and serves it through an enterprise-style UI — governed by a
tiered quota engine with hard cost caps and invite-only access.

> **Compliance note:** Google results come from **Apify's managed Google Search
> Results Scraper** (a sanctioned API — Apify runs the infrastructure), not
> home-grown SERP scraping or CAPTCHA circumvention. The tool is rate-limited and
> intended for low-volume research.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js (App Router, TypeScript) + Tailwind |
| Backend | FastAPI (async) |
| Extraction | Playwright + trafilatura |
| Entities | spaCy (free) · Google Cloud NL · Apify LangExtract (LLM) |
| Data | Postgres (durable) + Redis (quota / cache / breakers) |
| Deploy | Docker Compose (local) · Vercel + Render (prod) |

## Features

- **Multi-provider search** — Google (via Apify), Brave, DuckDuckGo, behind one
  interface; pick the provider per query.
- **Geo-targeting** — country + language + **city-level** results. City precision uses
  Google's UULE encoding (e.g. "Austin, Texas, United States"). Same query from
  different cities returns genuinely localized SERPs.
- **SERP fallback rotation** — Serper → ScaleSERP → SerpAPI for registered users,
  per-key daily caps + circuit breaker (one legitimate account per vendor).
- **Content extraction** — Playwright fetches JS-rendered pages, trafilatura strips
  boilerplate; results **stream in over SSE** as each page finishes, with per-result
  status (extracted / blocked / error).
- **Entity extraction (top-10 by salience)** — per-result button. **Tier-based:** free
  users get local **spaCy** (computed salience); registered users get premium **Google
  NL** (native salience) or **Apify LangExtract** (LLM), with hard caps and spaCy
  fallback. See [Cost controls](#cost-controls).
- **Quota engine (Redis)** — anonymous vs. registered tiers, atomic capped counters,
  a shared race-free "borrow pool" (Lua), a global **kill-switch**, and a query
  **cache** that spends zero quota.
- **Invite-only auth** — no public signup; single-use, email-bound, expiring tokens
  (hashed at rest); you email the link yourself.
- **Admin panel** — users, invites, provider health, search kill-switch, cache hit
  rate, and **entity-engine usage / estimated spend**.
- **Export** — CSV / JSON.

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env     # change admin password; add keys you have
docker compose up --build
```

- Frontend → http://localhost:3000
- Backend docs (Swagger) → http://localhost:8000/docs

The bootstrap admin (`ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD`) is seeded
on first run. Sign in, open **Admin → Invite a user**, and email the generated link.

**Zero-key demo:** DuckDuckGo search and spaCy entity extraction work with **no API
keys at all**. Add keys to unlock Google/Brave search and the premium entity engines.

## API keys

All optional except where noted; set in `backend/.env`:

| Key | Unlocks | Free tier |
|-----|---------|-----------|
| `APIFY_API_TOKEN` | Google search (Apify actor) | ~$5 platform credits/mo |
| `BRAVE_API_KEY` | Brave search | 2,000/mo |
| `SERPER_API_KEY` / `SCALESERP_API_KEY` / `SERPAPI_API_KEY` | SERP fallback rotation | varies |
| `GOOGLE_NL_API_KEY` | Premium entities, true salience | 5,000 units/mo (billing acct required) |
| `LANGEXTRACT_LLM_KEY` (+ `APIFY_API_TOKEN`) | Premium entities via LLM | LLM provider's free tier (e.g. Gemini Flash) |

`ddgs`-free DuckDuckGo and spaCy need no keys.

## Cost controls

Every billable path is hard-capped so it cannot run up a surprise bill:

- **Apify (Google search)** — global daily kill-switch (`global.daily_cap`).
- **SERP fallback vendors** — per-vendor daily caps + circuit breaker.
- **Google NL entities** — billed **per 1,000 chars, rounded up; 5,000 units/month
  free**. Each call is **truncated to `entities.max_chars` (≈5 units)**, and a
  **monthly unit counter** stops at the free tier (`entities.google_nl_units_month`),
  falling back to spaCy. Default cap = free tier → **$0 spend** unless raised.
- **LangExtract** — separate daily request cap (`entities.langextract_daily`).

All visible live in the **admin panel**.

## Configuration

Tier limits & caps → `backend/limits.yaml`:

```yaml
anonymous:  { apify: 3,  brave: 3,  ddg: 10 }
registered: { apify: 20, brave: 20, ddg: unlimited }
fallback:   { serper: 80, scaleserp: 30, serpapi: 3 }
global:     { guarded_provider: apify, daily_cap: 100 }   # search kill-switch
entities:
  max_chars: 5000              # truncate before billing (~5 Google NL units/call)
  google_nl_units_month: 5000  # = free tier; hard monthly cap → $0 spend
  langextract_daily: 50
```

## Request precedence (search)

```
query
  ├─ cache hit?            → serve cached (spends nothing)
  ├─ within own quota?     → primary provider (Apify / Brave / DDG)
  ├─ borrow pool + global
  │   kill-switch ok?      → primary provider (atomic, race-free)
  ├─ SERP fallback         → Serper → ScaleSERP → SerpAPI (each capped)
  └─ exhausted             → graceful "resets at 00:00 UTC"
```

## Entity precedence (per result)

```
anonymous tier  → spaCy (computed salience, free)
registered tier → Google NL (native salience, monthly unit cap)
                → else LangExtract (LLM salience, daily cap)
                → spaCy fallback on cap / unconfigured / error
```

## Local dev (without Docker)

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
python -m spacy download en_core_web_sm
uvicorn app.main:app --reload      # needs Postgres + Redis running
```

**Frontend**
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

## Deployment (production)

- **Frontend** → Vercel (`NEXT_PUBLIC_API_URL` → backend URL)
- **Backend** → Render / Railway / Fly.io (container; Playwright + spaCy need a
  persistent process — not serverless-compatible)
- **Redis** → Upstash · **Postgres** → Neon / Supabase
- Set `FRONTEND_ORIGIN` on the backend to your Vercel domain for CORS.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design: data model, Redis key
schema, quota precedence, API surface, auth model, and deployment topology.
