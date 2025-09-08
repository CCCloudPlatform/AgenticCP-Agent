"""
에이전트 스키마

에이전트 관련 요청/응답 스키마 정의
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator

from ..models.agent import AgentStatus
from .common import PaginatedResponse


class AgentBase(BaseModel):
    """에이전트 기본 스키마"""
    
    agent_id: str = Field(..., min_length=1, max_length=100, description="에이전트 ID")
    name: str = Field(..., min_length=1, max_length=200, description="에이전트 이름")
    description: Optional[str] = Field(None, description="에이전트 설명")
    agent_type: str = Field("general", max_length=50, description="에이전트 타입")
    max_concurrent_tasks: int = Field(10, ge=1, le=100, description="최대 동시 작업 수")
    task_timeout_seconds: int = Field(300, ge=1, le=3600, description="작업 타임아웃(초)")
    config: Optional[str] = Field(None, description="에이전트 설정 (JSON)")
    host: Optional[str] = Field(None, max_length=255, description="호스트")
    port: Optional[int] = Field(None, ge=1, le=65535, description="포트")
    endpoint: Optional[str] = Field(None, max_length=500, description="엔드포인트")
    version: Optional[str] = Field(None, max_length=50, description="에이전트 버전")
    
    @validator('agent_id')
    def validate_agent_id(cls, v):
        """에이전트 ID 검증"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('에이전트 ID는 영문, 숫자, 하이픈, 언더스코어만 사용 가능합니다')
        return v


class AgentCreate(AgentBase):
    """에이전트 생성 요청 스키마"""
    pass


class AgentUpdate(BaseModel):
    """에이전트 수정 요청 스키마"""
    
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="에이전트 이름")
    description: Optional[str] = Field(None, description="에이전트 설명")
    agent_type: Optional[str] = Field(None, max_length=50, description="에이전트 타입")
    max_concurrent_tasks: Optional[int] = Field(None, ge=1, le=100, description="최대 동시 작업 수")
    task_timeout_seconds: Optional[int] = Field(None, ge=1, le=3600, description="작업 타임아웃(초)")
    config: Optional[str] = Field(None, description="에이전트 설정 (JSON)")
    host: Optional[str] = Field(None, max_length=255, description="호스트")
    port: Optional[int] = Field(None, ge=1, le=65535, description="포트")
    endpoint: Optional[str] = Field(None, max_length=500, description="엔드포인트")
    version: Optional[str] = Field(None, max_length=50, description="에이전트 버전")


class AgentStatusUpdate(BaseModel):
    """에이전트 상태 수정 요청 스키마"""
    
    status: AgentStatus = Field(..., description="에이전트 상태")
    is_enabled: Optional[bool] = Field(None, description="활성화 여부")


class AgentResponse(AgentBase):
    """에이전트 응답 스키마"""
    
    id: int = Field(..., description="에이전트 ID")
    status: AgentStatus = Field(..., description="에이전트 상태")
    is_enabled: bool = Field(..., description="활성화 여부")
    last_heartbeat: Optional[str] = Field(None, description="마지막 하트비트")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")
    created_by: Optional[str] = Field(None, description="생성자")
    updated_by: Optional[str] = Field(None, description="수정자")
    
    # 계산된 속성
    is_active: bool = Field(..., description="활성 상태 여부")
    is_available: bool = Field(..., description="사용 가능 여부")
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AgentListResponse(PaginatedResponse[AgentResponse]):
    """에이전트 목록 응답 스키마"""
    pass


class AgentHeartbeatRequest(BaseModel):
    """에이전트 하트비트 요청 스키마"""
    
    agent_id: str = Field(..., description="에이전트 ID")
    status: AgentStatus = Field(..., description="현재 상태")
    current_tasks: int = Field(0, ge=0, description="현재 실행 중인 작업 수")
    system_info: Optional[dict] = Field(None, description="시스템 정보")


class AgentHeartbeatResponse(BaseModel):
    """에이전트 하트비트 응답 스키마"""
    
    success: bool = Field(..., description="성공 여부")
    message: str = Field(..., description="응답 메시지")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="응답 시간")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
