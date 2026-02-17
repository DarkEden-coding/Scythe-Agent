from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import get_sessionmaker


def get_db() -> Generator[Session, None, None]:
    session_factory = get_sessionmaker()
    db = session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

