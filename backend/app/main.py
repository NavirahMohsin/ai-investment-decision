
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import v1_router

app = FastAPI(
    title="ArthAI API",
    description="Backend API for the ArthAI Financial Intelligence Platform",
    version="0.1.0"
)

# Allow our Next.js frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/")
def home():
    return {
        "message": "Welcome to ArthAI API",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": "ArthAI"
    }
