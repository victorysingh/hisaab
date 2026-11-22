from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from routers import agent, bills, customers, dashboard, forecast, invoices, payments, razorpay, settings, sms

app = FastAPI(title="Hisaab API", version="1.0.0")

config = get_settings()
origins = ["http://localhost:3000"] + ([config.web_origin] if config.web_origin else [])
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

app.include_router(customers.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(bills.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(forecast.router, prefix="/api/v1")
app.include_router(sms.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(razorpay.router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
