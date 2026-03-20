from fastapi import APIRouter

router = APIRouter()

# Placeholders for future modules
@router.get("/")
async def placeholder():
    return {"message": "Decision module placeholder"}