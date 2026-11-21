from fastapi import FastAPI

app = FastAPI(title="Hisaab API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
