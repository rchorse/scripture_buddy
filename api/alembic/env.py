from sqlalchemy import create_engine

# Model metadata for autogenerate. Import every models module here as they are
# added so autogenerate sees the full picture.
import app.models.content
import app.models.core  # noqa: F401
from alembic import context
from app.core.db import build_engine_config
from app.models import metadata

target_metadata = metadata


def run_migrations_offline() -> None:
    url, _ = build_engine_config()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url, connect_args = build_engine_config()
    engine = create_engine(url, connect_args=connect_args or {})
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
