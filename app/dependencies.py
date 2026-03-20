from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from jose import jwt, JWTError
import os

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

ACCESS_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
if not ACCESS_SECRET:
    raise RuntimeError("ACCESS_TOKEN_SECRET is not set in environment")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    from app.models import User
    from sqlalchemy.future import select
    from app.database import AsyncSessionLocal

    try:
        payload = jwt.decode(token, ACCESS_SECRET, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user
