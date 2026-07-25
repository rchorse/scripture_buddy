import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.core.db import ensure_engine, init_engine
from app.routers import me


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise the engine once per Lambda cold start.
    init_engine()
    yield


app = FastAPI(title="ScriptureBuddy API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(me.router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok"}


_mangum = Mangum(app, lifespan="auto")


def handler(event, context):
    """Top-level Lambda handler. Routes admin/job tasks or falls through to Mangum."""
    task = event.get("task") if isinstance(event, dict) else None
    if task == "migrate":
        return _run_migrations()
    if task == "bootstrap_db":
        from app.jobs.bootstrap import bootstrap_database
        return bootstrap_database()
    if isinstance(event, dict) and event.get("warmer"):
        ensure_engine()
        return {"status": "warm"}
    return _mangum(event, context)


def _run_migrations():
    import alembic.config

    alembic_cfg = alembic.config.Config()
    alembic_cfg.set_main_option(
        "script_location", os.path.join(os.path.dirname(__file__), "alembic")
    )
    alembic.config.command.upgrade(alembic_cfg, "head")
    return {"status": "ok", "message": "Migrations applied successfully"}
