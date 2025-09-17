"""
작업 API 엔드포인트

작업 관련 REST API 제공
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.database import get_async_session
from ...config.redis import get_cache_service, CacheService
from ...schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskListResponse,
    TaskStatusUpdate,
    TaskExecutionRequest,
    TaskExecutionResponse,
    TaskProgressUpdate,
    TaskProgressResponse,
)
from ...schemas.common import PaginationParams, PaginatedResponse
from ...services.task_service import TaskService

router = APIRouter()


def get_task_service(
    db: AsyncSession = Depends(get_async_session),
    cache: CacheService = Depends(get_cache_service)
) -> TaskService:
    """작업 서비스 의존성"""
    return TaskService(db, cache)


@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="작업 생성",
    description="새로운 작업을 생성합니다."
)
async def create_task(
    task_data: TaskCreate,
    task_service: TaskService = Depends(get_task_service)
) -> TaskResponse:
    """작업 생성"""
    try:
        task = await task_service.create_task(task_data)
        return TaskResponse.from_orm(task)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/",
    response_model=PaginatedResponse[TaskResponse],
    summary="작업 목록 조회",
    description="작업 목록을 페이징하여 조회합니다."
)
async def get_tasks(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, description="상태 필터"),
    task_type: Optional[str] = Query(None, description="작업 타입 필터"),
    agent_id: Optional[int] = Query(None, description="에이전트 ID 필터"),
    task_service: TaskService = Depends(get_task_service)
) -> PaginatedResponse[TaskResponse]:
    """작업 목록 조회"""
    # 필터 구성
    filters = {}
    if status_filter:
        filters["status"] = status_filter
    if task_type:
        filters["task_type"] = task_type
    if agent_id:
        filters["agent_id"] = agent_id
    
    # 작업 목록 조회
    tasks = await task_service.get_all(
        skip=pagination.offset,
        limit=pagination.size,
        filters=filters if filters else None
    )
    
    # 전체 개수 조회
    total = await task_service.count(filters if filters else None)
    
    # 응답 생성
    task_responses = [TaskResponse.from_orm(task) for task in tasks]
    return PaginatedResponse.create(
        items=task_responses,
        total=total,
        page=pagination.page,
        size=pagination.size
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="작업 조회",
    description="특정 작업의 상세 정보를 조회합니다."
)
async def get_task(
    task_id: str,
    task_service: TaskService = Depends(get_task_service)
) -> TaskResponse:
    """작업 조회"""
    task = await task_service.get_by_task_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"작업 ID '{task_id}'를 찾을 수 없습니다"
        )
    
    return TaskResponse.from_orm(task)


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    summary="작업 수정",
    description="작업 정보를 수정합니다."
)
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    task_service: TaskService = Depends(get_task_service)
) -> TaskResponse:
    """작업 수정"""
    try:
        task = await task_service.update_task(task_id, task_data)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"작업 ID '{task_id}'를 찾을 수 없습니다"
            )
        
        return TaskResponse.from_orm(task)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch(
    "/{task_id}/status",
    response_model=TaskResponse,
    summary="작업 상태 수정",
    description="작업의 상태를 수정합니다."
)
async def update_task_status(
    task_id: str,
    status_data: TaskStatusUpdate,
    task_service: TaskService = Depends(get_task_service)
) -> TaskResponse:
    """작업 상태 수정"""
    task = await task_service.update_task_status(task_id, status_data)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"작업 ID '{task_id}'를 찾을 수 없습니다"
        )
    
    return TaskResponse.from_orm(task)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="작업 삭제",
    description="작업을 삭제합니다."
)
async def delete_task(
    task_id: str,
    task_service: TaskService = Depends(get_task_service)
):
    """작업 삭제"""
    try:
        success = await task_service.delete_task(task_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"작업 ID '{task_id}'를 찾을 수 없습니다"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/execute",
    response_model=TaskExecutionResponse,
    summary="작업 실행",
    description="작업을 실행합니다."
)
async def execute_task(
    execution_request: TaskExecutionRequest,
    task_service: TaskService = Depends(get_task_service)
) -> TaskExecutionResponse:
    """작업 실행"""
    try:
        if execution_request.agent_id:
            # 특정 에이전트에 할당
            task = await task_service.assign_task_to_agent(
                execution_request.task_id,
                execution_request.agent_id
            )
            assigned_agent_id = execution_request.agent_id
        else:
            # 자동 할당
            task = await task_service.auto_assign_task(execution_request.task_id)
            assigned_agent_id = task.agent_id if task else None
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"작업 ID '{execution_request.task_id}'를 찾을 수 없습니다"
            )
        
        return TaskExecutionResponse(
            success=True,
            message="작업이 성공적으로 실행되었습니다",
            task_id=execution_request.task_id,
            assigned_agent_id=assigned_agent_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/{task_id}/cancel",
    response_model=TaskResponse,
    summary="작업 취소",
    description="실행 중인 작업을 취소합니다."
)
async def cancel_task(
    task_id: str,
    task_service: TaskService = Depends(get_task_service)
) -> TaskResponse:
    """작업 취소"""
    try:
        task = await task_service.cancel_task(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"작업 ID '{task_id}'를 찾을 수 없습니다"
            )
        
        return TaskResponse.from_orm(task)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/{task_id}/retry",
    response_model=TaskResponse,
    summary="작업 재시도",
    description="실패한 작업을 재시도합니다."
)
async def retry_task(
    task_id: str,
    task_service: TaskService = Depends(get_task_service)
) -> TaskResponse:
    """작업 재시도"""
    try:
        task = await task_service.retry_task(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"작업 ID '{task_id}'를 찾을 수 없습니다"
            )
        
        return TaskResponse.from_orm(task)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/{task_id}/progress",
    response_model=TaskProgressResponse,
    summary="작업 진행률 업데이트",
    description="작업의 진행률을 업데이트합니다."
)
async def update_task_progress(
    task_id: str,
    progress_data: TaskProgressUpdate,
    task_service: TaskService = Depends(get_task_service)
) -> TaskProgressResponse:
    """작업 진행률 업데이트"""
    try:
        status_update = TaskStatusUpdate(
            progress=progress_data.progress,
            output_data=progress_data.output_data
        )
        
        task = await task_service.update_task_status(task_id, status_update)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"작업 ID '{task_id}'를 찾을 수 없습니다"
            )
        
        return TaskProgressResponse(
            success=True,
            message="작업 진행률이 성공적으로 업데이트되었습니다"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/running/list",
    response_model=List[TaskResponse],
    summary="실행 중인 작업 목록",
    description="현재 실행 중인 작업 목록을 조회합니다."
)
async def get_running_tasks(
    task_service: TaskService = Depends(get_task_service)
) -> List[TaskResponse]:
    """실행 중인 작업 목록 조회"""
    tasks = await task_service.get_running_tasks()
    return [TaskResponse.from_orm(task) for task in tasks]


@router.get(
    "/pending/list",
    response_model=List[TaskResponse],
    summary="대기 중인 작업 목록",
    description="대기 중인 작업 목록을 조회합니다."
)
async def get_pending_tasks(
    task_service: TaskService = Depends(get_task_service)
) -> List[TaskResponse]:
    """대기 중인 작업 목록 조회"""
    tasks = await task_service.get_pending_tasks()
    return [TaskResponse.from_orm(task) for task in tasks]


@router.get(
    "/statistics/overview",
    response_model=dict,
    summary="작업 통계",
    description="작업 통계 정보를 조회합니다."
)
async def get_task_statistics(
    task_service: TaskService = Depends(get_task_service)
) -> dict:
    """작업 통계 조회"""
    return await task_service.get_task_statistics()

