import logging
from collections.abc import Generator

from sqlmodel import Session, SQLModel

logger = logging.getLogger(__name__)

# Module-level engine — initialized by get_engine() at startup
_engine = None


def get_engine():
    """Create and return a SQLModel engine from DATABASE_URL in config.

    TODO:
    - Import settings from server.config
    - Create engine with create_engine(settings.database_url, connect_args={"check_same_thread": False})
      (check_same_thread=False is required for SQLite with FastAPI's async request handling)
    - Assign to the module-level _engine variable
    - Return the engine
    """
    pass


def create_db_and_tables() -> None:
    """Create all database tables defined in models.py if they don't exist.

    Called once at app startup via the FastAPI lifespan context manager in api.py.

    TODO:
    - Call get_engine() to ensure the engine is initialized
    - Call SQLModel.metadata.create_all(engine) to create tables
    """
    pass


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request.

    Usage in route handlers:
        session: Session = Depends(get_session)

    TODO:
    - Call get_engine() to get the engine
    - Use Session(engine) as a context manager
    - Yield the session so FastAPI handles cleanup after the request
    """
    pass
