# Hisaab: deployment handover

Repo: https://github.com/victorysingh/hisaab (branch `main`)

| | URL |
|---|---|
| Web (Vercel) | https://hisaab-peach-phi.vercel.app |
| API (Render) | https://hisaab-api-q5n9.onrender.com |

The earlier API at `hisaab-api-zcid.onrender.com` (another Render account) is no longer used.

## 1. Render: API (`hisaab-api`)

Created from the public repo URL, so it is not connected to GitHub. To ship new API code: Render → hisaab-api → **Manual Deploy → Deploy latest commit**.

| Setting | Value |
|---|---|
| Root Directory | `apps/api` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |
| Region / Plan | Singapore / Free |

### Environment variables

| Key | Value |
|---|---|
| `SUPABASE_URL` | `https://uugheqtrykmivkxthjkz.supabase.co` (no trailing slash) |
| `SUPABASE_SERVICE_KEY` | the **service_role** key from `apps/api/.env` |
| `DEMO_MODE` | `true` |
| `DEMO_OWNER_USER_ID` | the demo user's UID only |
| `DEMO_TODAY` | `2026-11-22` |
| `PYTHON_VERSION` | `3.13.9` |
| `WEB_ORIGIN` | `https://hisaab-peach-phi.vercel.app` (no trailing slash) |
| `RAZORPAY_KEY_ID` | `rzp_test_...` (Razorpay, Test Mode, API Keys). Not set yet |
| `RAZORPAY_KEY_SECRET` | from the same screen. Not set yet |
| `RAZORPAY_WEBHOOK_SECRET` | any long random text; must match the webhook below. Not set yet |

Check: `https://hisaab-api-q5n9.onrender.com/api/v1/forecast?days=60` returns JSON with `"shortfall"`.

## 2. Vercel: web

Project `hisaab`, root `apps/web`, deployed with the Vercel CLI (the repo owner's GitHub account has no Vercel integration, so pushes do not deploy). Env var: `NEXT_PUBLIC_API_BASE_URL` = `https://hisaab-api-q5n9.onrender.com`.

To redeploy:

```
cd apps/web
npx vercel deploy --prod
```

If the page says "Failed to fetch": press F12 → Console. A CORS error means `WEB_ORIGIN` on Render doesn't exactly match the Vercel URL.

## 3. Razorpay webhook (test mode)

Razorpay dashboard → **Test Mode** → **Account & Settings → Webhooks → Add New Webhook**

| Field | Value |
|---|---|
| Webhook URL | `https://hisaab-api-q5n9.onrender.com/api/v1/webhooks/razorpay` |
| Secret | same as `RAZORPAY_WEBHOOK_SECRET` on Render |
| Active events | `payment_link.paid` |

Even without the webhook, Home checks open payment links every few seconds and marks paid ones (`/payment-links/sync`).

**Test payment:** Dues → **Remind** on someone, then open the `rzp.io` link in the WhatsApp message → pay with Razorpay's **test UPI ID `success@razorpay`** (or a test card). Within seconds Home shows "Payment received".

## 4. Before the demo / recording

- Render free tier **sleeps after 15 minutes**. Open `/health` 1 minute before, since the first call takes about 50 seconds.
- Reset the demo data: run `supabase/demo-setup.sql` in the Supabase SQL Editor.
- Use **Chrome** for voice (mic permission must be allowed for the Vercel URL).
- The SMS simulator is at `/sms-simulator`. Click a preset each time; re-sending the same text is rejected as a duplicate on purpose.

## 5. Regenerate the API contract (Slice 3)

```
cd apps/api
python scripts/export_openapi.py      # writes docs/openapi.json
```
