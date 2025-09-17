"""
에이전트 API 엔드포인트

에이전트 관련 REST API 제공
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.database import get_async_session
from ...config.redis import get_cache_service, CacheService
from ...schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    AgentStatusUpdate,
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
)
from ...schemas.common import PaginationParams, PaginatedResponse
from ...services.agent_service import AgentService

router = APIRouter()


def get_agent_service(
    db: AsyncSession = Depends(get_async_session),
    cache: CacheService = Depends(get_cache_service)
) -> AgentService:
    """에이전트 서비스 의존성"""
    return AgentService(db, cache)


@router.post(
    "/",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="에이전트 생성",
    description="새로운 에이전트를 생성합니다."
)
async def create_agent(
    agent_data: AgentCreate,
    agent_service: AgentService = Depends(get_agent_service)
) -> AgentResponse:
    """에이전트 생성"""
    try:
        agent = await agent_service.create_agent(agent_data)
        return AgentResponse.from_orm(agent)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/",
    response_model=PaginatedResponse[AgentResponse],
    summary="에이전트 목록 조회",
    description="에이전트 목록을 페이징하여 조회합니다."
)
async def get_agents(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, description="상태 필터"),
    agent_type: Optional[str] = Query(None, description="에이전트 타입 필터"),
    agent_service: AgentService = Depends(get_agent_service)
) -> PaginatedResponse[AgentResponse]:
    """에이전트 목록 조회"""
    # 필터 구성
    filters = {}
    if status_filter:
        filters["status"] = status_filter
    if agent_type:
        filters["agent_type"] = agent_type
    
    # 에이전트 목록 조회
    agents = await agent_service.get_all(
        skip=pagination.offset,
        limit=pagination.size,
        filters=filters if filters else None
    )
    
    # 전체 개수 조회
    total = await agent_service.count(filters if filters else None)
    
    # 응답 생성
    agent_responses = [AgentResponse.from_orm(agent) for agent in agents]
    return PaginatedResponse.create(
        items=agent_responses,
        total=total,
        page=pagination.page,
        size=pagination.size
    )


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="에이전트 조회",
    description="특정 에이전트의 상세 정보를 조회합니다."
)
async def get_agent(
    agent_id: int,
    agent_service: AgentService = Depends(get_agent_service)
) -> AgentResponse:
    """에이전트 조회"""
    agent = await agent_service.get_by_id(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"에이전트 ID {agent_id}를 찾을 수 없습니다"
        )
    
    return AgentResponse.from_orm(agent)


@router.put(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="에이전트 수정",
    description="에이전트 정보를 수정합니다."
)
async def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    agent_service: AgentService = Depends(get_agent_service)
) -> AgentResponse:
    """에이전트 수정"""
    try:
        agent = await agent_service.update_agent(agent_id, agent_data)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"에이전트 ID {agent_id}를 찾을 수 없습니다"
            )
        
        return AgentResponse.from_orm(agent)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch(
    "/{agent_id}/status",
    response_model=AgentResponse,
    summary="에이전트 상태 수정",
    description="에이전트의 상태를 수정합니다."
)
async def update_agent_status(
    agent_id: int,
    status_data: AgentStatusUpdate,
    agent_service: AgentService = Depends(get_agent_service)
) -> AgentResponse:
    """에이전트 상태 수정"""
    agent = await agent_service.update_status(agent_id, status_data)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"에이전트 ID {agent_id}를 찾을 수 없습니다"
        )
    
    return AgentResponse.from_orm(agent)


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="에이전트 삭제",
    description="에이전트를 삭제합니다."
)
async def delete_agent(
    agent_id: int,
    agent_service: AgentService = Depends(get_agent_service)
):
    """에이전트 삭제"""
    try:
        success = await agent_service.delete_agent(agent_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"에이전트 ID {agent_id}를 찾을 수 없습니다"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/active/list",
    response_model=List[AgentResponse],
    summary="활성 에이전트 목록",
    description="활성 상태인 에이전트 목록을 조회합니다."
)
async def get_active_agents(
    agent_service: AgentService = Depends(get_agent_service)
) -> List[AgentResponse]:
    """활성 에이전트 목록 조회"""
    agents = await agent_service.get_active_agents()
    return [AgentResponse.from_orm(agent) for agent in agents]


@router.get(
    "/available/list",
    response_model=List[AgentResponse],
    summary="사용 가능한 에이전트 목록",
    description="작업을 수락할 수 있는 에이전트 목록을 조회합니다."
)
async def get_available_agents(
    agent_service: AgentService = Depends(get_agent_service)
) -> List[AgentResponse]:
    """사용 가능한 에이전트 목록 조회"""
    agents = await agent_service.get_available_agents()
    return [AgentResponse.from_orm(agent) for agent in agents]


@router.post(
    "/heartbeat",
    response_model=AgentHeartbeatResponse,
    summary="에이전트 하트비트",
    description="에이전트의 하트비트를 업데이트합니다."
)
async def update_heartbeat(
    heartbeat_data: AgentHeartbeatRequest,
    agent_service: AgentService = Depends(get_agent_service)
) -> AgentHeartbeatResponse:
    """에이전트 하트비트 업데이트"""
    agent = await agent_service.update_heartbeat(
        heartbeat_data.agent_id,
        heartbeat_data.dict()
    )
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"에이전트 ID '{heartbeat_data.agent_id}'를 찾을 수 없습니다"
        )
    
    return AgentHeartbeatResponse(
        success=True,
        message="하트비트가 성공적으로 업데이트되었습니다"
    )


@router.get(
    "/statistics/overview",
    response_model=dict,
    summary="에이전트 통계",
    description="에이전트 통계 정보를 조회합니다."
)
async def get_agent_statistics(
    agent_service: AgentService = Depends(get_agent_service)
) -> dict:
    """에이전트 통계 조회"""
    return await agent_service.get_agent_statistics()

