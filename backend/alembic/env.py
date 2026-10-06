"""Alembic environment. Uses the application's engine and metadata."""

from alembic import context

from app import models  # noqa: F401  (registers the tables on Base.metadata)
from app.core.config import get_settings
from app.database.session import Base, engine

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = get_settings().sqlalchemy_url
    context.configure(
        url=url if isinstance(url, str) else url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
