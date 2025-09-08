# AgenticCP Agent

Python FastAPI 기반 에이전트 서비스

## 🚀 빠른 시작

### 개발 환경 설정

```bash
# 저장소 클론
git clone https://github.com/agenticcp/agenticcp-agent.git
cd agenticcp-agent

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements-dev.txt

# 환경 변수 설정
cp env.example .env

# 데이터베이스 마이그레이션
alembic upgrade head

# 개발 서버 실행
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker 환경

```bash
# Docker Compose로 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f agent
```

## 📚 문서

- [API 문서](http://localhost:8000/docs) - Swagger UI
- [개발 표준](docs/PYTHON_FASTAPI_STANDARDS.md)
- [배포 가이드](docs/DEPLOYMENT.md)
- [API 레퍼런스](docs/API.md)

## 🏗️ 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │───▶│   PostgreSQL    │    │     Redis       │
│   (Port 8000)   │    │   (Port 5432)   │    │   (Port 6379)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🎯 주요 기능

- **에이전트 관리**: 에이전트의 생성, 수정, 삭제, 상태 관리
- **작업 관리**: 작업의 생성, 실행, 모니터링, 상태 추적
- **자동 할당**: 사용 가능한 에이전트에 작업 자동 할당
- **실시간 모니터링**: 에이전트 및 작업 상태 실시간 추적
- **헬스체크**: 시스템 및 의존성 상태 모니터링

## 🧪 테스트

```bash
# 전체 테스트 실행
pytest

# 커버리지 포함 테스트
pytest --cov=src

# 특정 테스트 실행
pytest tests/test_agents.py
```

## 📊 모니터링

- **헬스체크**: `GET /api/v1/health`
- **메트릭**: `GET /metrics` (설정 시)
- **로그**: `logs/agent.log`

## 🤝 기여하기

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## 📄 라이선스

MIT License