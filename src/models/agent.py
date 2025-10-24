"""
에이전트 모델

에이전트 정보를 관리하는 모델
"""

from enum import Enum
from typing import List, Optional

from sqlalchemy import Enum as SQLEnum, String, Text, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class AgentStatus(str, Enum):
    """에이전트 상태"""
    ACTIVE = "ACTIVE"      # 활성
    INACTIVE = "INACTIVE"  # 비활성
    MAINTENANCE = "MAINTENANCE"  # 유지보수
    ERROR = "ERROR"        # 오류


class Agent(Base):
    """에이전트 모델"""
    
    __tablename__ = "agents"
    
    # 기본 정보
    agent_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True, comment="에이전트 ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="에이전트 이름")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="에이전트 설명")
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False, default="general", comment="에이전트 타입")
    
    # 상태 정보
    status: Mapped[AgentStatus] = mapped_column(
        SQLEnum(AgentStatus), 
        nullable=False, 
        default=AgentStatus.ACTIVE,
        comment="에이전트 상태"
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="활성화 여부")
    
    # 설정 정보
    max_concurrent_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=10, comment="최대 동시 작업 수")
    task_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300, comment="작업 타임아웃(초)")
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="에이전트 설정 (JSON)")
    
    # 연결 정보
    host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="호스트")
    port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="포트")
    endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="엔드포인트")
    
    # 메타데이터
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="에이전트 버전")
    last_heartbeat: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="마지막 하트비트")
    
    # 관계
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="agent", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<Agent(id={self.id}, agent_id='{self.agent_id}', name='{self.name}', status='{self.status}')>"
    
    @property
    def is_active(self) -> bool:
        """활성 상태 여부"""
        return self.status == AgentStatus.ACTIVE and self.is_enabled
    
    @property
    def is_available(self) -> bool:
        """사용 가능 여부"""
        return self.is_active and self.status != AgentStatus.MAINTENANCE
    
    def can_accept_task(self) -> bool:
        """작업 수락 가능 여부"""
        if not self.is_available:
            return False
        
        # 현재 실행 중인 작업 수 확인 (실제 구현에서는 쿼리 필요)
        # current_tasks = len([task for task in self.tasks if task.status == TaskStatus.RUNNING])
        # return current_tasks < self.max_concurrent_tasks
        
        return True  # 임시로 항상 True 반환

