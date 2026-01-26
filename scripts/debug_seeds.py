
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.database import Base
from app.main import app # Triggers imports
from sqlalchemy import create_engine

def debug_tables():
    print("Registered tables in Base.metadata:")
    for t in Base.metadata.tables.keys():
        print(f"- {t}")

    if "seeds" in Base.metadata.tables:
        print("SUCCESS: 'seeds' table is registered.")
    else:
        print("FAILURE: 'seeds' table is NOT registered.")

if __name__ == "__main__":
    debug_tables()
