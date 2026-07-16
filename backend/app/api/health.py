from fastapi import APIRouter

from app.core.responses import success

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return success({"status": "ok"})
