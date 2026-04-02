import os
import hmac
from fastapi import Header, HTTPException
from jose import jwt, JWTError

ACCESS_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
if not ACCESS_SECRET:
    raise RuntimeError("ACCESS_TOKEN_SECRET is not set in environment")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD is not set in environment")

def verify_admin_password(password: str) -> bool:
    return hmac.compare_digest(password or "", ADMIN_PASSWORD)

def require_admin(authorization: str = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing admin token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, ACCESS_SECRET, algorithms=["HS256"])
        if not payload.get("admin"):
            raise HTTPException(status_code=401, detail="Not an admin token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True
