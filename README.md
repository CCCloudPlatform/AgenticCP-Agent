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

### 🐳 Docker 환경

#### 개발 환경

```bash
# 환경변수 파일 설정
cp env.dev.example .env.dev
# .env.dev 파일을 편집하여 필요한 설정을 변경하세요

# 개발 환경 실행
docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d

# 로그 확인
docker-compose -f docker-compose.dev.yml logs -f agent

# 서비스 중지
docker-compose -f docker-compose.dev.yml down
```

**개발 환경 특징:**
- 🔧 **Hot Reload**: 소스 코드 변경 시 자동 재시작
- 🗄️ **Adminer**: 데이터베이스 관리 도구 (http://localhost:8080)
- 📊 **Debug 로그**: 상세한 디버깅 정보 제공
- 🔄 **볼륨 마운트**: 로컬 소스 코드와 실시간 동기화

#### 프로덕션 환경

```bash
# 환경변수 파일 설정
cp env.prod.example .env.prod
# .env.prod 파일을 편집하여 보안 설정을 변경하세요

# 프로덕션 환경 실행
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 헬스체크 확인
docker-compose -f docker-compose.prod.yml ps

# 로그 확인
docker-compose -f docker-compose.prod.yml logs -f agent
```

**프로덕션 환경 특징:**
- 🚀 **최적화된 빌드**: 멀티스테이지 빌드로 이미지 크기 최소화
- 🔒 **보안 강화**: 프로덕션용 시크릿 키 및 환경 변수
- 📈 **성능 모니터링**: 프로덕션 로그 레벨 및 메트릭 수집
- 🛡️ **헬스체크**: 자동 복구 및 상태 모니터링

#### Docker 서비스 구성

| 서비스 | 포트 | 설명 |
|--------|------|------|
| **agent** | 8000 | AgenticCP Agent 애플리케이션 |
| **postgres** | 5432 | PostgreSQL 데이터베이스 |
| **redis** | 6379 | Redis 캐시 및 세션 저장소 |
| **adminer** | 8080 | 데이터베이스 관리 도구 (개발용) |

#### Docker 명령어 참조

```bash
# 특정 서비스만 실행
docker-compose up postgres redis

# 백그라운드에서 실행
docker-compose up -d

# 로그 실시간 확인
docker-compose logs -f agent

# 서비스 재시작
docker-compose restart agent

# 볼륨 및 네트워크 포함 완전 정리
docker-compose down -v --remove-orphans

# 이미지 재빌드
docker-compose build --no-cache agent
```

#### 기본 Docker Compose (환경변수 기반)

```bash
# 환경변수 파일 설정
cp env.example .env
# .env 파일을 편집하여 필요한 설정을 변경하세요

# 기본 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f agent
```

## 📚 문서

- [API 문서](http://localhost:8000/docs) - Swagger UI
- [개발 표준](docs/PYTHON_FASTAPI_STANDARDS.md)
- [배포 가이드](docs/DEPLOYMENT.md)
- [API 레퍼런스](docs/API.md)
- [환경변수 관리 가이드](docs/ENVIRONMENT_VARIABLES.md) - 환경변수 설정 및 관리

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

## 🚀 배포 가이드

### 환경별 배포

#### 개발 환경 배포

```bash
# 1. 환경변수 설정
cp env.dev.example .env.dev
nano .env.dev  # 필요한 설정 변경

# 2. 개발 환경 실행
docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d

# 3. 서비스 상태 확인
docker-compose -f docker-compose.dev.yml ps
```

#### 프로덕션 환경 배포

```bash
# 1. 환경변수 설정 (보안 중요!)
cp env.prod.example .env.prod
nano .env.prod  # 필수 보안 설정 변경

# 2. 프로덕션 환경 실행
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 3. 헬스체크 확인
curl http://localhost:8000/health

# 4. 서비스 상태 확인
docker-compose -f docker-compose.prod.yml ps
```

### 보안 체크리스트

- [ ] `POSTGRES_PASSWORD` 강력한 비밀번호 설정
- [ ] `SECRET_KEY` 랜덤 문자열로 설정
- [ ] `CORS_ORIGINS` 실제 도메인으로 제한
- [ ] AWS 자격 증명 올바르게 설정
- [ ] `.env.prod` 파일 권한 제한 (`chmod 600`)
- [ ] 프로덕션 환경에서 `DEBUG=false` 설정

### 모니터링

```bash
# 로그 실시간 확인
docker-compose -f docker-compose.prod.yml logs -f

# 특정 서비스 로그 확인
docker-compose -f docker-compose.prod.yml logs -f agent

# 컨테이너 상태 확인
docker-compose -f docker-compose.prod.yml ps

# 리소스 사용량 확인
docker stats
```

### 백업 및 복구

```bash
# 데이터베이스 백업
docker exec agenticcp-agent-postgres-prod pg_dump -U agenticcp_prod agenticcp_agent_prod > backup.sql

# 데이터베이스 복구
docker exec -i agenticcp-agent-postgres-prod psql -U agenticcp_prod agenticcp_agent_prod < backup.sql
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