
import os
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base

# Load ENV
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not set")
    exit(1)

engine = sa.create_engine(DATABASE_URL)
meta = sa.MetaData()
meta.reflect(bind=engine)
print(f"Dropping tables: {list(meta.tables.keys())}")
meta.drop_all(bind=engine)
# Drop alembic_version explicitly if needed (it is a table)
print("Done.")
