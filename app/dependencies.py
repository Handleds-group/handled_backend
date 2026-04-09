from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from app.database import SessionLocal
from jose import ExpiredSignatureError, JWTError
from datetime import datetime
from dotenv import load_dotenv
import os
from app.tokens import decode_access_token

load_dotenv()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

ACCESS_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
if not ACCESS_SECRET:
    raise RuntimeError("ACCESS_TOKEN_SECRET is not set in environment")

def get_current_user(token: str = Depends(oauth2_scheme)):
    from app.models import User

    try:
        payload = decode_access_token(token)
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    session = SessionLocal()
    try:
        result = session.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        user.last_seen = datetime.utcnow()
        session.add(user)
        session.commit()
        return user
    finally:
        session.close()
