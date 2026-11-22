# Hisaab

Other apps make you type the past. Hisaab you just talk to, and it tells you the future.

Live: https://hisaab-peach-phi.vercel.app (API: https://hisaab-api-q5n9.onrender.com)

Hisaab is a voice-first fee and cash-flow app for Indian home tutors. It tells you whether you will have enough cash next month before the money runs out.

## The problem (PS1: small business cash flow)

Small service businesses keep track of who owes them money in their heads or in a notebook. They find out they are short when rent is due, not weeks before. Hisaab tracks what is owed and what is coming in, forecasts the balance day by day, and shows any shortfall early, with the reasons.

## Persona

Priya, a home tutor in Pune with 40 students in 3 batches. Fees of Rs 2,500 to 3,000 a month are due on the 5th, rent of Rs 12,000 is due on the 1st, and a salary of Rs 8,000 is due on the 7th. She speaks Hindi and English.

## Features (the 5 PS1 must-haves)

| Must-have | What it does | Where |
|---|---|---|
| Invoice-to-payment flow, with SMS matching | Generates monthly invoices, records payments, and matches incoming bank SMS to open invoices. Unclear matches go to a review list. | `POST /api/v1/invoices/generate`, `POST /api/v1/payments`, `POST /api/v1/payments/ingest`, `POST /api/v1/payments/{payment_id}/confirm-match`, `GET /api/v1/payments/review`. Engines: `engines/sms_parser.py`, `engines/matching.py` |
| Dues dashboard | Shows who owes and how much. | `GET /api/v1/dashboard/dues`. Home and Dues pages |
| 30/60/90-day forecast | Daily best, likely and worst balances, the first shortfall date, its named causes, and the assumptions used. | `GET /api/v1/forecast?days=30` (or 60, or 90). Engine: `engines/forecast.py` |
| What-if scenarios | A customer pays N days late, customers leave, a new bill, or a new customer. Shows the baseline and the changed forecast side by side. | `POST /api/v1/forecast/what-if`. Forecast chart and what-if slider |
| Action-today alerts with WhatsApp reminders | Home names who to chase today, and whether they cover the shortfall. Each reminder opens WhatsApp with the message filled in. Nothing is sent automatically. | Action card on Home. `whatsappUrl` in `apps/web/src/lib/api.ts` |

## Voice agent

Speak or type a request in the mic bar. The web app sends the transcript as text to `POST /api/v1/agent/turn`. A rule-based parser (`engines/intents.py`) understands English and Hinglish and picks one intent: dues, forecast, chase, what_if, record_payment, add_customers or help. The numbers in each reply come from the engines, not from a language model. Changes to data go through `POST /api/v1/agent/confirm`. Speech-to-text is not part of the API; the API takes the transcript as text.

## Architecture

    Next.js web app (apps/web)
        -> FastAPI (apps/api)
             -> engines: forecast, matching, sms_parser, intents, dues, payments, bills, statuses
                  (pure Python: no database, no LLM calls)
             -> app/repo.py: Supabase reads and writes
        -> Supabase Postgres (supabase/migrations, supabase/seed.sql)

## Run the API

    cd apps/api
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload

The API runs at http://127.0.0.1:8000. Check it with `GET /health`. The interactive docs are at http://127.0.0.1:8000/docs. The API routes are under `/api/v1`.

## Run the web app

    cd apps/web
    npm install
    npm run dev

The web app runs at http://localhost:3000. It needs the API running at the URL in `NEXT_PUBLIC_API_BASE_URL`.

## Environment variables

Copy `.env.example` to `.env` and fill in values locally. Never commit `.env`. Never commit real keys.

The API reads these names (`apps/api/app/config.py`):

- `SUPABASE_URL`: your Supabase project URL.
- `SUPABASE_SERVICE_KEY`: the Supabase service key used by the API.
- `DEMO_MODE`: `true` skips login and uses the demo business.
- `DEMO_OWNER_USER_ID`: the owner user ID of the demo business.
- `DEMO_TODAY` (optional): pins "today" to a date such as `2026-11-22`, so a demo looks the same whenever you record it.
- `WEB_ORIGIN` (optional): an extra allowed CORS origin, besides `http://localhost:3000`.

The web app reads these names (`apps/web/.env.local`):

- `NEXT_PUBLIC_API_BASE_URL` (defaults to `http://127.0.0.1:8000`)
- `NEXT_PUBLIC_BUSINESS_NAME` (optional; defaults to "Priya's Classes")

These names are set in `apps/web/.env.local` but the web code does not read them yet: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_DEMO_MODE`.

Razorpay (test mode), read by `apps/api/adapters/payments.py`:

- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`: from Razorpay Test Mode, API Keys. Without them, reminders carry no payment link.
- `RAZORPAY_WEBHOOK_SECRET`: must match the secret on the Razorpay webhook.

These names are in `.env.example` but are not read by the code yet: `SARVAM_API_KEY`, `OPENAI_API_KEY`, `LLM_API_KEY`, `TTS_API_KEY`, `API_BASE_URL`.

## Run the tests

    cd apps/api
    python -m pytest

The web app has no test script. Check it with `npm run lint` in `apps/web`.

## Deploy the API

`render.yaml` at the repo root defines the API as a Python web service on Render, with `rootDir` set to `apps/api`. Set the environment variables in the Render dashboard; they are marked `sync: false` in the file, so their values are not stored in the repo.

Step-by-step deploy (Render, Vercel, Razorpay webhook): `docs/DEPLOY.md`.

## Data

All data is synthetic. The seed data uses made-up names and no real phone numbers or UPI IDs.
