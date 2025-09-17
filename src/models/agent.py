"""
에이전트 모델

에이전트 정보를 관리하는 모델
"""

from enum import Enum
from typing import List, Optional

from sqlalchemy import Column, Enum as SQLEnum, String, Text, Boolean, Integer
from sqlalchemy.orm import relationship

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
    agent_id = Column(String(100), unique=True, nullable=False, index=True, comment="에이전트 ID")
    name = Column(String(200), nullable=False, comment="에이전트 이름")
    description = Column(Text, nullable=True, comment="에이전트 설명")
    agent_type = Column(String(50), nullable=False, default="general", comment="에이전트 타입")
    
    # 상태 정보
    status = Column(
        SQLEnum(AgentStatus), 
        nullable=False, 
        default=AgentStatus.ACTIVE,
        comment="에이전트 상태"
    )
    is_enabled = Column(Boolean, nullable=False, default=True, comment="활성화 여부")
    
    # 설정 정보
    max_concurrent_tasks = Column(Integer, nullable=False, default=10, comment="최대 동시 작업 수")
    task_timeout_seconds = Column(Integer, nullable=False, default=300, comment="작업 타임아웃(초)")
    config = Column(Text, nullable=True, comment="에이전트 설정 (JSON)")
    
    # 연결 정보
    host = Column(String(255), nullable=True, comment="호스트")
    port = Column(Integer, nullable=True, comment="포트")
    endpoint = Column(String(500), nullable=True, comment="엔드포인트")
    
    # 메타데이터
    version = Column(String(50), nullable=True, comment="에이전트 버전")
    last_heartbeat = Column(String(50), nullable=True, comment="마지막 하트비트")
    
    # 관계
    tasks = relationship("Task", back_populates="agent", cascade="all, delete-orphan")
    
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

