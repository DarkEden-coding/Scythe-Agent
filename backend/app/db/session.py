from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings

_engine = None
_sessionmaker: sessionmaker[Session] | None = None


def get_engine():
    global _engine
    if _engine is not None:
        return _engine
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    _engine = create_engine(settings.database_url, future=True, connect_args=connect_args)

    if "sqlite" in settings.database_url:

        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return _engine


def reset_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def get_sessionmaker() -> sessionmaker[Session]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = sessionmaker(bind=get_engine(), expire_on_commit=False, class_=Session)
    return _sessionmaker


def reset_sessionmaker() -> None:
    global _sessionmaker
    _sessionmaker = None
