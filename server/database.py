import logging
from collections.abc import Generator
from sqlmodel import Session, SQLModel, create_engine
from server.config import settings
from server import models

logger = logging.getLogger(__name__)

# Module-level engine — initialized by get_engine() at startup
_engine = None


def get_engine():
    """Create and return a SQLModel engine from DATABASE_URL in config.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            connect_args = {"check_same_thread": False}
        )
    return _engine


def create_db_and_tables() -> None:
    """Create all database tables defined in models.py if they don't exist.

    Called once at app startup via the FastAPI lifespan context manager in api.py.
    """
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created")


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request.

    Usage in route handlers:
        session: Session = Depends(get_session)
    """
    engine = get_engine()
    with Session(engine) as session:
        yield session
