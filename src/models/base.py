"""
기본 모델 클래스

공통 필드 및 기능을 제공하는 기본 모델
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func


@as_declarative()
class Base:
    """기본 모델 클래스"""
    
    __name__: str
    
    # 테이블 이름 자동 생성 (클래스명을 snake_case로 변환)
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
    
    # 공통 필드
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, comment="기본 키")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False,
        comment="생성일시"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(),
        nullable=False,
        comment="수정일시"
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="생성자")
    updated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="수정자")
    
    def __repr__(self) -> str:
        """문자열 표현"""
        return f"<{self.__class__.__name__}(id={self.id})>"
    
    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }

