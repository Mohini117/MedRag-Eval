# backend/db/session.py

import logging

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from backend.config import config
from backend.db.models import init_db


logger = logging.getLogger(__name__)


def _require_database_url() -> str:
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set.")
    return config.DATABASE_URL

# create_engine establishes the connection pool
# pool_pre_ping=True — tests connections before using them
# Prevents "connection closed" errors after periods of inactivity
engine = create_engine(
    _require_database_url(),
    pool_pre_ping=True,
    pool_recycle=300
)

# SessionLocal is a factory — call SessionLocal() to get a session
# autocommit=False — you control when transactions commit
# autoflush=False — changes not sent to DB until you call flush/commit
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    """
    FastAPI dependency — yields a database session per request.

    Why yield not return:
    Yield turns this into a context manager. FastAPI ensures
    the finally block runs after the request completes —
    even if an exception was raised. Session always closes.
    Without this, connections leak and your pool exhausts.
    """
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        yield db
    except OperationalError as exc:
        logger.error(f"Database unavailable: {str(exc)}")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Start PostgreSQL on localhost:5432 and retry."
        ) from exc
    finally:
        db.close()


def initialize_database() -> None:
    """
    Called once at application startup in main.py.
    Creates all tables if they don't exist.
    """
    init_db(engine)


def check_database_connection() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError as exc:
        logger.warning(f"Database connection check failed: {str(exc)}")
        return False
 
'''

## Progress card — save this
MEDRAG EVAL — PROGRESS CARD v4

Completed:
✓ config.py
✓ fetcher.py (ChatDoctor corpus + PubMedQA eval testset)
✓ indexer.py (fixed + semantic + parent-child + ChromaDB)
✓ strategy_a/b/c.py (all three pipelines)
✓ db/models.py (runs, metrics, claims, traces tables)
✓ db/session.py (connection pool + FastAPI dependency)

Next:
→ ragas_runner.py
→ deepeval_runner.py  
→ trulens_runner.py
→ main.py (FastAPI)

Key schema decisions:
- UUID primary keys (app-generated, no DB round trip needed)
- Metrics separate from runs (written at different times)
- Claims 1:many (one run → many individual claims)
- Traces lazy loaded (large data, only fetched when needed)
- Cascade deletes (delete run → deletes everything linked)


'''
