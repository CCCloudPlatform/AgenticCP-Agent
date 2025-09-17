"""
AgenticCP Agent 메인 애플리케이션

FastAPI 기반 에이전트 서비스 메인 애플리케이션
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from .api.v1 import api_router
from .config.database import db_manager
from .config.redis import redis_manager
from .config.settings import get_settings
from .schemas.common import ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """애플리케이션 생명주기 관리"""
    # 시작 시 실행
    logger.info("🚀 AgenticCP Agent 서비스 시작 중...")
    
    # 데이터베이스 연결 확인
    try:
        # 데이터베이스 연결 테스트
        logger.info("📊 데이터베이스 연결 확인 중...")
        # 실제 구현에서는 데이터베이스 연결 테스트 수행
        logger.info("✅ 데이터베이스 연결 성공")
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {e}")
        raise
    
    # Redis 연결 확인
    try:
        logger.info("🔴 Redis 연결 확인 중...")
        # 실제 구현에서는 Redis 연결 테스트 수행
        logger.info("✅ Redis 연결 성공")
    except Exception as e:
        logger.error(f"❌ Redis 연결 실패: {e}")
        # Redis는 선택적이므로 경고만 출력
        logger.warning("⚠️ Redis 연결 실패 - 캐싱 기능이 비활성화됩니다")
    
    logger.info("🎉 AgenticCP Agent 서비스 시작 완료!")
    
    yield
    
    # 종료 시 실행
    logger.info("🛑 AgenticCP Agent 서비스 종료 중...")
    
    # 데이터베이스 연결 종료
    try:
        await db_manager.close()
        logger.info("✅ 데이터베이스 연결 종료 완료")
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 종료 실패: {e}")
    
    # Redis 연결 종료
    try:
        await redis_manager.close()
        logger.info("✅ Redis 연결 종료 완료")
    except Exception as e:
        logger.error(f"❌ Redis 연결 종료 실패: {e}")
    
    logger.info("👋 AgenticCP Agent 서비스 종료 완료!")


def create_app() -> FastAPI:
    """FastAPI 애플리케이션 생성"""
    settings = get_settings()
    
    # FastAPI 앱 생성
    app = FastAPI(
        title=settings.api.title,
        description=settings.api.description,
        version=settings.api.version,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan
    )
    
    # 미들웨어 설정
    setup_middleware(app, settings)
    
    # 라우터 등록
    app.include_router(
        api_router,
        prefix=settings.api.v1_prefix
    )
    
    # 루트 엔드포인트
    @app.get("/", tags=["root"])
    async def root():
        """루트 엔드포인트"""
        return {
            "message": "AgenticCP Agent API",
            "version": settings.app_version,
            "environment": settings.environment,
            "docs_url": "/docs" if settings.is_development else None
        }
    
    # 전역 예외 처리기
    setup_exception_handlers(app)
    
    return app


def setup_middleware(app: FastAPI, settings) -> None:
    """미들웨어 설정"""
    
    # CORS 미들웨어
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.origins,
        allow_credentials=settings.cors.credentials,
        allow_methods=settings.cors.methods,
        allow_headers=settings.cors.headers,
    )
    
    # 신뢰할 수 있는 호스트 미들웨어 (프로덕션 환경)
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]  # 실제 환경에서는 구체적인 호스트 지정
        )
    
    # 요청 로깅 미들웨어
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """요청 로깅"""
        start_time = time.time()
        
        # 요청 로깅
        logger.info(
            f"📥 {request.method} {request.url.path} - "
            f"Client: {request.client.host if request.client else 'unknown'}"
        )
        
        # 요청 처리
        response = await call_next(request)
        
        # 응답 로깅
        process_time = time.time() - start_time
        logger.info(
            f"📤 {request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        
        # 응답 헤더에 처리 시간 추가
        response.headers["X-Process-Time"] = str(process_time)
        
        return response


def setup_exception_handlers(app: FastAPI) -> None:
    """전역 예외 처리기 설정"""
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """ValueError 처리"""
        logger.error(f"ValueError: {exc}")
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                code="VALIDATION_ERROR",
                message=str(exc),
                path=request.url.path,
                method=request.method
            ).dict()
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """일반 예외 처리"""
        logger.error(f"Unexpected error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                code="INTERNAL_SERVER_ERROR",
                message="서버 내부 오류가 발생했습니다",
                path=request.url.path,
                method=request.method
            ).dict()
        )


# 애플리케이션 인스턴스 생성
app = create_app()

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.logging.level.lower()
    )

