"""API v1 라우터"""

from fastapi import APIRouter

from .agents import router as agents_router
from .tasks import router as tasks_router
from .health import router as health_router

api_router = APIRouter()

# 라우터 등록
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(health_router, prefix="/health", tags=["health"])

__all__ = ["api_router"]

