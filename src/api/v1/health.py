"""
헬스체크 API 엔드포인트

시스템 상태 및 의존성 상태 확인 API
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.database import get_async_session
from ...schemas.common import HealthCheckResponse
from ...services.health_service import HealthService

router = APIRouter()


def get_health_service(
    db: AsyncSession = Depends(get_async_session)
) -> HealthService:
    """헬스체크 서비스 의존성"""
    return HealthService(db)


@router.get(
    "/",
    response_model=HealthCheckResponse,
    summary="헬스체크",
    description="시스템의 전체 상태를 확인합니다."
)
async def health_check(
    health_service: HealthService = Depends(get_health_service)
) -> HealthCheckResponse:
    """헬스체크"""
    health_status = await health_service.get_health_status()
    
    # 상태에 따른 HTTP 상태 코드 설정
    if health_status["status"] == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )
    
    return HealthCheckResponse(**health_status)


@router.get(
    "/liveness",
    response_model=dict,
    summary="라이브니스 체크",
    description="서비스가 살아있는지 확인합니다."
)
async def liveness_check(
    health_service: HealthService = Depends(get_health_service)
) -> dict:
    """라이브니스 체크"""
    return await health_service.get_liveness_check()


@router.get(
    "/readiness",
    response_model=dict,
    summary="레디니스 체크",
    description="서비스가 요청을 처리할 준비가 되었는지 확인합니다."
)
async def readiness_check(
    health_service: HealthService = Depends(get_health_service)
) -> dict:
    """레디니스 체크"""
    readiness_status = await health_service.get_readiness_check()
    
    # 준비되지 않은 경우 503 상태 코드 반환
    if readiness_status["status"] == "not_ready":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=readiness_status
        )
    
    return readiness_status


@router.get(
    "/database",
    response_model=dict,
    summary="데이터베이스 상태 확인",
    description="데이터베이스 연결 상태를 확인합니다."
)
async def database_health_check(
    health_service: HealthService = Depends(get_health_service)
) -> dict:
    """데이터베이스 상태 확인"""
    return await health_service.check_database_health()


@router.get(
    "/redis",
    response_model=dict,
    summary="Redis 상태 확인",
    description="Redis 연결 상태를 확인합니다."
)
async def redis_health_check(
    health_service: HealthService = Depends(get_health_service)
) -> dict:
    """Redis 상태 확인"""
    return await health_service.check_redis_health()


@router.get(
    "/external-services",
    response_model=dict,
    summary="외부 서비스 상태 확인",
    description="외부 서비스 연결 상태를 확인합니다."
)
async def external_services_health_check(
    health_service: HealthService = Depends(get_health_service)
) -> dict:
    """외부 서비스 상태 확인"""
    return await health_service.check_external_services()


@router.get(
    "/system",
    response_model=dict,
    summary="시스템 정보",
    description="시스템 정보를 조회합니다."
)
async def system_info(
    health_service: HealthService = Depends(get_health_service)
) -> dict:
    """시스템 정보 조회"""
    return await health_service.get_system_info()

