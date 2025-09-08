# AgenticCP Agent 문서

## 📋 개요

AgenticCP Agent는 Python FastAPI 기반의 에이전트 서비스입니다. 멀티 클라우드 플랫폼에서 다양한 작업을 수행하는 에이전트들을 관리하고 실행하는 역할을 담당합니다.

## 🚀 주요 기능

- **에이전트 관리**: 에이전트의 생성, 수정, 삭제, 상태 관리
- **작업 관리**: 작업의 생성, 실행, 모니터링, 상태 추적
- **자동 할당**: 사용 가능한 에이전트에 작업 자동 할당
- **실시간 모니터링**: 에이전트 및 작업 상태 실시간 추적
- **헬스체크**: 시스템 및 의존성 상태 모니터링
- **RESTful API**: 표준 REST API를 통한 모든 기능 제공

## 🏗️ 아키텍처

### 기술 스택

- **Framework**: FastAPI 0.104+
- **Database**: PostgreSQL 15+ (SQLAlchemy 2.0+)
- **Cache**: Redis 7+
- **Authentication**: JWT
- **Documentation**: OpenAPI/Swagger
- **Testing**: pytest, pytest-asyncio
- **Code Quality**: black, isort, flake8, mypy

### 프로젝트 구조

```
src/
├── api/                    # API 라우터
│   └── v1/                # API v1
│       ├── agents.py      # 에이전트 API
│       ├── tasks.py       # 작업 API
│       └── health.py      # 헬스체크 API
├── config/                # 설정 관리
│   ├── settings.py        # 애플리케이션 설정
│   ├── database.py        # 데이터베이스 설정
│   └── redis.py           # Redis 설정
├── models/                # 데이터 모델
│   ├── base.py           # 기본 모델
│   ├── agent.py          # 에이전트 모델
│   └── task.py           # 작업 모델
├── schemas/               # Pydantic 스키마
│   ├── common.py         # 공통 스키마
│   ├── agent.py          # 에이전트 스키마
│   └── task.py           # 작업 스키마
├── services/              # 비즈니스 로직
│   ├── base_service.py   # 기본 서비스
│   ├── agent_service.py  # 에이전트 서비스
│   ├── task_service.py   # 작업 서비스
│   └── health_service.py # 헬스체크 서비스
└── main.py               # 메인 애플리케이션
```

## 📚 API 문서

### 에이전트 API

- `POST /api/v1/agents` - 에이전트 생성
- `GET /api/v1/agents` - 에이전트 목록 조회
- `GET /api/v1/agents/{id}` - 에이전트 조회
- `PUT /api/v1/agents/{id}` - 에이전트 수정
- `PATCH /api/v1/agents/{id}/status` - 에이전트 상태 수정
- `DELETE /api/v1/agents/{id}` - 에이전트 삭제
- `POST /api/v1/agents/heartbeat` - 하트비트 업데이트

### 작업 API

- `POST /api/v1/tasks` - 작업 생성
- `GET /api/v1/tasks` - 작업 목록 조회
- `GET /api/v1/tasks/{id}` - 작업 조회
- `PUT /api/v1/tasks/{id}` - 작업 수정
- `PATCH /api/v1/tasks/{id}/status` - 작업 상태 수정
- `DELETE /api/v1/tasks/{id}` - 작업 삭제
- `POST /api/v1/tasks/execute` - 작업 실행
- `POST /api/v1/tasks/{id}/cancel` - 작업 취소
- `POST /api/v1/tasks/{id}/retry` - 작업 재시도

### 헬스체크 API

- `GET /api/v1/health` - 전체 헬스체크
- `GET /api/v1/health/liveness` - 라이브니스 체크
- `GET /api/v1/health/readiness` - 레디니스 체크
- `GET /api/v1/health/database` - 데이터베이스 상태
- `GET /api/v1/health/redis` - Redis 상태

## 🔧 설정

### 환경 변수

주요 환경 변수들:

```bash
# 애플리케이션 설정
APP_NAME=AgenticCP Agent
APP_VERSION=0.1.0
DEBUG=false
ENVIRONMENT=development

# 서버 설정
HOST=0.0.0.0
PORT=8000

# 데이터베이스 설정
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/agenticcp_agent

# Redis 설정
REDIS_URL=redis://localhost:6379/0

# JWT 설정
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 데이터베이스 마이그레이션

```bash
# 마이그레이션 생성
alembic revision --autogenerate -m "Initial migration"

# 마이그레이션 실행
alembic upgrade head
```

## 🚀 실행 방법

### 개발 환경

```bash
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

### 프로덕션 환경

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
export ENVIRONMENT=production
export DATABASE_URL=postgresql+asyncpg://...

# 서버 실행
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 🧪 테스트

```bash
# 전체 테스트 실행
pytest

# 커버리지 포함 테스트
pytest --cov=src

# 특정 테스트 실행
pytest tests/test_agents.py

# 통합 테스트 실행
pytest -m integration
```

## 📊 모니터링

### 메트릭

- `GET /metrics` - Prometheus 메트릭 (설정 시)

### 로깅

- **레벨**: INFO, DEBUG, WARNING, ERROR
- **포맷**: JSON (프로덕션), 텍스트 (개발)
- **파일**: `logs/agent.log`

### 헬스체크

- **Liveness**: `GET /api/v1/health/liveness`
- **Readiness**: `GET /api/v1/health/readiness`
- **Full Health**: `GET /api/v1/health`

## 🔒 보안

- JWT 기반 인증
- CORS 설정
- 입력 데이터 검증
- SQL 인젝션 방지
- XSS 방지

## 📈 성능

- 비동기 처리 (async/await)
- 연결 풀링
- Redis 캐싱
- 데이터베이스 인덱싱
- 쿼리 최적화

## 🤝 기여하기

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## 📄 라이선스

MIT License

## 📞 지원

- 이슈 트래커: [GitHub Issues](https://github.com/agenticcp/agenticcp-agent/issues)
- 문서: [API Documentation](http://localhost:8000/docs)
- 이메일: dev@agenticcp.com
