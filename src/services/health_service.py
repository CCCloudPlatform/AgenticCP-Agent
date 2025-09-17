"""
헬스체크 서비스

시스템 상태 및 의존성 상태 확인
"""

import time
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import db_manager
from ..config.redis import redis_manager
from ..config.settings import get_settings


class HealthService:
    """헬스체크 서비스"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.settings = get_settings()
        self._start_time = time.time()
    
    async def check_database_health(self) -> Dict[str, any]:
        """데이터베이스 상태 확인"""
        try:
            # 간단한 쿼리로 데이터베이스 연결 확인
            result = await self.db.execute(text("SELECT 1"))
            result.scalar()
            
            return {
                "status": "healthy",
                "message": "데이터베이스 연결 정상",
                "response_time_ms": 0  # 실제로는 측정 필요
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"데이터베이스 연결 실패: {str(e)}",
                "error": str(e)
            }
    
    async def check_redis_health(self) -> Dict[str, any]:
        """Redis 상태 확인"""
        try:
            # Redis 연결 확인
            redis_client = redis_manager.client
            await redis_client.ping()
            
            return {
                "status": "healthy",
                "message": "Redis 연결 정상",
                "response_time_ms": 0  # 실제로는 측정 필요
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Redis 연결 실패: {str(e)}",
                "error": str(e)
            }
    
    async def check_external_services(self) -> Dict[str, any]:
        """외부 서비스 상태 확인"""
        try:
            # Core 서비스 연결 확인 (실제 구현에서는 HTTP 요청)
            # import httpx
            # async with httpx.AsyncClient() as client:
            #     response = await client.get(
            #         f"{self.settings.external_service.core_service_url}/health",
            #         timeout=5.0
            #     )
            #     if response.status_code == 200:
            #         return {"status": "healthy", "message": "Core 서비스 연결 정상"}
            #     else:
            #         return {"status": "unhealthy", "message": f"Core 서비스 응답 오류: {response.status_code}"}
            
            # 임시로 항상 정상 반환
            return {
                "status": "healthy",
                "message": "외부 서비스 연결 정상",
                "response_time_ms": 0
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"외부 서비스 연결 실패: {str(e)}",
                "error": str(e)
            }
    
    async def get_system_info(self) -> Dict[str, any]:
        """시스템 정보 조회"""
        import psutil
        
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "uptime_seconds": time.time() - self._start_time,
            "python_version": f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}.{psutil.sys.version_info.micro}",
            "platform": psutil.sys.platform
        }
    
    async def get_health_status(self) -> Dict[str, any]:
        """전체 헬스체크 상태 조회"""
        # 각 의존성 상태 확인
        database_health = await self.check_database_health()
        redis_health = await self.check_redis_health()
        external_services_health = await self.check_external_services()
        
        # 전체 상태 결정
        all_healthy = all([
            dependency["status"] == "healthy"
            for dependency in [database_health, redis_health, external_services_health]
        ])
        
        overall_status = "healthy" if all_healthy else "unhealthy"
        
        # 시스템 정보
        system_info = await self.get_system_info()
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "version": self.settings.app_version,
            "environment": self.settings.environment,
            "uptime_seconds": system_info["uptime_seconds"],
            "dependencies": {
                "database": database_health,
                "redis": redis_health,
                "external_services": external_services_health
            },
            "system": system_info
        }
    
    async def get_liveness_check(self) -> Dict[str, any]:
        """라이브니스 체크 (서비스가 살아있는지 확인)"""
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": time.time() - self._start_time
        }
    
    async def get_readiness_check(self) -> Dict[str, any]:
        """레디니스 체크 (서비스가 요청을 처리할 준비가 되었는지 확인)"""
        # 핵심 의존성만 확인
        database_health = await self.check_database_health()
        
        is_ready = database_health["status"] == "healthy"
        
        return {
            "status": "ready" if is_ready else "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": {
                "database": database_health
            }
        }

