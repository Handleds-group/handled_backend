import asyncio
import redis.asyncio as redis
from urllib.parse import quote

password = "Ae0000095tDxmLzIz/aIvo26P3k9FFCGK6XFIc+/CFBfsUw/P7Fjqz5vIP+6wsu8yWCEMME"
encoded_password = quote(password, safe='')

REDIS_URL = f"redis://default:{encoded_password}@handled-iefh-ghai-875671.leapcell.cloud:6379/0?ssl=true&ssl_cert_reqs=required"

async def test_redis():
    r = redis.from_url(REDIS_URL)
    pong = await r.ping()
    print("Redis ping:", pong)

asyncio.run(test_redis())