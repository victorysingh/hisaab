# Hisaab

Voice-first fee and cash-flow app for Indian home tutors.

## Stack

- apps/web: Next.js (App Router), TypeScript, Tailwind, shadcn/ui, Recharts, installable PWA
- apps/api: FastAPI with Pydantic
- supabase: Postgres, phone OTP login, Realtime (migrations and seed)
- docs: OpenAPI spec and agent log

## Run the web app

    cd apps/web
    npm install
    npm run dev

## Run the API

    cd apps/api
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload
    python -m pytest

Copy .env.example to .env and fill in values locally. Never commit .env.
