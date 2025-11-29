#!/bin/bash
# 로컬 개발 환경 실행 스크립트 (WSL/Linux/Mac)

# 프로젝트 루트로 이동
cd "$(dirname "$0")"

# 가상환경 활성화 (있는 경우)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# uvicorn으로 서버 실행
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

