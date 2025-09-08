# AgenticCP Agent API 문서

## 📋 개요

AgenticCP Agent API는 RESTful 설계 원칙을 따르며, JSON 형식으로 데이터를 주고받습니다. 모든 API는 `/api/v1` 프리픽스를 사용합니다.

## 🔗 기본 URL

- **개발 환경**: `http://localhost:8000`
- **프로덕션 환경**: `https://api.agenticcp.com`

## 📝 공통 응답 형식

### 성공 응답

```json
{
  "success": true,
  "message": "요청이 성공적으로 처리되었습니다",
  "data": { ... },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 에러 응답

```json
{
  "code": "ERROR_CODE",
  "message": "에러 메시지",
  "details": ["상세 에러 정보"],
  "timestamp": "2024-01-01T00:00:00Z",
  "path": "/api/v1/endpoint",
  "method": "POST"
}
```

### 페이징 응답

```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "size": 20,
  "pages": 5,
  "has_next": true,
  "has_prev": false
}
```

## 🔐 인증

API는 JWT(JSON Web Token) 기반 인증을 사용합니다.

### 헤더

```http
Authorization: Bearer <jwt_token>
```

### 토큰 갱신

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "your_refresh_token"
}
```

## 📊 에이전트 API

### 에이전트 생성

```http
POST /api/v1/agents
Content-Type: application/json

{
  "agent_id": "agent-001",
  "name": "데이터 처리 에이전트",
  "description": "대용량 데이터 처리 전용 에이전트",
  "agent_type": "data_processing",
  "max_concurrent_tasks": 5,
  "task_timeout_seconds": 600,
  "host": "192.168.1.100",
  "port": 8080,
  "endpoint": "/api/v1/process"
}
```

**응답:**
```json
{
  "id": 1,
  "agent_id": "agent-001",
  "name": "데이터 처리 에이전트",
  "status": "ACTIVE",
  "is_enabled": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### 에이전트 목록 조회

```http
GET /api/v1/agents?page=1&size=20&status=ACTIVE&agent_type=data_processing
```

**쿼리 파라미터:**
- `page`: 페이지 번호 (기본값: 1)
- `size`: 페이지 크기 (기본값: 20, 최대: 100)
- `status`: 상태 필터 (ACTIVE, INACTIVE, MAINTENANCE, ERROR)
- `agent_type`: 에이전트 타입 필터

### 에이전트 조회

```http
GET /api/v1/agents/1
```

### 에이전트 수정

```http
PUT /api/v1/agents/1
Content-Type: application/json

{
  "name": "업데이트된 에이전트 이름",
  "max_concurrent_tasks": 10
}
```

### 에이전트 상태 수정

```http
PATCH /api/v1/agents/1/status
Content-Type: application/json

{
  "status": "MAINTENANCE",
  "is_enabled": false
}
```

### 에이전트 삭제

```http
DELETE /api/v1/agents/1
```

### 하트비트 업데이트

```http
POST /api/v1/agents/heartbeat
Content-Type: application/json

{
  "agent_id": "agent-001",
  "status": "ACTIVE",
  "current_tasks": 3,
  "system_info": {
    "cpu_usage": 45.2,
    "memory_usage": 67.8,
    "disk_usage": 23.1
  }
}
```

## 🎯 작업 API

### 작업 생성

```http
POST /api/v1/tasks
Content-Type: application/json

{
  "task_id": "task-001",
  "name": "데이터 분석 작업",
  "description": "고객 데이터 분석 및 리포트 생성",
  "task_type": "DATA_PROCESSING",
  "priority": 7,
  "input_data": {
    "dataset_id": "dataset-123",
    "analysis_type": "customer_segmentation",
    "output_format": "pdf"
  },
  "timeout_seconds": 1800,
  "agent_id": 1
}
```

### 작업 목록 조회

```http
GET /api/v1/tasks?page=1&size=20&status=RUNNING&task_type=DATA_PROCESSING&agent_id=1
```

**쿼리 파라미터:**
- `page`: 페이지 번호
- `size`: 페이지 크기
- `status`: 상태 필터 (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED, TIMEOUT)
- `task_type`: 작업 타입 필터
- `agent_id`: 에이전트 ID 필터

### 작업 조회

```http
GET /api/v1/tasks/task-001
```

### 작업 실행

```http
POST /api/v1/tasks/execute
Content-Type: application/json

{
  "task_id": "task-001",
  "agent_id": 1
}
```

**자동 할당 (agent_id 생략):**
```http
POST /api/v1/tasks/execute
Content-Type: application/json

{
  "task_id": "task-001"
}
```

### 작업 상태 수정

```http
PATCH /api/v1/tasks/task-001/status
Content-Type: application/json

{
  "status": "COMPLETED",
  "progress": 100,
  "output_data": {
    "result_file": "analysis_report.pdf",
    "summary": "분석 완료",
    "metrics": {
      "accuracy": 0.95,
      "processing_time": 1200
    }
  }
}
```

### 작업 진행률 업데이트

```http
POST /api/v1/tasks/task-001/progress
Content-Type: application/json

{
  "task_id": "task-001",
  "progress": 75,
  "message": "데이터 분석 진행 중...",
  "output_data": {
    "processed_records": 75000,
    "total_records": 100000
  }
}
```

### 작업 취소

```http
POST /api/v1/tasks/task-001/cancel
```

### 작업 재시도

```http
POST /api/v1/tasks/task-001/retry
```

## 🏥 헬스체크 API

### 전체 헬스체크

```http
GET /api/v1/health
```

**응답:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "0.1.0",
  "environment": "production",
  "uptime_seconds": 86400,
  "dependencies": {
    "database": {
      "status": "healthy",
      "message": "데이터베이스 연결 정상"
    },
    "redis": {
      "status": "healthy",
      "message": "Redis 연결 정상"
    },
    "external_services": {
      "status": "healthy",
      "message": "외부 서비스 연결 정상"
    }
  },
  "system": {
    "cpu_percent": 25.5,
    "memory_percent": 67.2,
    "disk_percent": 45.8,
    "uptime_seconds": 86400
  }
}
```

### 라이브니스 체크

```http
GET /api/v1/health/liveness
```

### 레디니스 체크

```http
GET /api/v1/health/readiness
```

### 개별 의존성 상태

```http
GET /api/v1/health/database
GET /api/v1/health/redis
GET /api/v1/health/external-services
```

## 📊 통계 API

### 에이전트 통계

```http
GET /api/v1/agents/statistics/overview
```

**응답:**
```json
{
  "total": 10,
  "active": 8,
  "inactive": 2,
  "by_status": {
    "ACTIVE": 8,
    "INACTIVE": 1,
    "MAINTENANCE": 1,
    "ERROR": 0
  }
}
```

### 작업 통계

```http
GET /api/v1/tasks/statistics/overview
```

**응답:**
```json
{
  "total": 150,
  "by_status": {
    "PENDING": 5,
    "RUNNING": 12,
    "COMPLETED": 120,
    "FAILED": 8,
    "CANCELLED": 3,
    "TIMEOUT": 2
  },
  "by_type": {
    "DATA_PROCESSING": 80,
    "API_CALL": 45,
    "FILE_OPERATION": 20,
    "NOTIFICATION": 5
  }
}
```

## 🚨 에러 코드

| 코드 | HTTP 상태 | 설명 |
|------|-----------|------|
| `VALIDATION_ERROR` | 400 | 입력 데이터 검증 실패 |
| `UNAUTHORIZED` | 401 | 인증 실패 |
| `FORBIDDEN` | 403 | 권한 없음 |
| `NOT_FOUND` | 404 | 리소스를 찾을 수 없음 |
| `CONFLICT` | 409 | 리소스 충돌 |
| `INTERNAL_SERVER_ERROR` | 500 | 서버 내부 오류 |
| `SERVICE_UNAVAILABLE` | 503 | 서비스 사용 불가 |

## 📈 Rate Limiting

API는 Rate Limiting을 적용하여 서비스 안정성을 보장합니다.

- **기본 제한**: 분당 1000 요청
- **인증된 사용자**: 분당 5000 요청
- **헤더**: `X-RateLimit-*` 헤더로 제한 정보 제공

## 🔄 Webhook

작업 상태 변경 시 Webhook을 통해 알림을 받을 수 있습니다.

### Webhook 설정

```http
POST /api/v1/webhooks
Content-Type: application/json

{
  "url": "https://your-service.com/webhook",
  "events": ["task.completed", "task.failed"],
  "secret": "your_webhook_secret"
}
```

### Webhook 페이로드

```json
{
  "event": "task.completed",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": {
    "task_id": "task-001",
    "status": "COMPLETED",
    "agent_id": 1,
    "duration_seconds": 1200
  }
}
```

## 📚 SDK 및 예제

### Python SDK 예제

```python
from agenticcp_agent import AgentClient

client = AgentClient(
    base_url="http://localhost:8000",
    api_key="your_api_key"
)

# 에이전트 생성
agent = client.agents.create({
    "agent_id": "my-agent",
    "name": "My Agent",
    "agent_type": "general"
})

# 작업 생성 및 실행
task = client.tasks.create({
    "task_id": "my-task",
    "name": "My Task",
    "task_type": "DATA_PROCESSING"
})

client.tasks.execute(task.task_id)
```

### cURL 예제

```bash
# 에이전트 생성
curl -X POST "http://localhost:8000/api/v1/agents" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -d '{
    "agent_id": "agent-001",
    "name": "Test Agent",
    "agent_type": "general"
  }'

# 작업 목록 조회
curl -X GET "http://localhost:8000/api/v1/tasks?status=RUNNING" \
  -H "Authorization: Bearer your_token"
```
