python - <<'PY'
import os, asyncio, asyncpg
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")
print("URL:", url)

async def main():
    try:
        conn = await asyncpg.connect(url)
        val = await conn.fetchval("SELECT 1")
        print("DB OK:", val)
        await conn.close()
    except Exception as e:
        print("DB ERROR:", type(e).__name__, e)

asyncio.run(main())
