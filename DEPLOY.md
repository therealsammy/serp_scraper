# Deployment — Vercel (frontend) + Render (backend)

The frontend (Next.js) deploys to Vercel; the backend (FastAPI + Playwright + spaCy)
runs as a Docker container on Render with managed Postgres + Redis. They're separate
services that talk over HTTPS — Playwright/spaCy need a persistent process, so the
backend can't be serverless.

## 1. Backend → Render

**Option A — Blueprint (recommended).** Render → **New + → Blueprint** → pick this
repo. It reads [`render.yaml`](render.yaml) and provisions the web service, Redis, and
Postgres. Then fill the `sync:false` env vars in the dashboard:

- `FRONTEND_ORIGIN` → your Vercel URL (e.g. `https://serp-yourname.vercel.app`)
- `ADMIN_BOOTSTRAP_EMAIL`, `ADMIN_BOOTSTRAP_PASSWORD`
- Provider keys you have: `APIFY_API_TOKEN`, `BRAVE_API_KEY`, the SERP fallback keys,
  `GOOGLE_NL_API_KEY`, `LANGEXTRACT_*`

`DATABASE_URL`, `REDIS_URL`, and `JWT_SECRET` are wired/generated automatically.

**Option B — manual.** Create a Docker web service (root `backend/`), a Render Redis,
and a Render Postgres, then set the same env vars by hand (see §1a).

Notes:
- The app binds to Render's injected `$PORT` automatically.
- Any standard `postgres://` / `postgresql://` URL is normalized to the async driver.
- Health check path is `/health`.
- First request after idle is slow on the free plan (cold start + Chromium boot) —
  bump to an always-on instance for live demos.

## 1a. Database & Redis (the two data stores)

The backend needs **Postgres** (durable: users, invites) and **Redis** (quota
counters, cache, breakers). The blueprint provisions both automatically; below is how
to do it manually and/or with external providers, and how to wire the connection
strings.

### Postgres

The app accepts any standard `postgres://` / `postgresql://` URL — it auto-normalizes
to the async driver — so any of these work:

**On Render (managed):**
1. Render → **New + → PostgreSQL** → name `serp-postgres` → choose a region (same as
   the backend) → Create.
2. Open it → **Connections** → copy the **Internal Database URL** (use *internal* when
   the backend is on Render — faster, free egress).
3. On the backend service → **Environment** → add `DATABASE_URL` = that URL.

**On Neon / Supabase (external free tier):**
1. Create a project at [neon.tech](https://neon.tech) (or supabase.com) → it gives a
   `postgresql://USER:PASSWORD@HOST/DB?sslmode=require` string.
2. Set `DATABASE_URL` to it on the backend. (SSL is fine; asyncpg honors `sslmode`.)

> Tables are created automatically on first boot (`init_db()` runs `create_all`),
> and the bootstrap admin is seeded — no migration step needed for the first deploy.

### Redis

**On Render (managed):**
1. Render → **New + → Redis** → name `serp-redis` → **Maxmemory policy: `noeviction`**
   (critical — quota counters must not be evicted) → Create.
2. Open it → copy the **Internal Redis URL** (`redis://...`).
3. On the backend → **Environment** → add `REDIS_URL` = that URL.

**On Upstash (external, serverless free tier):**
1. Create a database at [upstash.com](https://upstash.com) → enable **TLS**.
2. Copy the `rediss://...` URL (note the double-s = TLS) → set `REDIS_URL` to it.
3. In the Upstash console set **eviction = off / noeviction**.

> Why `noeviction`: the quota engine, kill-switch, and monthly NL-unit counters live in
> Redis. If Redis evicts keys under memory pressure, caps could silently reset. The
> data is small (counters + short-TTL cache), so eviction should never trigger anyway.

### Verify the connections

After both env vars are set and the backend redeploys, check `/health` (200) and the
logs for `Application startup complete` with no DB/Redis errors. Then:
```bash
curl https://<your-backend>.onrender.com/health        # {"status":"ok"}
# log in as the seeded admin to confirm Postgres works:
curl -X POST https://<your-backend>.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"<ADMIN_BOOTSTRAP_EMAIL>","password":"<ADMIN_BOOTSTRAP_PASSWORD>"}'
```
A successful token response means Postgres (user seeded) **and** Redis (the request
touched quota keys) are both wired correctly.

## 2. Frontend → Vercel

Vercel → **Add New → Project** → import this repo.

- **Root Directory:** `frontend` ← important (monorepo).
- Framework preset: **Next.js** (auto-detected; [`vercel.json`](frontend/vercel.json)
  pins it).
- **Environment variable:** `NEXT_PUBLIC_API_URL` → your Render backend URL
  (e.g. `https://serp-backend.onrender.com`).
- Deploy.

## 3. Wire them together

1. Copy the Vercel production URL → set `FRONTEND_ORIGIN` on Render → redeploy backend
   (CORS + the anonymous-identity cookie use it; over HTTPS the cookie is automatically
   set `SameSite=None; Secure` for cross-site requests).
2. Confirm `NEXT_PUBLIC_API_URL` on Vercel points at the Render URL.
3. Visit the Vercel URL → run a DuckDuckGo search (no keys needed) to smoke-test.
4. Log in as the bootstrap admin → **Admin** → invite yourself a second user.

## Checklist
- [ ] `backend/.env` is **not** committed (gitignored); secrets only in dashboards
- [ ] `FRONTEND_ORIGIN` (Render) == Vercel URL; `NEXT_PUBLIC_API_URL` (Vercel) == Render URL
- [ ] `ADMIN_BOOTSTRAP_PASSWORD` changed from the default
- [ ] Redis `maxmemory-policy` = `noeviction` (quota counters must persist)
- [ ] Provider keys rotated if they were ever exposed locally
