import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.admin.routes import router as admin_router
from app.core.db import ensure_engine, init_engine
from app.routers import lessons, library, me, reviews


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
app.include_router(library.router, prefix="/v1")
app.include_router(lessons.router, prefix="/v1")
app.include_router(reviews.router, prefix="/v1")
app.include_router(admin_router)


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
    if task == "ingest":
        from app.jobs.ingest import ingest_scriptures
        return ingest_scriptures(event["work_slug"], event["s3_key"])
    if task == "validate_exercises":
        from app.jobs.validate_exercises import validate_exercises
        return validate_exercises(event["work_slug"])
    if task == "import_exercises":
        from app.jobs.import_exercises import import_exercises
        return import_exercises(event["work_slug"], event["s3_key"])
    if task == "set_work_status":
        # Owner stopgap until the M2 admin UI: flips a work between draft/released.
        from sqlalchemy import update
        from sqlalchemy.orm import Session as _Session

        from app.core.db import get_engine
        from app.models.content import Work

        assert event["status"] in ("draft", "released")
        with _Session(get_engine()) as s:
            s.execute(
                update(Work).where(Work.slug == event["work_slug"]).values(status=event["status"])
            )
            s.commit()
        return {"status": "ok", "work": event["work_slug"], "set_to": event["status"]}
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
