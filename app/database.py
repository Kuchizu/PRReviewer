from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models import Base
from os import getenv

DATABASE_URL = getenv('DATABASE_URL', 'postgresql://user:password@db:5432/reviewer_service')

engine_kwargs = {
    'echo': getenv('SQLALCHEMY_ECHO', 'false').lower() == 'true'
}

if 'postgresql' in DATABASE_URL:
    engine_kwargs['pool_pre_ping'] = True

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
