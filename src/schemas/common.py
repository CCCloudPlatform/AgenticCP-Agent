"""
공통 스키마

API 요청/응답에 사용되는 공통 스키마 정의
"""

from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar('T')


class ErrorResponse(BaseModel):
    """에러 응답 스키마"""
    
    code: str = Field(..., description="에러 코드")
    message: str = Field(..., description="에러 메시지")
    details: Optional[List[str]] = Field(None, description="상세 에러 정보")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="에러 발생 시간")
    path: Optional[str] = Field(None, description="요청 경로")
    method: Optional[str] = Field(None, description="HTTP 메서드")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SuccessResponse(BaseModel, Generic[T]):
    """성공 응답 스키마"""
    
    success: bool = Field(True, description="성공 여부")
    message: str = Field(..., description="응답 메시지")
    data: Optional[T] = Field(None, description="응답 데이터")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="응답 시간")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PaginationParams(BaseModel):
    """페이징 파라미터"""
    
    page: int = Field(1, ge=1, description="페이지 번호")
    size: int = Field(20, ge=1, le=100, description="페이지 크기")
    sort_by: Optional[str] = Field(None, description="정렬 기준")
    sort_order: str = Field("asc", regex="^(asc|desc)$", description="정렬 순서")
    
    @property
    def offset(self) -> int:
        """오프셋 계산"""
        return (self.page - 1) * self.size


class PaginatedResponse(BaseModel, Generic[T]):
    """페이징된 응답 스키마"""
    
    items: List[T] = Field(..., description="데이터 목록")
    total: int = Field(..., description="전체 개수")
    page: int = Field(..., description="현재 페이지")
    size: int = Field(..., description="페이지 크기")
    pages: int = Field(..., description="전체 페이지 수")
    has_next: bool = Field(..., description="다음 페이지 존재 여부")
    has_prev: bool = Field(..., description="이전 페이지 존재 여부")
    
    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        size: int
    ) -> "PaginatedResponse[T]":
        """페이징된 응답 생성"""
        pages = (total + size - 1) // size
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1
        )


class HealthCheckResponse(BaseModel):
    """헬스체크 응답 스키마"""
    
    status: str = Field(..., description="서비스 상태")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="체크 시간")
    version: str = Field(..., description="서비스 버전")
    environment: str = Field(..., description="환경")
    uptime: Optional[float] = Field(None, description="가동 시간(초)")
    dependencies: Optional[dict] = Field(None, description="의존성 상태")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

