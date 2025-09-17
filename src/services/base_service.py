"""
기본 서비스 클래스

공통 기능을 제공하는 기본 서비스 클래스
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from ..config.redis import CacheService
from ..models.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """기본 서비스 클래스"""
    
    def __init__(
        self, 
        model: Type[ModelType], 
        db_session: AsyncSession,
        cache_service: Optional[CacheService] = None
    ):
        self.model = model
        self.db = db_session
        self.cache = cache_service
    
    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """ID로 조회"""
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()
    
    async def get_by_field(self, field_name: str, value: Any) -> Optional[ModelType]:
        """특정 필드로 조회"""
        field = getattr(self.model, field_name)
        result = await self.db.execute(select(self.model).where(field == value))
        return result.scalar_one_or_none()
    
    async def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """전체 조회 (페이징)"""
        query = select(self.model)
        
        # 필터 적용
        if filters:
            for field_name, value in filters.items():
                if hasattr(self.model, field_name):
                    field = getattr(self.model, field_name)
                    query = query.where(field == value)
        
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """개수 조회"""
        from sqlalchemy import func
        
        query = select(func.count(self.model.id))
        
        # 필터 적용
        if filters:
            for field_name, value in filters.items():
                if hasattr(self.model, field_name):
                    field = getattr(self.model, field_name)
                    query = query.where(field == value)
        
        result = await self.db.execute(query)
        return result.scalar()
    
    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        """생성"""
        obj_data = obj_in.dict() if hasattr(obj_in, 'dict') else obj_in
        db_obj = self.model(**obj_data)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj
    
    async def update(
        self, 
        db_obj: ModelType, 
        obj_in: UpdateSchemaType
    ) -> ModelType:
        """수정"""
        obj_data = obj_in.dict(exclude_unset=True) if hasattr(obj_in, 'dict') else obj_in
        
        for field, value in obj_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj
    
    async def delete(self, id: int) -> bool:
        """삭제"""
        obj = await self.get_by_id(id)
        if obj:
            await self.db.delete(obj)
            await self.db.commit()
            return True
        return False
    
    async def exists(self, id: int) -> bool:
        """존재 여부 확인"""
        obj = await self.get_by_id(id)
        return obj is not None
    
    def _get_cache_key(self, prefix: str, *args) -> str:
        """캐시 키 생성"""
        return f"{prefix}:{':'.join(str(arg) for arg in args)}"
    
    async def _get_from_cache(self, key: str) -> Optional[Any]:
        """캐시에서 조회"""
        if self.cache:
            return await self.cache.get(key)
        return None
    
    async def _set_to_cache(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """캐시에 저장"""
        if self.cache:
            return await self.cache.set(key, value, expire)
        return False
    
    async def _delete_from_cache(self, key: str) -> bool:
        """캐시에서 삭제"""
        if self.cache:
            return await self.cache.delete(key)
        return False

