"""
Redis 설정 및 연결 관리

Redis를 활용한 캐싱 및 세션 관리
"""

import json
from typing import Any, Optional

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from .settings import get_settings


class RedisManager:
    """Redis 연결 관리자"""
    
    def __init__(self):
        self.settings = get_settings()
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
    
    @property
    def pool(self) -> ConnectionPool:
        """연결 풀 반환"""
        if self._pool is None:
            self._pool = ConnectionPool.from_url(
                self.settings.redis.url,
                max_connections=self.settings.redis.max_connections,
                socket_timeout=self.settings.redis.socket_timeout,
                socket_connect_timeout=self.settings.redis.socket_connect_timeout,
            )
        return self._pool
    
    @property
    def client(self) -> redis.Redis:
        """Redis 클라이언트 반환"""
        if self._client is None:
            self._client = redis.Redis(connection_pool=self.pool)
        return self._client
    
    async def close(self):
        """Redis 연결 종료"""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()


# 전역 Redis 매니저 인스턴스
redis_manager = RedisManager()


class CacheService:
    """캐시 서비스"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception:
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[int] = None
    ) -> bool:
        """캐시에 값 저장"""
        try:
            serialized_value = json.dumps(value, default=str)
            return await self.redis.set(key, serialized_value, ex=expire)
        except Exception:
            return False
    
    async def delete(self, key: str) -> bool:
        """캐시에서 값 삭제"""
        try:
            return await self.redis.delete(key) > 0
        except Exception:
            return False
    
    async def exists(self, key: str) -> bool:
        """키 존재 여부 확인"""
        try:
            return await self.redis.exists(key) > 0
        except Exception:
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """키 만료 시간 설정"""
        try:
            return await self.redis.expire(key, seconds)
        except Exception:
            return False
    
    async def ttl(self, key: str) -> int:
        """키의 남은 만료 시간 조회"""
        try:
            return await self.redis.ttl(key)
        except Exception:
            return -1


def get_cache_service() -> CacheService:
    """캐시 서비스 의존성"""
    return CacheService(redis_manager.client)

