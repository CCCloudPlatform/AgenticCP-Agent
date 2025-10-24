"""API v1 라우터"""

from fastapi import APIRouter

from .agents import router as agents_router
from .tasks import router as tasks_router
from .health import router as health_router
from .multi_agent import router as multi_agent_router

api_router = APIRouter()

# 라우터 등록
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(multi_agent_router, prefix="/multi-agent", tags=["multi-agent"])

__all__ = ["api_router"]

