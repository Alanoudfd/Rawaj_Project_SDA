import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# Always anchor Rawaj's local SQLite database at the repository root.  The
# outreach notebook runs from a nested directory, so a bare relative URL would
# otherwise silently create a second, empty `rawaj.db` beside the notebook.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = f"sqlite:///{(PROJECT_ROOT / 'rawaj.db').as_posix()}"


def _resolve_database_url(configured_url: str | None) -> str:
    """Keep the legacy relative local URL compatible and deterministic."""
    if configured_url in {None, "", "sqlite:///./rawaj.db", "sqlite:///rawaj.db"}:
        return DEFAULT_DATABASE_URL
    return configured_url


DATABASE_URL = _resolve_database_url(os.getenv("DATABASE_URL"))


engine = create_engine(
    DATABASE_URL,
    echo=False,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
