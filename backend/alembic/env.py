from alembic import context
from app.config import Settings
from app.db import make_engine

# Schema revisions are explicit SQL, including pgvector and generated tsvector columns.
engine = make_engine(Settings())
with engine.connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
