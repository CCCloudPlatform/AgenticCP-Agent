"""
데이터베이스 설정 및 연결 관리

SQLAlchemy를 활용한 비동기/동기 데이터베이스 연결 관리
"""

from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from .settings import get_settings


class DatabaseManager:
    """데이터베이스 연결 관리자"""
    
    def __init__(self):
        self.settings = get_settings()
        self._async_engine = None
        self._sync_engine = None
        self._async_session_factory = None
        self._sync_session_factory = None
    
    @property
    def async_engine(self):
        """비동기 엔진 반환"""
        if self._async_engine is None:
            self._async_engine = create_async_engine(
                self.settings.database_url,
                echo=self.settings.database.echo,
                pool_size=self.settings.database.pool_size,
                max_overflow=self.settings.database.max_overflow,
                pool_timeout=self.settings.database.pool_timeout,
                pool_recycle=self.settings.database.pool_recycle,
            )
        return self._async_engine
    
    @property
    def sync_engine(self):
        """동기 엔진 반환"""
        if self._sync_engine is None:
            self._sync_engine = create_engine(
                self.settings.database_url_sync,
                echo=self.settings.database.echo,
                pool_size=self.settings.database.pool_size,
                max_overflow=self.settings.database.max_overflow,
                pool_timeout=self.settings.database.pool_timeout,
                pool_recycle=self.settings.database.pool_recycle,
            )
        return self._sync_engine
    
    @property
    def async_session_factory(self):
        """비동기 세션 팩토리 반환"""
        if self._async_session_factory is None:
            self._async_session_factory = async_sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._async_session_factory
    
    @property
    def sync_session_factory(self):
        """동기 세션 팩토리 반환"""
        if self._sync_session_factory is None:
            self._sync_session_factory = sessionmaker(
                bind=self.sync_engine,
                autocommit=False,
                autoflush=False,
            )
        return self._sync_session_factory
    
    async def close(self):
        """데이터베이스 연결 종료"""
        if self._async_engine:
            await self._async_engine.dispose()
        if self._sync_engine:
            self._sync_engine.dispose()


# 전역 데이터베이스 매니저 인스턴스
db_manager = DatabaseManager()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """비동기 데이터베이스 세션 의존성"""
    async with db_manager.async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session() -> Generator[sessionmaker, None, None]:
    """동기 데이터베이스 세션 의존성"""
    session = db_manager.sync_session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
