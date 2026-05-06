import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
url = os.environ["DATABASE_URL"].replace("+asyncpg", "")

engine = create_engine(url)
with engine.connect() as conn:
    conn.execute(text("UPDATE alembic_version SET version_num = 'cdf11d509e0d' WHERE version_num = 'fd2995205f43'"))
    conn.commit()
print("done")