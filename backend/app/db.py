from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings


def make_engine(settings: Settings):
    return create_engine(settings.database_url, pool_pre_ping=True)


def session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)
