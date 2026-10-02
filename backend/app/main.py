from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analytics, clients, feedback, matches, profiles
from app.core.config import settings

app = FastAPI(title="MatchGuard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clients.router)
app.include_router(profiles.router)
app.include_router(matches.router)
app.include_router(feedback.router)
app.include_router(analytics.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "MatchGuard API"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
