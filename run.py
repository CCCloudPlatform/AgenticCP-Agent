#!/usr/bin/env python3
"""
로컬 개발 환경 실행 스크립트

프로젝트 루트에서 실행:
    python run.py

또는:
    python -m run
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    import uvicorn
    from src.config.settings import get_settings
    
    settings = get_settings()
    
    print("🚀 AgenticCP Agent 서버 시작 중...")
    print(f"📍 프로젝트 루트: {project_root}")
    print(f"🌐 서버 주소: http://{settings.host}:{settings.port}")
    print(f"📚 API 문서: http://{settings.host}:{settings.port}/docs")
    print()
    
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.logging.level.lower()
    )

