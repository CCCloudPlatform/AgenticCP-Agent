"""
에이전트 서비스

에이전트 관련 비즈니스 로직 처리
"""

from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.redis import CacheService
from ..models.agent import Agent, AgentStatus
from ..schemas.agent import AgentCreate, AgentUpdate, AgentStatusUpdate
from .base_service import BaseService


class AgentService(BaseService[Agent, AgentCreate, AgentUpdate]):
    """에이전트 서비스"""
    
    def __init__(
        self, 
        db_session: AsyncSession,
        cache_service: Optional[CacheService] = None
    ):
        super().__init__(Agent, db_session, cache_service)
    
    async def get_by_agent_id(self, agent_id: str) -> Optional[Agent]:
        """에이전트 ID로 조회"""
        return await self.get_by_field("agent_id", agent_id)
    
    async def get_active_agents(self) -> List[Agent]:
        """활성 에이전트 목록 조회"""
        result = await self.db.execute(
            select(Agent).where(
                and_(
                    Agent.status == AgentStatus.ACTIVE,
                    Agent.is_enabled == True
                )
            )
        )
        return result.scalars().all()
    
    async def get_available_agents(self) -> List[Agent]:
        """사용 가능한 에이전트 목록 조회"""
        result = await self.db.execute(
            select(Agent).where(
                and_(
                    Agent.status == AgentStatus.ACTIVE,
                    Agent.is_enabled == True
                )
            )
        )
        agents = result.scalars().all()
        
        # 현재 작업 수를 고려하여 사용 가능한 에이전트만 반환
        available_agents = []
        for agent in agents:
            if agent.can_accept_task():
                available_agents.append(agent)
        
        return available_agents
    
    async def update_status(
        self, 
        agent_id: int, 
        status_update: AgentStatusUpdate
    ) -> Optional[Agent]:
        """에이전트 상태 업데이트"""
        agent = await self.get_by_id(agent_id)
        if not agent:
            return None
        
        agent.status = status_update.status
        if status_update.is_enabled is not None:
            agent.is_enabled = status_update.is_enabled
        
        await self.db.commit()
        await self.db.refresh(agent)
        
        # 캐시 무효화
        cache_key = self._get_cache_key("agent", agent_id)
        await self._delete_from_cache(cache_key)
        
        return agent
    
    async def update_heartbeat(self, agent_id: str, heartbeat_data: dict) -> Optional[Agent]:
        """하트비트 업데이트"""
        agent = await self.get_by_agent_id(agent_id)
        if not agent:
            return None
        
        # 하트비트 정보 업데이트
        agent.last_heartbeat = heartbeat_data.get("timestamp")
        if "status" in heartbeat_data:
            agent.status = AgentStatus(heartbeat_data["status"])
        
        await self.db.commit()
        await self.db.refresh(agent)
        
        return agent
    
    async def get_agent_statistics(self) -> dict:
        """에이전트 통계 정보 조회"""
        # 전체 에이전트 수
        total_count = await self.count()
        
        # 상태별 에이전트 수
        status_counts = {}
        for status in AgentStatus:
            count = await self.count({"status": status})
            status_counts[status.value] = count
        
        # 활성화된 에이전트 수
        active_count = await self.count({"is_enabled": True})
        
        return {
            "total": total_count,
            "active": active_count,
            "inactive": total_count - active_count,
            "by_status": status_counts
        }
    
    async def create_agent(self, agent_data: AgentCreate) -> Agent:
        """에이전트 생성"""
        # 에이전트 ID 중복 확인
        existing_agent = await self.get_by_agent_id(agent_data.agent_id)
        if existing_agent:
            raise ValueError(f"에이전트 ID '{agent_data.agent_id}'가 이미 존재합니다")
        
        # 에이전트 생성
        agent = await self.create(agent_data)
        
        # 캐시에 저장
        cache_key = self._get_cache_key("agent", agent.id)
        await self._set_to_cache(cache_key, agent.to_dict(), expire=3600)
        
        return agent
    
    async def update_agent(self, agent_id: int, agent_data: AgentUpdate) -> Optional[Agent]:
        """에이전트 수정"""
        agent = await self.get_by_id(agent_id)
        if not agent:
            return None
        
        # 에이전트 ID 변경 시 중복 확인
        if agent_data.agent_id and agent_data.agent_id != agent.agent_id:
            existing_agent = await self.get_by_agent_id(agent_data.agent_id)
            if existing_agent:
                raise ValueError(f"에이전트 ID '{agent_data.agent_id}'가 이미 존재합니다")
        
        # 에이전트 수정
        updated_agent = await self.update(agent, agent_data)
        
        # 캐시 무효화
        cache_key = self._get_cache_key("agent", agent_id)
        await self._delete_from_cache(cache_key)
        
        return updated_agent
    
    async def delete_agent(self, agent_id: int) -> bool:
        """에이전트 삭제"""
        # 실행 중인 작업이 있는지 확인
        from ..models.task import Task, TaskStatus
        result = await self.db.execute(
            select(Task).where(
                and_(
                    Task.agent_id == agent_id,
                    Task.status == TaskStatus.RUNNING
                )
            )
        )
        running_tasks = result.scalars().all()
        
        if running_tasks:
            raise ValueError("실행 중인 작업이 있는 에이전트는 삭제할 수 없습니다")
        
        # 에이전트 삭제
        success = await self.delete(agent_id)
        
        if success:
            # 캐시 무효화
            cache_key = self._get_cache_key("agent", agent_id)
            await self._delete_from_cache(cache_key)
        
        return success

