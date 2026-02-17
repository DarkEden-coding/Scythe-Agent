"""Base repository providing shared session management."""

from __future__ import annotations

from sqlalchemy.orm import Session


class BaseRepository:
    """Base class for all repositories with shared commit/rollback."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
