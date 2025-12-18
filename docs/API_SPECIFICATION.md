# AgenticCP Agent API 명세서


### Base URL
```
http://localhost:8000
```


## 엔드포인트 목록

### 1. Multi-Agent System

#### 1.1 채팅 요청
**POST** `/api/v1/multi-agent/chat`

Multi-Agent System과 대화하고 AWS 리소스 관리를 요청합니다.

**Request Body**
```json
{
  "message": "EC2 인스턴스 목록을 조회해주세요",
  "thread_id": "thread-123",
  "stream": false,
  "context": {
    "user_id": "user-123",
    "session_id": "session-456"
  }
}
```

**Request Fields**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| message | string | Yes | 사용자 메시지 (1-1000자) |
| thread_id | string | No | 대화 스레드 ID (기본값: "default") |
| stream | boolean | No | 스트리밍 응답 여부 (기본값: false) |
| context | object | No | 추가 컨텍스트 정보 |

**Response 200 OK**
```json
{
  "success": true,
  "response": "EC2 인스턴스 목록 (2개):\n• i-1234567890abcdef0 (t2.micro) - running - Public IP: 1.2.3.4",
  "agent_used": "ec2",
  "confidence": 0.9,
  "routing_info": {
    "agent_type": "ec2",
    "reasoning": "EC2 관련 키워드가 감지되어 EC2 Agent로 라우팅합니다.",
    "confidence": 0.9,
    "context": {
      "method": "rule_based",
      "keywords_found": true,
      "confidence": 0.9
    }
  },
  "thread_id": "thread-123",
  "timestamp": "2025-10-25T04:46:16.235662",
  "processing_time": 0.54
}
```

**Response Fields**
| Field | Type | Description |
|-------|------|-------------|
| success | boolean | 요청 처리 성공 여부 |
| response | string | 에이전트 응답 메시지 |
| agent_used | string | 사용된 에이전트 (ec2, s3, vpc, general) |
| confidence | float | 신뢰도 점수 (0.0-1.0) |
| routing_info | object | 라우팅 정보 |
| thread_id | string | 대화 스레드 ID |
| timestamp | datetime | 응답 생성 시간 |
| processing_time | float | 처리 시간(초) |

---

#### 1.2 스트리밍 채팅
**POST** `/api/v1/multi-agent/chat/stream`

실시간 스트리밍으로 응답을 받습니다.

**Request Body**
```json
{
  "message": "EC2 인스턴스를 생성해주세요",
  "thread_id": "thread-123",
  "stream": true
}
```

**Response**
```
Content-Type: text/plain
Cache-Control: no-cache
Connection: keep-alive

data: {"success":true,"response":"인스턴스 i-1234567890abcdef0가 생성되었습니다.","agent_used":"ec2",...}
```

---

#### 1.3 대화 기록 조회
**GET** `/api/v1/multi-agent/history/{thread_id}`

특정 스레드의 대화 기록을 조회합니다.

**Path Parameters**
| Parameter | Type | Description |
|-----------|------|-------------|
| thread_id | string | 대화 스레드 ID |

**Response 200 OK**
```json
{
  "thread_id": "thread-123",
  "messages": [
    {
      "role": "user",
      "content": "EC2 인스턴스 목록을 조회해주세요",
      "timestamp": "2025-10-25T04:45:00.000000"
    },
    {
      "role": "assistant",
      "content": "EC2 인스턴스 목록 (2개)...",
      "timestamp": "2025-10-25T04:46:16.235662"
    }
  ],
  "total_count": 2
}
```

**Response Fields**
| Field | Type | Description |
|-------|------|-------------|
| thread_id | string | 대화 스레드 ID |
| messages | array | 대화 메시지 목록 |
| total_count | integer | 총 메시지 수 |

---

#### 1.4 대화 기록 삭제
**DELETE** `/api/v1/multi-agent/history/{thread_id}`

특정 스레드의 대화 기록을 삭제합니다.

**Path Parameters**
| Parameter | Type | Description |
|-----------|------|-------------|
| thread_id | string | 대화 스레드 ID |

**Response 200 OK**
```json
{
  "success": true,
  "message": "스레드 'thread-123'의 대화 기록이 삭제되었습니다."
}
```

---

#### 1.5 시스템 상태 조회
**GET** `/api/v1/multi-agent/status`

Multi-Agent System의 상태와 사용 가능한 에이전트를 확인합니다.

**Response 200 OK**
```json
{
  "supervisor_agent": true,
  "ec2_agent": true,
  "available_agents": [
    "supervisor",
    "ec2",
    "s3",
    "vpc",
    "general"
  ],
  "system_health": "healthy"
}
```

**Response Fields**
| Field | Type | Description |
|-------|------|-------------|
| supervisor_agent | boolean | Supervisor Agent 상태 |
| ec2_agent | boolean | EC2 Agent 상태 |
| available_agents | array | 사용 가능한 에이전트 목록 |
| system_health | string | 시스템 상태 (healthy, initializing, error) |

---

#### 1.6 시스템 초기화
**POST** `/api/v1/multi-agent/initialize`

Multi-Agent System을 수동으로 초기화합니다.

**Response 200 OK**
```json
{
  "success": true,
  "message": "Multi-Agent System이 성공적으로 초기화되었습니다."
}
```

---

#### 1.7 사용 가능한 에이전트 목록
**GET** `/api/v1/multi-agent/agents`

사용 가능한 에이전트들의 목록과 설명을 반환합니다.

**Response 200 OK**
```json
{
  "agents": [
    {
      "name": "supervisor",
      "description": "사용자 요청을 분석하고 적절한 Mini Agent로 라우팅하는 Supervisor Agent",
      "capabilities": [
        "요청 분석",
        "에이전트 라우팅",
        "대화 관리",
        "상태 추적"
      ]
    },
    {
      "name": "ec2",
      "description": "AWS EC2 인스턴스 관리 및 조작을 담당하는 EC2 Mini Agent",
      "capabilities": [
        "EC2 인스턴스 생성",
        "인스턴스 목록 조회",
        "인스턴스 상태 확인",
        "AWS 리소스 관리"
      ]
    },
    {
      "name": "s3",
      "description": "AWS S3 버킷 및 객체 관리 및 조작을 담당하는 S3 Mini Agent",
      "capabilities": [
        "S3 버킷 생성",
        "버킷 목록 조회",
        "객체 업로드/다운로드",
        "버킷 정책 관리"
      ]
    },
    {
      "name": "vpc",
      "description": "AWS VPC, 서브넷, 보안 그룹 관리 및 조작을 담당하는 VPC Mini Agent",
      "capabilities": [
        "VPC 생성",
        "서브넷 관리",
        "보안 그룹 관리",
        "네트워크 설정"
      ]
    },
    {
      "name": "general",
      "description": "일반적인 대화 및 질문을 처리하는 General Agent",
      "capabilities": [
        "일반 대화",
        "정보 제공",
        "질문 답변",
        "도움말 제공"
      ]
    }
  ],
  "total_count": 5
}
```

---

### 2. Health Check

#### 2.1 헬스 체크
**GET** `/api/v1/health`

서비스의 전체적인 상태를 확인합니다.

**Response 200 OK**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "timestamp": "2025-10-25T04:46:16.235662"
}
```

---

#### 2.2 Liveness Check
**GET** `/api/v1/health/liveness`

서비스가 살아있는지 확인합니다.

**Response 200 OK**
```json
{
  "status": "alive",
  "timestamp": "2025-10-25T04:46:16.235662"
}
```

---

#### 2.3 Redis Health Check
**GET** `/api/v1/health/redis`

Redis 연결 상태를 확인합니다.

**Response 200 OK**
```json
{
  "status": "connected",
  "ping": "pong",
  "timestamp": "2025-10-25T04:46:16.235662"
}
```

---

#### 2.4 External Services Health Check
**GET** `/api/v1/health/external`

외부 서비스(AWS 등) 연결 상태를 확인합니다.

**Response 200 OK**
```json
{
  "aws": "connected",
  "bedrock": "available",
  "timestamp": "2025-10-25T04:46:16.235662"
}
```

---

### 3. Root

#### 3.1 루트 엔드포인트
**GET** `/`

API의 기본 정보와 엔드포인트 목록을 반환합니다.

**Response 200 OK**
```json
{
  "message": "AgenticCP Agent API",
  "version": "1.0.0",
  "environment": "development",
  "docs_url": "/docs",
  "features": {
    "multi_agent_system": true,
    "langgraph_integration": true,
    "supervisor_agent": true,
    "ec2_agent": true,
    "conversation_management": true,
    "streaming_support": true
  },
  "api_endpoints": {
    "multi_agent_chat": "/api/v1/multi-agent/chat",
    "multi_agent_status": "/api/v1/multi-agent/status",
    "multi_agent_history": "/api/v1/multi-agent/history/{thread_id}",
    "available_agents": "/api/v1/multi-agent/agents"
  }
}
```

---

## 요청 예시

### EC2 인스턴스 목록 조회
```bash
curl -X POST http://localhost:8000/api/v1/multi-agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "EC2 인스턴스 목록을 조회해주세요",
    "thread_id": "ec2-list-001"
  }'
```

### EC2 인스턴스 생성
```bash
curl -X POST http://localhost:8000/api/v1/multi-agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "EC2 서버를 생성해주세요",
    "thread_id": "ec2-create-001"
  }'
```

### EC2 인스턴스 삭제
```bash
curl -X POST http://localhost:8000/api/v1/multi-agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "EC2 Instance Created by Agent로 되어있는 Name의 Instance를 지워줘",
    "thread_id": "ec2-delete-001"
  }'
```

### 대화 기록 조회
```bash
curl -X GET http://localhost:8000/api/v1/multi-agent/history/ec2-list-001
```

### 시스템 상태 확인
```bash
curl -X GET http://localhost:8000/api/v1/multi-agent/status
```

---

## 에러 응답

### 400 Bad Request
```json
{
  "code": "VALIDATION_ERROR",
  "message": "메시지가 비어있습니다.",
  "path": "/api/v1/multi-agent/chat",
  "method": "POST"
}
```

### 500 Internal Server Error
```json
{
  "code": "INTERNAL_SERVER_ERROR",
  "message": "서버 내부 오류가 발생했습니다",
  "path": "/api/v1/multi-agent/chat",
  "method": "POST"
}
```

---

## 지원되는 EC2 액션

### 1. 목록 조회
**키워드**: `목록`, `리스트`, `조회`, `보여`, `list`, `show`
```json
{
  "message": "EC2 인스턴스 목록을 조회해주세요"
}
```

### 2. 인스턴스 생성
**키워드**: `생성`, `만들`, `create`, `launch`
```json
{
  "message": "EC2 서버를 생성해주세요"
}
```

### 3. 인스턴스 삭제
**키워드**: `삭제`, `지워`, `종료`, `terminate`, `delete`, `remove`
```json
{
  "message": "EC2 인스턴스를 지워줘"
}
```

### 4. 인스턴스 중지
**키워드**: `중지`, `정지`, `stop`, `shutdown`
```json
{
  "message": "EC2 인스턴스를 중지해줘"
}
```

---

## 참고사항

### LLM Provider 설정
- **Bedrock**: 기본값으로 Claude 3 Haiku 사용
- **OpenAI**: GPT-4o-mini 사용

### AWS 자격 증명
프로덕션 환경에서는 환경 변수를 통해 AWS 자격 증명을 설정해야 합니다.

### 스레드 관리
- 각 스레드는 독립적인 대화 컨텍스트를 유지합니다
- 스레드 ID를 사용하여 대화 기록을 관리합니다

### 신뢰도 점수
- **0.9 이상**: 높은 신뢰도, 정확한 라우팅
- **0.7-0.9**: 중간 신뢰도, 일반적인 라우팅
- **0.7 미만**: 낮은 신뢰도, General Agent로 라우팅

---

## API 문서

프로덕션 환경에서는 `/docs` 엔드포인트를 통해 상호작용 가능한 API 문서를 제공합니다.

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

