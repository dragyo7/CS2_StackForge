from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import SessionLocal, engine
from app.migrations import run_migrations
from app.providers.cswatch import CSWatchProvider
from app.providers.external import FaceitProvider, LeetifyProvider
from app.providers.steam import SteamProvider
from app.routes.platform import router as platform_router
from app.routes.players import router as players_router
from app.routes.rooms import router as rooms_router
from app.services import scheduler
from app.services.player_service import get_or_create_default_community


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_migrations(engine)
    db = SessionLocal()
    try:
        get_or_create_default_community(db)
    finally:
        db.close()
    scheduler.start_background_scheduler()
    try:
        yield
    finally:
        await scheduler.stop_background_scheduler()


settings = get_settings()

app = FastAPI(
    title="StackForge API",
    version="0.1.0",
    description="Private CS2 5v5 match organizer and deterministic 126-partition team balancer.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players_router)
app.include_router(rooms_router)
app.include_router(platform_router)


@app.get("/api/health")
def health():
    sched = scheduler.get_scheduler_health()
    return {
        "status": "ok",
        "providers": {
            "steam": "configured" if SteamProvider().is_configured else "not_configured",
            "faceit": "configured" if FaceitProvider().is_configured else "not_configured",
            "leetify": "keyless_public_ready" if not LeetifyProvider().api_key else "configured",
            "cswatch": "public_ready",
        },
        "map_policy": "random_no_picker",
        "scheduler": sched["status"],
        "scheduler_detail": sched,
    }
