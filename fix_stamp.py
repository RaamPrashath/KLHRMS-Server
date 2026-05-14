import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
url = os.environ["DATABASE_URL"].replace("+asyncpg", "")

engine = create_engine(url)
with engine.connect() as conn:
    result = conn.execute(text("SELECT version_num FROM alembic_version"))
    rows = result.fetchall()
    print("Current stamps:", rows)
    conn.execute(text("UPDATE alembic_version SET version_num = 'f0a1b2c3d4e5' WHERE version_num = '40e3ade9ac5a'"))
    conn.commit()
    print("done")