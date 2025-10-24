"""
작업 모델

에이전트가 수행하는 작업을 관리하는 모델
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Enum as SQLEnum, String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class TaskStatus(str, Enum):
    """작업 상태"""
    PENDING = "PENDING"        # 대기 중
    RUNNING = "RUNNING"        # 실행 중
    COMPLETED = "COMPLETED"    # 완료
    FAILED = "FAILED"          # 실패
    CANCELLED = "CANCELLED"    # 취소됨
    TIMEOUT = "TIMEOUT"        # 타임아웃


class TaskType(str, Enum):
    """작업 타입"""
    DATA_PROCESSING = "DATA_PROCESSING"    # 데이터 처리
    API_CALL = "API_CALL"                  # API 호출
    FILE_OPERATION = "FILE_OPERATION"      # 파일 작업
    NOTIFICATION = "NOTIFICATION"          # 알림
    CUSTOM = "CUSTOM"                      # 사용자 정의


class Task(Base):
    """작업 모델"""
    
    __tablename__ = "tasks"
    
    # 기본 정보
    task_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True, comment="작업 ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="작업 이름")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="작업 설명")
    task_type: Mapped[TaskType] = mapped_column(
        SQLEnum(TaskType), 
        nullable=False, 
        default=TaskType.CUSTOM,
        comment="작업 타입"
    )
    
    # 상태 정보
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus), 
        nullable=False, 
        default=TaskStatus.PENDING,
        comment="작업 상태"
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5, comment="우선순위 (1-10)")
    
    # 입력/출력 데이터
    input_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="입력 데이터 (JSON)")
    output_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="출력 데이터 (JSON)")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="오류 메시지")
    
    # 실행 정보
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="시작 시간")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="완료 시간")
    timeout_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="타임아웃(초)")
    
    # 진행률
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="진행률 (0-100)")
    
    # 관계
    agent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("agents.id"), nullable=True, comment="에이전트 ID")
    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="tasks")
    
    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<Task(id={self.id}, task_id='{self.task_id}', name='{self.name}', status='{self.status}')>"
    
    @property
    def is_running(self) -> bool:
        """실행 중 여부"""
        return self.status == TaskStatus.RUNNING
    
    @property
    def is_completed(self) -> bool:
        """완료 여부"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT]
    
    @property
    def is_successful(self) -> bool:
        """성공 여부"""
        return self.status == TaskStatus.COMPLETED
    
    @property
    def duration_seconds(self) -> Optional[int]:
        """실행 시간(초)"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None
    
    def can_be_cancelled(self) -> bool:
        """취소 가능 여부"""
        return self.status in [TaskStatus.PENDING, TaskStatus.RUNNING]
    
    def can_be_retried(self) -> bool:
        """재시도 가능 여부"""
        return self.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT]

