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
- **Multi-Agent System**: LangGraph 기반 Supervisor Agent와 EC2 Mini Agent 통합
- **자연어 처리**: OpenAI GPT-4o-mini를 활용한 자연어 요청 처리
- **AWS 통합**: EC2 인스턴스 관리 및 AWS 리소스 조작

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

## 🤖 Multi-Agent System

### CLI 도구 사용법

```bash
# CLI 도구 실행
python -m src.cli.multi_agent_cli

# 환경 변수 파일 지정
python -m src.cli.multi_agent_cli --env-file .env

# 특정 Thread ID 사용
python -m src.cli.multi_agent_cli --thread-id user-123
```

### API 엔드포인트

- **요청 처리**: `POST /api/v1/multi-agent/process`
- **비동기 요청**: `POST /api/v1/multi-agent/process-async`
- **대화 기록**: `GET /api/v1/multi-agent/conversation-history/{thread_id}`
- **그래프 상태**: `GET /api/v1/multi-agent/graph-state/{thread_id}`
- **EC2 직접 요청**: `POST /api/v1/multi-agent/ec2/direct`
- **시스템 상태**: `GET /api/v1/multi-agent/health`
- **에이전트 정보**: `GET /api/v1/multi-agent/agents/info`

### 사용 예시

```bash
# EC2 인스턴스 목록 조회
curl -X POST "http://localhost:8000/api/v1/multi-agent/process" \
  -H "Content-Type: application/json" \
  -d '{"user_request": "EC2 인스턴스 목록을 보여줘"}'

# 일반 대화
curl -X POST "http://localhost:8000/api/v1/multi-agent/process" \
  -H "Content-Type: application/json" \
  -d '{"user_request": "안녕하세요"}'
```

## 🤝 기여하기

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## 📄 라이선스

MIT License