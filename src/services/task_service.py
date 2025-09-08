"""
작업 서비스

작업 관련 비즈니스 로직 처리
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.redis import CacheService
from ..models.task import Task, TaskStatus, TaskType
from ..models.agent import Agent, AgentStatus
from ..schemas.task import TaskCreate, TaskUpdate, TaskStatusUpdate
from .base_service import BaseService


class TaskService(BaseService[Task, TaskCreate, TaskUpdate]):
    """작업 서비스"""
    
    def __init__(
        self, 
        db_session: AsyncSession,
        cache_service: Optional[CacheService] = None
    ):
        super().__init__(Task, db_session, cache_service)
    
    async def get_by_task_id(self, task_id: str) -> Optional[Task]:
        """작업 ID로 조회"""
        return await self.get_by_field("task_id", task_id)
    
    async def get_tasks_by_agent(self, agent_id: int) -> List[Task]:
        """에이전트별 작업 목록 조회"""
        result = await self.db.execute(
            select(Task).where(Task.agent_id == agent_id)
        )
        return result.scalars().all()
    
    async def get_running_tasks(self) -> List[Task]:
        """실행 중인 작업 목록 조회"""
        result = await self.db.execute(
            select(Task).where(Task.status == TaskStatus.RUNNING)
        )
        return result.scalars().all()
    
    async def get_pending_tasks(self) -> List[Task]:
        """대기 중인 작업 목록 조회"""
        result = await self.db.execute(
            select(Task).where(Task.status == TaskStatus.PENDING)
        )
        return result.scalars().all()
    
    async def assign_task_to_agent(self, task_id: str, agent_id: int) -> Optional[Task]:
        """작업을 에이전트에 할당"""
        task = await self.get_by_task_id(task_id)
        if not task:
            return None
        
        # 에이전트 존재 확인
        agent_result = await self.db.execute(select(Agent).where(Agent.id == agent_id))
        agent = agent_result.scalar_one_or_none()
        if not agent:
            raise ValueError(f"에이전트 ID {agent_id}를 찾을 수 없습니다")
        
        # 에이전트가 작업을 수락할 수 있는지 확인
        if not agent.can_accept_task():
            raise ValueError(f"에이전트 {agent.name}이 현재 작업을 수락할 수 없습니다")
        
        # 작업 할당
        task.agent_id = agent_id
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(task)
        
        return task
    
    async def auto_assign_task(self, task_id: str) -> Optional[Task]:
        """작업을 사용 가능한 에이전트에 자동 할당"""
        task = await self.get_by_task_id(task_id)
        if not task:
            return None
        
        # 사용 가능한 에이전트 조회
        available_agents_result = await self.db.execute(
            select(Agent).where(
                and_(
                    Agent.status == AgentStatus.ACTIVE,
                    Agent.is_enabled == True
                )
            )
        )
        available_agents = available_agents_result.scalars().all()
        
        # 작업을 수락할 수 있는 에이전트 찾기
        for agent in available_agents:
            if agent.can_accept_task():
                return await self.assign_task_to_agent(task_id, agent.id)
        
        raise ValueError("사용 가능한 에이전트가 없습니다")
    
    async def update_task_status(
        self, 
        task_id: str, 
        status_update: TaskStatusUpdate
    ) -> Optional[Task]:
        """작업 상태 업데이트"""
        task = await self.get_by_task_id(task_id)
        if not task:
            return None
        
        # 상태 업데이트
        task.status = status_update.status
        if status_update.progress is not None:
            task.progress = status_update.progress
        if status_update.output_data is not None:
            task.output_data = status_update.output_data
        if status_update.error_message is not None:
            task.error_message = status_update.error_message
        
        # 완료 상태인 경우 완료 시간 설정
        if status_update.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            task.completed_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(task)
        
        return task
    
    async def cancel_task(self, task_id: str) -> Optional[Task]:
        """작업 취소"""
        task = await self.get_by_task_id(task_id)
        if not task:
            return None
        
        if not task.can_be_cancelled():
            raise ValueError("취소할 수 없는 작업입니다")
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(task)
        
        return task
    
    async def retry_task(self, task_id: str) -> Optional[Task]:
        """작업 재시도"""
        task = await self.get_by_task_id(task_id)
        if not task:
            return None
        
        if not task.can_be_retried():
            raise ValueError("재시도할 수 없는 작업입니다")
        
        # 작업 상태 초기화
        task.status = TaskStatus.PENDING
        task.progress = 0
        task.started_at = None
        task.completed_at = None
        task.error_message = None
        
        await self.db.commit()
        await self.db.refresh(task)
        
        return task
    
    async def get_task_statistics(self) -> dict:
        """작업 통계 정보 조회"""
        # 전체 작업 수
        total_count = await self.count()
        
        # 상태별 작업 수
        status_counts = {}
        for status in TaskStatus:
            count = await self.count({"status": status})
            status_counts[status.value] = count
        
        # 타입별 작업 수
        type_counts = {}
        for task_type in TaskType:
            count = await self.count({"task_type": task_type})
            type_counts[task_type.value] = count
        
        return {
            "total": total_count,
            "by_status": status_counts,
            "by_type": type_counts
        }
    
    async def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """상태별 작업 목록 조회"""
        result = await self.db.execute(
            select(Task).where(Task.status == status)
        )
        return result.scalars().all()
    
    async def get_tasks_by_type(self, task_type: TaskType) -> List[Task]:
        """타입별 작업 목록 조회"""
        result = await self.db.execute(
            select(Task).where(Task.task_type == task_type)
        )
        return result.scalars().all()
    
    async def create_task(self, task_data: TaskCreate) -> Task:
        """작업 생성"""
        # 작업 ID 중복 확인
        existing_task = await self.get_by_task_id(task_data.task_id)
        if existing_task:
            raise ValueError(f"작업 ID '{task_data.task_id}'가 이미 존재합니다")
        
        # 작업 생성
        task = await self.create(task_data)
        
        # 에이전트가 지정된 경우 자동 할당
        if task_data.agent_id:
            try:
                await self.assign_task_to_agent(task.task_id, task_data.agent_id)
            except ValueError:
                # 할당 실패 시 대기 상태로 유지
                pass
        
        return task
    
    async def update_task(self, task_id: str, task_data: TaskUpdate) -> Optional[Task]:
        """작업 수정"""
        task = await self.get_by_task_id(task_id)
        if not task:
            return None
        
        # 실행 중인 작업은 수정 제한
        if task.status == TaskStatus.RUNNING:
            raise ValueError("실행 중인 작업은 수정할 수 없습니다")
        
        # 작업 수정
        updated_task = await self.update(task, task_data)
        
        return updated_task
    
    async def delete_task(self, task_id: str) -> bool:
        """작업 삭제"""
        task = await self.get_by_task_id(task_id)
        if not task:
            return False
        
        # 실행 중인 작업은 삭제 불가
        if task.status == TaskStatus.RUNNING:
            raise ValueError("실행 중인 작업은 삭제할 수 없습니다")
        
        # 작업 삭제
        await self.db.delete(task)
        await self.db.commit()
        
        return True
