from datetime import datetime, timedelta
from jose import jwt
from dotenv import load_dotenv
import os

load_dotenv()

ACCESS_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
REFRESH_SECRET = os.getenv("REFRESH_TOKEN_SECRET")
ACCESS_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

if not ACCESS_SECRET:
    raise RuntimeError("ACCESS_TOKEN_SECRET is not set in environment")
if not REFRESH_SECRET:
    raise RuntimeError("REFRESH_TOKEN_SECRET is not set in environment")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, ACCESS_SECRET, algorithm="HS256")

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, REFRESH_SECRET, algorithm="HS256")

def decode_access_token(token: str):
    return jwt.decode(token, ACCESS_SECRET, algorithms=["HS256"])

def decode_refresh_token(token: str):
    return jwt.decode(token, REFRESH_SECRET, algorithms=["HS256"])
