"""
Dependency helpers for agent nodes.

Each agent node that needs a database session should call
``get_agent_db_session()`` to open its own short-lived session rather than
sharing one across parallel branches.  Sessions are closed explicitly after
the node's work is complete; they are never stored in the graph state.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.llm_service import LLMService, get_llm_service

logger = logging.getLogger(__name__)


@contextmanager
def get_agent_db_session() -> Generator[Session, None, None]:
    """
    Open a fresh SQLAlchemy session for a single agent node.

    Usage::

        with get_agent_db_session() as db:
            results = db.query(Company).all()
    """
    session: Session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_agent_llm_service() -> LLMService:
    """Return the shared LLMService singleton."""
    return get_llm_service()
