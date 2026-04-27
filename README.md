# Astro Compute

Deterministic astrology compute microservice for the Astro project.
Wraps **Swiss Ephemeris** (`pyswisseph`) behind a small FastAPI surface.
Called from the Next.js app at `github.com/Tatu1984/Astro` via shared-secret auth.

## Endpoints

| Method | Path       | Auth                 | Purpose                                         |
|-------:|------------|----------------------|-------------------------------------------------|
| GET    | `/healthz` | none                 | Liveness check (also reports secret config)     |
| POST   | `/natal`   | `X-Compute-Secret`   | Natal chart: planets, houses, asc, mc           |

More endpoints land per phase: `/transit`, `/synastry`, `/dasha`, `/divisional`, etc.

## Local development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Generate a secret and paste into .env:
# echo "COMPUTE_SHARED_SECRET=$(openssl rand -hex 32)"

uvicorn app.main:app --reload --port 8000
```

Smoke test:
```bash
curl http://localhost:8000/healthz
```

Run tests:
```bash
pip install pytest httpx
pytest
```

## Deploying on Render

This repo includes `render.yaml`. In the Render dashboard:

1. **New + → Web Service → Connect this repo**
2. `render.yaml` is auto-detected; accept defaults
3. Set the `COMPUTE_SHARED_SECRET` env var in the dashboard (it's marked `sync: false` so it's never committed)
4. Deploy. First build is slow (~3–5 min) because `pyswisseph` compiles native code.

After deploy, the service URL goes back into the Next.js app's env as `COMPUTE_BASE_URL`.

## Why a separate Python service?

Swiss Ephemeris and the Vedic libraries (Kerykeion, Jyotisha) are mature in Python and produce deterministic, identical results. Reimplementing in Node would risk subtle errors in astronomical math. We isolate Python here and call it from Next.js — Node owns user-facing logic, Python owns the numbers.
