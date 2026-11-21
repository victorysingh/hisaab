# Hisaab

Voice-first fee and cash-flow app for Indian home tutors.

## Layout

- `apps/web/` - Next.js PWA (App Router, TypeScript, Tailwind, shadcn/ui)
- `apps/api/` - FastAPI backend
- `apps/sms-helper/` - Kotlin Android SMS helper (stretch)
- `packages/shared/` - shared API types generated from OpenAPI
- `supabase/` - Postgres schema, migrations and seed
- `docs/` - OpenAPI spec and agent log

## Local run

Web:

```
cd apps/web
npm install
npm run dev
```

API:

```
cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Tests:

```
cd apps/api
python -m pytest
```

## Deploy

- **Web:** Vercel, with root directory `apps/web`.
- **API:** Render or Railway, with root directory `apps/api` and start command:
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Set the environment variables listed in `.env.example` in the host dashboard. Never commit `.env`.
- CORS origin comes from the `WEB_ORIGIN` env var in `apps/api/app/main.py`.
