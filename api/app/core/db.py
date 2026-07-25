import json
import os
import time
from collections.abc import Generator

import boto3
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

_engine = None
_SessionLocal = None

# Aurora scale-to-zero: the first connection after the cluster has paused triggers
# a resume that can take ~15-25s. Connect with a generous timeout and retry the
# probe, bounded to stay under API Gateway's 29s integration timeout.
_CONNECT_TIMEOUT_SECONDS = 24
_RESUME_RETRIES = 2
_RESUME_BACKOFF_SECONDS = 0.5


def build_engine_config() -> tuple[str, dict]:
    """Return (url, connect_args) for the database engine.

    - Local/dev: set DATABASE_URL to any sync SQLAlchemy URL.
    - Lambda: build a direct psycopg2 connection to the shared Aurora cluster from
      the sb_app credentials in Secrets Manager (function runs inside the VPC).
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url, {}

    secret_arn = os.environ.get("DB_SECRET_ARN")
    if not secret_arn:
        raise RuntimeError("Set DATABASE_URL or DB_SECRET_ARN")

    client = boto3.client(
        "secretsmanager", region_name=os.environ.get("AWS_REGION", "us-west-2")
    )
    secret = json.loads(client.get_secret_value(SecretId=secret_arn)["SecretString"])

    user = secret["username"]
    password = secret["password"]
    host = secret.get("host") or os.environ.get("DB_HOST", "")
    port = secret.get("port", 5432)
    dbname = secret.get("dbname") or os.environ.get("DB_NAME", "scripturebuddy")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    return url, {"connect_timeout": _CONNECT_TIMEOUT_SECONDS}


def init_engine(url: str | None = None, connect_args: dict | None = None) -> None:
    """Create the engine + session factory. Idempotent (warm containers reuse it)."""
    global _engine, _SessionLocal
    if _engine is not None:
        return
    if url is None:
        url, connect_args = build_engine_config()
    _engine = create_engine(
        url,
        poolclass=NullPool,
        connect_args=connect_args or {},
    )
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def ensure_engine() -> None:
    """Initialise the engine if needed and probe the connection, riding out an
    Aurora resume-from-pause if one is in progress."""
    init_engine()
    for attempt in range(_RESUME_RETRIES + 1):
        try:
            with _engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError:
            if attempt == _RESUME_RETRIES:
                raise
            time.sleep(_RESUME_BACKOFF_SECONDS)


def get_engine():
    init_engine()
    return _engine


def get_db() -> Generator[Session]:
    """FastAPI dependency yielding a session."""
    init_engine()
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
