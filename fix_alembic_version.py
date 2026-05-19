"""
Fix the alembic_version table by setting it to the correct head revision.
This script will:
1. Check the current alembic_version
2. Update it to the latest head (4b262fe191ed)
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from app.shared.config import normalize_database_url

load_dotenv()

# Get database URL and convert from asyncpg to psycopg2
db_url = normalize_database_url(os.environ["DATABASE_URL"]).replace("+asyncpg", "")

# Create engine
engine = create_engine(db_url)

def check_current_version():
    """Check the current alembic version in the database."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        rows = result.fetchall()
        if rows:
            print(f"Current alembic_version: {[row[0] for row in rows]}")
        else:
            print("No alembic_version found in database")
        return rows

def update_version(new_version):
    """Update the alembic_version table to the new version."""
    with engine.begin() as conn:
        # Delete all existing versions
        conn.execute(text("DELETE FROM alembic_version"))
        # Insert the new version
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
            {"version": new_version}
        )
        print(f"Updated alembic_version to: {new_version}")

if __name__ == "__main__":
    print("=" * 60)
    print("Alembic Version Fixer")
    print("=" * 60)
    
    # Check current version
    print("\n1. Checking current version...")
    current = check_current_version()
    
    # Update to the merge head
    print("\n2. Updating to merge head (4b262fe191ed)...")
    update_version("4b262fe191ed")
    
    # Verify
    print("\n3. Verifying update...")
    check_current_version()
    
    print("\n" + "=" * 60)
    print("Done! You can now run: alembic current")
    print("=" * 60)
