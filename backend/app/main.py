from fastapi import FastAPI

app = FastAPI(
    title="AI Investment Decision Engine",
    description="Backend API for an AI-driven Indian stock market investment engine",
    version="0.1.0"
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "AI Investment Engine backend is running"
    }