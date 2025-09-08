# Python FastAPI 개발 표준

## 📋 개요

이 문서는 AgenticCP Agent 프로젝트에서 Python FastAPI를 사용한 개발 시 준수해야 할 표준과 가이드라인을 정의합니다.

## 🏗️ 프로젝트 구조 표준

### 디렉토리 구조

```
src/
├── api/                    # API 라우터
│   └── v1/                # API 버전별 라우터
├── config/                # 설정 관리
├── models/                # SQLAlchemy 모델
├── schemas/               # Pydantic 스키마 (DTO)
├── services/              # 비즈니스 로직
├── utils/                 # 유틸리티 함수
├── exceptions/            # 커스텀 예외
└── main.py               # 애플리케이션 진입점
```

### 네이밍 규칙

- **패키지/모듈**: `snake_case` (`user_service.py`)
- **클래스**: `PascalCase` (`UserService`, `UserModel`)
- **함수/변수**: `snake_case` (`get_user_by_id`, `user_id`)
- **상수**: `UPPER_SNAKE_CASE` (`MAX_RETRY_COUNT`)
- **API 엔드포인트**: `kebab-case` (`/api/v1/user-profiles`)

## 🎨 코드 스타일 가이드

### 1. 클래스 작성 규칙

```python
"""
사용자 관리 서비스

사용자의 생성, 조회, 수정, 삭제 기능을 제공합니다.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from ..models.user import User
from ..schemas.user import UserCreate, UserUpdate
from .base_service import BaseService


class UserService(BaseService[User, UserCreate, UserUpdate]):
    """사용자 관리 서비스"""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__(User, db_session)
        self.logger = logger.bind(service="user")
    
    async def create_user(self, user_data: UserCreate) -> User:
        """
        사용자를 생성합니다.
        
        Args:
            user_data: 사용자 생성 데이터
            
        Returns:
            생성된 사용자 객체
            
        Raises:
            ValueError: 중복된 사용자명 또는 이메일인 경우
        """
        self.logger.info(f"사용자 생성 시작: username={user_data.username}")
        
        # 중복 검증
        if await self.exists_by_username(user_data.username):
            raise ValueError(f"사용자명 '{user_data.username}'이 이미 존재합니다")
        
        # 사용자 생성
        user = await self.create(user_data)
        
        self.logger.info(f"사용자 생성 완료: user_id={user.id}")
        return user
```

### 2. 함수 작성 규칙

```python
async def get_user_by_id(
    self, 
    user_id: int,
    include_inactive: bool = False
) -> Optional[User]:
    """
    ID로 사용자를 조회합니다.
    
    Args:
        user_id: 사용자 ID
        include_inactive: 비활성 사용자 포함 여부
        
    Returns:
        사용자 객체 또는 None
        
    Raises:
        ValueError: 유효하지 않은 사용자 ID인 경우
    """
    if user_id <= 0:
        raise ValueError(f"유효하지 않은 사용자 ID: {user_id}")
    
    self.logger.debug(f"사용자 조회: user_id={user_id}")
    
    user = await self.get_by_id(user_id)
    
    if user and not include_inactive and not user.is_active:
        return None
    
    return user
```

### 3. 타입 힌트 사용

```python
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

# ✅ 좋은 예
async def process_users(
    user_ids: List[int],
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Union[int, List[User]]]:
    """사용자 목록 처리"""
    pass

# ❌ 나쁜 예
async def process_users(user_ids, options=None):
    """사용자 목록 처리"""
    pass
```

## 🗄️ 데이터베이스 표준

### 1. SQLAlchemy 모델 작성

```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from .base import Base


class User(Base):
    """사용자 모델"""
    
    __tablename__ = "users"
    
    # 기본 정보
    username = Column(
        String(50), 
        unique=True, 
        nullable=False, 
        index=True,
        comment="사용자명"
    )
    email = Column(
        String(255), 
        unique=True, 
        nullable=False, 
        index=True,
        comment="이메일"
    )
    
    # 상태 정보
    is_active = Column(
        Boolean, 
        nullable=False, 
        default=True,
        comment="활성화 여부"
    )
    
    # 메타데이터
    last_login_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="마지막 로그인 시간"
    )
    
    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<User(id={self.id}, username='{self.username}')>"
    
    @property
    def is_online(self) -> bool:
        """온라인 상태 여부"""
        if not self.last_login_at:
            return False
        
        from datetime import datetime, timedelta
        return self.last_login_at > datetime.utcnow() - timedelta(minutes=30)
```

### 2. Repository 패턴

```python
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User


class UserRepository:
    """사용자 데이터 접근 계층"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def find_by_username(self, username: str) -> Optional[User]:
        """사용자명으로 사용자 조회"""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def find_active_users(self) -> List[User]:
        """활성 사용자 목록 조회"""
        result = await self.db.execute(
            select(User).where(User.is_active == True)
        )
        return result.scalars().all()
    
    async def find_by_email_domain(self, domain: str) -> List[User]:
        """이메일 도메인으로 사용자 조회"""
        result = await self.db.execute(
            select(User).where(User.email.endswith(f"@{domain}"))
        )
        return result.scalars().all()
```

## 🌐 API 설계 표준

### 1. FastAPI 라우터 작성

```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from ...schemas.user import UserCreate, UserUpdate, UserResponse
from ...services.user_service import UserService
from ...config.database import get_async_session

router = APIRouter()


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="사용자 생성",
    description="새로운 사용자를 생성합니다.",
    responses={
        201: {"description": "사용자가 성공적으로 생성되었습니다"},
        400: {"description": "잘못된 요청 데이터"},
        409: {"description": "중복된 사용자명 또는 이메일"}
    }
)
async def create_user(
    user_data: UserCreate,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """사용자 생성"""
    try:
        user = await user_service.create_user(user_data)
        return UserResponse.from_orm(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
```

### 2. 의존성 주입

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.database import get_async_session
from ...services.user_service import UserService


def get_user_service(
    db: AsyncSession = Depends(get_async_session)
) -> UserService:
    """사용자 서비스 의존성"""
    return UserService(db)


# 사용 예시
@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    user_service: UserService = Depends(get_user_service)
):
    """사용자 조회"""
    pass
```

### 3. 요청/응답 스키마

```python
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    """사용자 생성 요청 스키마"""
    
    username: str = Field(
        ..., 
        min_length=2, 
        max_length=50,
        description="사용자명"
    )
    email: str = Field(
        ..., 
        regex=r'^[^@]+@[^@]+\.[^@]+$',
        description="이메일 주소"
    )
    full_name: Optional[str] = Field(
        None, 
        max_length=100,
        description="전체 이름"
    )
    
    @validator('username')
    def validate_username(cls, v):
        """사용자명 검증"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('사용자명은 영문, 숫자, 하이픈, 언더스코어만 사용 가능합니다')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "full_name": "John Doe"
            }
        }


class UserResponse(BaseModel):
    """사용자 응답 스키마"""
    
    id: int = Field(..., description="사용자 ID")
    username: str = Field(..., description="사용자명")
    email: str = Field(..., description="이메일")
    full_name: Optional[str] = Field(None, description="전체 이름")
    is_active: bool = Field(..., description="활성화 여부")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

## ⚠️ 예외 처리 표준

### 1. 커스텀 예외 클래스

```python
from typing import Optional


class AgenticCpException(Exception):
    """기본 예외 클래스"""
    
    def __init__(
        self, 
        message: str, 
        code: Optional[str] = None,
        details: Optional[dict] = None
    ):
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details
        super().__init__(self.message)


class UserNotFoundException(AgenticCpException):
    """사용자를 찾을 수 없는 경우"""
    
    def __init__(self, user_id: int):
        super().__init__(
            message=f"사용자 ID {user_id}를 찾을 수 없습니다",
            code="USER_NOT_FOUND",
            details={"user_id": user_id}
        )


class DuplicateUserException(AgenticCpException):
    """중복된 사용자인 경우"""
    
    def __init__(self, field: str, value: str):
        super().__init__(
            message=f"{field} '{value}'가 이미 존재합니다",
            code="DUPLICATE_USER",
            details={"field": field, "value": value}
        )
```

### 2. 전역 예외 처리기

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from ..exceptions import AgenticCpException, UserNotFoundException


def setup_exception_handlers(app: FastAPI) -> None:
    """전역 예외 처리기 설정"""
    
    @app.exception_handler(AgenticCpException)
    async def agenticcp_exception_handler(
        request: Request, 
        exc: AgenticCpException
    ):
        """커스텀 예외 처리"""
        logger.error(f"비즈니스 예외 발생: {exc.message}", extra=exc.details)
        
        return JSONResponse(
            status_code=400,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "path": request.url.path,
                "method": request.method
            }
        )
    
    @app.exception_handler(UserNotFoundException)
    async def user_not_found_handler(
        request: Request, 
        exc: UserNotFoundException
    ):
        """사용자 없음 예외 처리"""
        return JSONResponse(
            status_code=404,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        )
```

## 📝 로깅 표준

### 1. 로거 설정

```python
from loguru import logger
import sys


def setup_logging():
    """로깅 설정"""
    
    # 기본 로거 제거
    logger.remove()
    
    # 콘솔 로거 추가
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level="INFO"
    )
    
    # 파일 로거 추가
    logger.add(
        "logs/agent.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="100 MB",
        retention="30 days",
        compression="zip"
    )
```

### 2. 로깅 사용법

```python
from loguru import logger


class UserService:
    """사용자 서비스"""
    
    def __init__(self):
        self.logger = logger.bind(service="user")
    
    async def create_user(self, user_data: UserCreate) -> User:
        """사용자 생성"""
        self.logger.info(
            "사용자 생성 시작",
            username=user_data.username,
            email=user_data.email
        )
        
        try:
            # 사용자 생성 로직
            user = await self._create_user_internal(user_data)
            
            self.logger.info(
                "사용자 생성 완료",
                user_id=user.id,
                username=user.username
            )
            
            return user
            
        except Exception as e:
            self.logger.error(
                "사용자 생성 실패",
                username=user_data.username,
                error=str(e),
                exc_info=True
            )
            raise
```

## 🧪 테스트 표준

### 1. 단위 테스트

```python
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.user_service import UserService
from ..schemas.user import UserCreate
from ..exceptions import DuplicateUserException


class TestUserService:
    """사용자 서비스 테스트"""
    
    @pytest.fixture
    async def user_service(self, db_session: AsyncSession):
        """사용자 서비스 픽스처"""
        return UserService(db_session)
    
    @pytest.fixture
    def user_create_data(self):
        """사용자 생성 데이터 픽스처"""
        return UserCreate(
            username="testuser",
            email="test@example.com",
            full_name="Test User"
        )
    
    @pytest.mark.asyncio
    async def test_create_user_success(
        self, 
        user_service: UserService, 
        user_create_data: UserCreate
    ):
        """사용자 생성 성공 테스트"""
        # Given
        with patch.object(user_service, 'exists_by_username', return_value=False):
            with patch.object(user_service, 'create') as mock_create:
                mock_user = AsyncMock()
                mock_user.id = 1
                mock_user.username = "testuser"
                mock_create.return_value = mock_user
                
                # When
                result = await user_service.create_user(user_create_data)
                
                # Then
                assert result.id == 1
                assert result.username == "testuser"
                mock_create.assert_called_once_with(user_create_data)
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(
        self, 
        user_service: UserService, 
        user_create_data: UserCreate
    ):
        """중복 사용자명으로 생성 시 예외 발생 테스트"""
        # Given
        with patch.object(user_service, 'exists_by_username', return_value=True):
            
            # When & Then
            with pytest.raises(DuplicateUserException) as exc_info:
                await user_service.create_user(user_create_data)
            
            assert "testuser" in str(exc_info.value)
```

### 2. 통합 테스트

```python
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

from ..main import app


class TestUserAPI:
    """사용자 API 통합 테스트"""
    
    @pytest.fixture
    def client(self):
        """테스트 클라이언트 픽스처"""
        return TestClient(app)
    
    @pytest.fixture
    async def async_client(self):
        """비동기 테스트 클라이언트 픽스처"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    def test_create_user_success(self, client: TestClient):
        """사용자 생성 API 성공 테스트"""
        # Given
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User"
        }
        
        # When
        response = client.post("/api/v1/users/", json=user_data)
        
        # Then
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
    
    def test_create_user_duplicate_username(self, client: TestClient):
        """중복 사용자명으로 생성 시 에러 테스트"""
        # Given
        user_data = {
            "username": "existinguser",
            "email": "test@example.com",
            "full_name": "Test User"
        }
        
        # When
        response = client.post("/api/v1/users/", json=user_data)
        
        # Then
        assert response.status_code == 409
        data = response.json()
        assert "already exists" in data["message"]
```

## 🔧 설정 관리 표준

### 1. Pydantic Settings 사용

```python
from pydantic import BaseSettings, Field
from typing import List, Optional


class DatabaseSettings(BaseSettings):
    """데이터베이스 설정"""
    
    url: str = Field(..., description="데이터베이스 URL")
    echo: bool = Field(False, description="SQL 쿼리 로깅 여부")
    pool_size: int = Field(10, ge=1, le=100, description="연결 풀 크기")
    
    class Config:
        env_prefix = "DATABASE_"


class Settings(BaseSettings):
    """전체 애플리케이션 설정"""
    
    app_name: str = Field("AgenticCP Agent", description="애플리케이션 이름")
    debug: bool = Field(False, description="디버그 모드")
    environment: str = Field("development", description="환경")
    
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
```

### 2. 환경별 설정

```python
# config/development.py
from .settings import Settings


class DevelopmentSettings(Settings):
    """개발 환경 설정"""
    
    debug: bool = True
    environment: str = "development"
    
    class Config:
        env_file = ".env.development"


# config/production.py
from .settings import Settings


class ProductionSettings(Settings):
    """프로덕션 환경 설정"""
    
    debug: bool = False
    environment: str = "production"
    
    class Config:
        env_file = ".env.production"
```

## 📊 성능 최적화 표준

### 1. 비동기 처리

```python
import asyncio
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession


class UserService:
    """사용자 서비스"""
    
    async def process_users_batch(self, user_ids: List[int]) -> List[User]:
        """사용자 배치 처리 (비동기)"""
        # ✅ 좋은 예 - 비동기 처리
        tasks = [self.get_user_by_id(user_id) for user_id in user_ids]
        users = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        valid_users = [
            user for user in users 
            if not isinstance(user, Exception)
        ]
        
        return valid_users
    
    async def process_users_sequential(self, user_ids: List[int]) -> List[User]:
        """사용자 순차 처리 (비동기)"""
        # ❌ 나쁜 예 - 순차 처리
        users = []
        for user_id in user_ids:
            user = await self.get_user_by_id(user_id)
            if user:
                users.append(user)
        
        return users
```

### 2. 데이터베이스 최적화

```python
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload


class UserRepository:
    """사용자 저장소"""
    
    async def get_users_with_profiles(self) -> List[User]:
        """프로필과 함께 사용자 조회 (N+1 문제 해결)"""
        # ✅ 좋은 예 - eager loading
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.profiles))
        )
        return result.scalars().all()
    
    async def get_user_count_by_status(self) -> dict:
        """상태별 사용자 수 조회 (집계 쿼리)"""
        # ✅ 좋은 예 - 집계 쿼리
        result = await self.db.execute(
            select(
                User.status,
                func.count(User.id).label('count')
            )
            .group_by(User.status)
        )
        
        return {row.status: row.count for row in result}
```

## 📋 체크리스트

### 코드 작성 전

- [ ] 요구사항 명확히 파악
- [ ] 설계 문서 검토
- [ ] 기존 코드 스타일 확인
- [ ] 테스트 케이스 계획

### 코드 작성 중

- [ ] 네이밍 규칙 준수
- [ ] 타입 힌트 추가
- [ ] 적절한 주석 작성
- [ ] 예외 처리 구현
- [ ] 로깅 구현
- [ ] 단위 테스트 작성

### 코드 작성 후

- [ ] 코드 리뷰 요청
- [ ] 통합 테스트 실행
- [ ] 문서 업데이트
- [ ] 성능 검증

## 🛠️ 개발 도구 설정

### 1. Pre-commit 설정

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

### 2. VS Code 설정

```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.sortImports.args": ["--profile", "black"],
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

이 표준을 준수하여 일관성 있고 유지보수가 용이한 Python FastAPI 코드를 작성하시기 바랍니다.
