"""
작업 스키마

작업 관련 요청/응답 스키마 정의
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from ..models.task import TaskStatus, TaskType
from .common import PaginatedResponse


class TaskBase(BaseModel):
    """작업 기본 스키마"""
    
    task_id: str = Field(..., min_length=1, max_length=100, description="작업 ID")
    name: str = Field(..., min_length=1, max_length=200, description="작업 이름")
    description: Optional[str] = Field(None, description="작업 설명")
    task_type: TaskType = Field(TaskType.CUSTOM, description="작업 타입")
    priority: int = Field(5, ge=1, le=10, description="우선순위 (1-10)")
    input_data: Optional[Dict[str, Any]] = Field(None, description="입력 데이터")
    timeout_seconds: Optional[int] = Field(None, ge=1, le=3600, description="타임아웃(초)")
    
    @validator('task_id')
    def validate_task_id(cls, v):
        """작업 ID 검증"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('작업 ID는 영문, 숫자, 하이픈, 언더스코어만 사용 가능합니다')
        return v


class TaskCreate(TaskBase):
    """작업 생성 요청 스키마"""
    
    agent_id: Optional[int] = Field(None, description="할당할 에이전트 ID (선택사항)")


class TaskUpdate(BaseModel):
    """작업 수정 요청 스키마"""
    
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="작업 이름")
    description: Optional[str] = Field(None, description="작업 설명")
    task_type: Optional[TaskType] = Field(None, description="작업 타입")
    priority: Optional[int] = Field(None, ge=1, le=10, description="우선순위 (1-10)")
    input_data: Optional[Dict[str, Any]] = Field(None, description="입력 데이터")
    timeout_seconds: Optional[int] = Field(None, ge=1, le=3600, description="타임아웃(초)")


class TaskStatusUpdate(BaseModel):
    """작업 상태 수정 요청 스키마"""
    
    status: TaskStatus = Field(..., description="작업 상태")
    progress: Optional[int] = Field(None, ge=0, le=100, description="진행률 (0-100)")
    output_data: Optional[Dict[str, Any]] = Field(None, description="출력 데이터")
    error_message: Optional[str] = Field(None, description="오류 메시지")


class TaskResponse(TaskBase):
    """작업 응답 스키마"""
    
    id: int = Field(..., description="작업 ID")
    status: TaskStatus = Field(..., description="작업 상태")
    progress: int = Field(..., description="진행률 (0-100)")
    output_data: Optional[Dict[str, Any]] = Field(None, description="출력 데이터")
    error_message: Optional[str] = Field(None, description="오류 메시지")
    started_at: Optional[datetime] = Field(None, description="시작 시간")
    completed_at: Optional[datetime] = Field(None, description="완료 시간")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")
    created_by: Optional[str] = Field(None, description="생성자")
    updated_by: Optional[str] = Field(None, description="수정자")
    
    # 에이전트 정보
    agent_id: Optional[int] = Field(None, description="에이전트 ID")
    agent_name: Optional[str] = Field(None, description="에이전트 이름")
    
    # 계산된 속성
    is_running: bool = Field(..., description="실행 중 여부")
    is_completed: bool = Field(..., description="완료 여부")
    is_successful: bool = Field(..., description="성공 여부")
    duration_seconds: Optional[int] = Field(None, description="실행 시간(초)")
    can_be_cancelled: bool = Field(..., description="취소 가능 여부")
    can_be_retried: bool = Field(..., description="재시도 가능 여부")
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TaskListResponse(PaginatedResponse[TaskResponse]):
    """작업 목록 응답 스키마"""
    pass


class TaskExecutionRequest(BaseModel):
    """작업 실행 요청 스키마"""
    
    task_id: str = Field(..., description="작업 ID")
    agent_id: Optional[int] = Field(None, description="에이전트 ID (자동 할당 시 생략)")


class TaskExecutionResponse(BaseModel):
    """작업 실행 응답 스키마"""
    
    success: bool = Field(..., description="성공 여부")
    message: str = Field(..., description="응답 메시지")
    task_id: str = Field(..., description="작업 ID")
    assigned_agent_id: Optional[int] = Field(None, description="할당된 에이전트 ID")
    estimated_completion_time: Optional[datetime] = Field(None, description="예상 완료 시간")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="응답 시간")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TaskProgressUpdate(BaseModel):
    """작업 진행률 업데이트 요청 스키마"""
    
    task_id: str = Field(..., description="작업 ID")
    progress: int = Field(..., ge=0, le=100, description="진행률 (0-100)")
    message: Optional[str] = Field(None, description="진행 메시지")
    output_data: Optional[Dict[str, Any]] = Field(None, description="중간 출력 데이터")


class TaskProgressResponse(BaseModel):
    """작업 진행률 업데이트 응답 스키마"""
    
    success: bool = Field(..., description="성공 여부")
    message: str = Field(..., description="응답 메시지")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="응답 시간")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

