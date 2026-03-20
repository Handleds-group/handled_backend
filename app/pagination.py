from typing import Any, List
from fastapi import Query

def paginate(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return {"limit": limit, "offset": offset}