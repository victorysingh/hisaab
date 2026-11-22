# Hisaab: deployment handover

Repo: https://github.com/victorysingh/hisaab (branch `main`)
API (Render): https://hisaab-api-zcid.onrender.com · Web (Vercel): to be created

## 1. Render: API (`hisaab-api`)

Already created. Settings to confirm:

| Setting | Value |
|---|---|
| Root Directory | `apps/api` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |
| Region | Singapore |

### Environment variables

| Key | Value |
|---|---|
| `SUPABASE_URL` | `https://uugheqtrykmivkxthjkz.supabase.co` (no trailing slash) |
| `SUPABASE_ANON_KEY` | from `apps/api/.env` |
| `SUPABASE_SERVICE_KEY` | the **service_role** key from `apps/api/.env` |
| `DEMO_MODE` | `true` |
| `DEMO_OWNER_USER_ID` | the demo user's UID **only**. Check that nothing is glued on after it |
| `DEMO_TODAY` | `2026-11-22` |
| `PYTHON_VERSION` | `3.13.9` |
| `WEB_ORIGIN` | the Vercel URL, e.g. `https://hisaab-xxxx.vercel.app` (no trailing slash) |
| `RAZORPAY_KEY_ID` | `rzp_test_...` (Razorpay dashboard, Test Mode → API Keys) |
| `RAZORPAY_KEY_SECRET` | from the same screen |
| `RAZORPAY_WEBHOOK_SECRET` | any long random text; must match the webhook below |

### Known issue to fix first
`/health` works, but `/api/v1/forecast?days=60` fails, so the API can't read the data.
1. Open `https://hisaab-api-zcid.onrender.com/api/v1/customers`.
2. Render → hisaab-api → **Logs**: read the newest red error.
3. Almost always one of: `SUPABASE_SERVICE_KEY` truncated or the anon key pasted instead; `DEMO_OWNER_USER_ID` has extra text after the UID; `SUPABASE_URL` has a trailing `/`.
4. Fix it, **Save Changes**, wait for the redeploy, and open the forecast URL again. It should return JSON with `"shortfall"`.

## 2. Vercel: web

1. vercel.com → **Create New → Project** → import `victorysingh/hisaab`.
2. **Root Directory:** `apps/web` (click Edit). Framework: Next.js.
3. Environment variable: `NEXT_PUBLIC_API_BASE_URL` = `https://hisaab-api-zcid.onrender.com` (no trailing slash, no `/api/v1`).
4. Deploy, then put the Vercel URL into Render's `WEB_ORIGIN` (see above).
5. Open the Vercel URL. Home should show **"You'll be ₹6,000 short on 1 Dec"**.

If the page says "Failed to fetch": press F12 → Console. A CORS error means `WEB_ORIGIN` doesn't exactly match the Vercel URL. A 500 means the Render data issue above.

## 3. Razorpay webhook (test mode)

Razorpay dashboard → **Test Mode** → **Account & Settings → Webhooks → Add New Webhook**

| Field | Value |
|---|---|
| Webhook URL | `https://hisaab-api-zcid.onrender.com/api/v1/webhooks/razorpay` |
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
