# AgenticCP Agent API 문서

## 개요

AgenticCP Agent는 AWS 리소스 관리를 위한 Multi-Agent System을 제공하는 FastAPI 기반 백엔드 서비스입니다. 프론트엔드와의 통신을 위한 REST API 엔드포인트와 Request/Response 형식을 정의합니다.

## 기본 정보

- **Base URL**: `http://localhost:8000`
- **API Version**: `v1`
- **Content-Type**: `application/json`
- **Authentication**: 현재 미구현 (향후 JWT 토큰 기반 인증 예정)

## API 엔드포인트

### 1. 헬스체크 (Health Check)

#### GET `/api/v1/health`

서비스 상태를 확인합니다.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-25T01:30:00.000Z",
  "version": "0.1.0",
  "environment": "development",
  "uptime": 3600.5,
  "dependencies": {
    "database": "connected",
    "redis": "connected"
  }
}
```

---

### 2. Multi-Agent System

#### POST `/api/v1/multi-agent/chat`

사용자 메시지를 처리하고 적절한 Agent로 라우팅합니다.

**Request:**
```json
{
  "message": "EC2 인스턴스 목록을 조회해주세요",
  "thread_id": "user-session-123",
  "stream": false,
  "context": {
    "user_id": "user-001",
    "session_id": "session-456"
  }
}
```

**Response:**
```json
{
  "success": true,
  "response": "EC2 인스턴스 목록을 조회했습니다. 현재 계정의 EC2 인스턴스 정보를 확인할 수 있습니다.",
  "agent_used": "ec2",
  "confidence": 0.9,
  "routing_info": {
    "intent": "list_instances",
    "confidence": 0.95,
    "processing_time": 1.2
  },
  "thread_id": "user-session-123",
  "timestamp": "2025-10-25T01:30:00.000Z",
  "processing_time": 1.2
}
```

#### GET `/api/v1/multi-agent/status`

Multi-Agent System의 상태를 확인합니다.

**Response:**
```json
{
  "supervisor_agent": true,
  "ec2_agent": true,
  "available_agents": ["supervisor", "ec2", "s3", "vpc"],
  "system_health": "healthy"
}
```

#### GET `/api/v1/multi-agent/history/{thread_id}`

특정 스레드의 대화 기록을 조회합니다.

**Response:**
```json
{
  "thread_id": "user-session-123",
  "messages": [
    {
      "role": "user",
      "content": "EC2 인스턴스 목록을 조회해주세요",
      "timestamp": "2025-10-25T01:30:00.000Z"
    },
    {
      "role": "assistant",
      "content": "EC2 인스턴스 목록을 조회했습니다.",
      "agent_used": "ec2",
      "timestamp": "2025-10-25T01:30:01.200Z"
    }
  ],
  "total_count": 2
}
```

---

### 3. Agent 관리

#### POST `/api/v1/agents/`

새로운 Agent를 생성합니다.

**Request:**
```json
{
  "agent_id": "ec2-agent-001",
  "name": "EC2 Management Agent",
  "description": "EC2 인스턴스 관리 전용 Agent",
  "agent_type": "ec2",
  "max_concurrent_tasks": 5,
  "task_timeout_seconds": 300,
  "config": "{\"region\": \"ap-northeast-2\"}",
  "host": "agent-server-01",
  "port": 8080,
  "endpoint": "/agent/ec2",
  "version": "1.0.0"
}
```

**Response:**
```json
{
  "id": 1,
  "agent_id": "ec2-agent-001",
  "name": "EC2 Management Agent",
  "description": "EC2 인스턴스 관리 전용 Agent",
  "agent_type": "ec2",
  "status": "active",
  "is_enabled": true,
  "is_active": true,
  "is_available": true,
  "max_concurrent_tasks": 5,
  "task_timeout_seconds": 300,
  "config": "{\"region\": \"ap-northeast-2\"}",
  "host": "agent-server-01",
  "port": 8080,
  "endpoint": "/agent/ec2",
  "version": "1.0.0",
  "last_heartbeat": "2025-10-25T01:30:00.000Z",
  "created_at": "2025-10-25T01:30:00.000Z",
  "updated_at": "2025-10-25T01:30:00.000Z",
  "created_by": "system",
  "updated_by": "system"
}
```

#### GET `/api/v1/agents/`

Agent 목록을 조회합니다.

**Query Parameters:**
- `page`: 페이지 번호 (기본값: 1)
- `size`: 페이지 크기 (기본값: 20, 최대: 100)
- `sort_by`: 정렬 기준 (기본값: created_at)
- `sort_order`: 정렬 순서 (asc/desc, 기본값: asc)
- `agent_type`: Agent 타입 필터
- `status`: Agent 상태 필터

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "agent_id": "ec2-agent-001",
      "name": "EC2 Management Agent",
      "agent_type": "ec2",
      "status": "active",
      "is_enabled": true,
      "is_active": true,
      "is_available": true,
      "created_at": "2025-10-25T01:30:00.000Z",
      "updated_at": "2025-10-25T01:30:00.000Z"
    }
  ],
  "total": 1,
  "page": 1,
  "size": 20,
  "pages": 1,
  "has_next": false,
  "has_prev": false
}
```

#### GET `/api/v1/agents/{agent_id}`

특정 Agent의 상세 정보를 조회합니다.

**Response:**
```json
{
  "id": 1,
  "agent_id": "ec2-agent-001",
  "name": "EC2 Management Agent",
  "description": "EC2 인스턴스 관리 전용 Agent",
  "agent_type": "ec2",
  "status": "active",
  "is_enabled": true,
  "is_active": true,
  "is_available": true,
  "max_concurrent_tasks": 5,
  "task_timeout_seconds": 300,
  "config": "{\"region\": \"ap-northeast-2\"}",
  "host": "agent-server-01",
  "port": 8080,
  "endpoint": "/agent/ec2",
  "version": "1.0.0",
  "last_heartbeat": "2025-10-25T01:30:00.000Z",
  "created_at": "2025-10-25T01:30:00.000Z",
  "updated_at": "2025-10-25T01:30:00.000Z",
  "created_by": "system",
  "updated_by": "system"
}
```

#### PUT `/api/v1/agents/{agent_id}`

Agent 정보를 수정합니다.

**Request:**
```json
{
  "name": "Updated EC2 Management Agent",
  "description": "Updated description",
  "max_concurrent_tasks": 10,
  "config": "{\"region\": \"us-east-1\"}"
}
```

#### POST `/api/v1/agents/{agent_id}/heartbeat`

Agent의 하트비트를 전송합니다.

**Request:**
```json
{
  "agent_id": "ec2-agent-001",
  "status": "active",
  "current_tasks": 2,
  "system_info": {
    "cpu_usage": 45.2,
    "memory_usage": 67.8,
    "disk_usage": 23.1
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Heartbeat received successfully",
  "timestamp": "2025-10-25T01:30:00.000Z"
}
```

---

### 4. Task 관리

#### POST `/api/v1/tasks/`

새로운 Task를 생성합니다.

**Request:**
```json
{
  "task_id": "task-001",
  "name": "EC2 Instance Creation",
  "description": "Create new EC2 instance",
  "task_type": "ec2_create",
  "priority": 5,
  "input_data": {
    "instance_type": "t2.micro",
    "ami_id": "ami-0abcdef1234567890",
    "key_name": "my-key"
  },
  "timeout_seconds": 600,
  "agent_id": 1
}
```

**Response:**
```json
{
  "id": 1,
  "task_id": "task-001",
  "name": "EC2 Instance Creation",
  "description": "Create new EC2 instance",
  "task_type": "ec2_create",
  "status": "pending",
  "progress": 0,
  "priority": 5,
  "input_data": {
    "instance_type": "t2.micro",
    "ami_id": "ami-0abcdef1234567890",
    "key_name": "my-key"
  },
  "output_data": null,
  "error_message": null,
  "timeout_seconds": 600,
  "started_at": null,
  "completed_at": null,
  "created_at": "2025-10-25T01:30:00.000Z",
  "updated_at": "2025-10-25T01:30:00.000Z",
  "created_by": "user-001",
  "updated_by": "user-001",
  "agent_id": 1,
  "agent_name": "EC2 Management Agent",
  "is_running": false,
  "is_completed": false,
  "is_successful": false,
  "duration_seconds": null,
  "can_be_cancelled": true,
  "can_be_retried": false
}
```

#### GET `/api/v1/tasks/`

Task 목록을 조회합니다.

**Query Parameters:**
- `page`: 페이지 번호 (기본값: 1)
- `size`: 페이지 크기 (기본값: 20, 최대: 100)
- `sort_by`: 정렬 기준 (기본값: created_at)
- `sort_order`: 정렬 순서 (asc/desc, 기본값: desc)
- `status`: Task 상태 필터
- `task_type`: Task 타입 필터
- `agent_id`: Agent ID 필터

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "task_id": "task-001",
      "name": "EC2 Instance Creation",
      "task_type": "ec2_create",
      "status": "running",
      "progress": 50,
      "priority": 5,
      "agent_id": 1,
      "agent_name": "EC2 Management Agent",
      "is_running": true,
      "is_completed": false,
      "is_successful": false,
      "created_at": "2025-10-25T01:30:00.000Z",
      "updated_at": "2025-10-25T01:30:30.000Z"
    }
  ],
  "total": 1,
  "page": 1,
  "size": 20,
  "pages": 1,
  "has_next": false,
  "has_prev": false
}
```

#### GET `/api/v1/tasks/{task_id}`

특정 Task의 상세 정보를 조회합니다.

**Response:**
```json
{
  "id": 1,
  "task_id": "task-001",
  "name": "EC2 Instance Creation",
  "description": "Create new EC2 instance",
  "task_type": "ec2_create",
  "status": "completed",
  "progress": 100,
  "priority": 5,
  "input_data": {
    "instance_type": "t2.micro",
    "ami_id": "ami-0abcdef1234567890",
    "key_name": "my-key"
  },
  "output_data": {
    "instance_id": "i-1234567890abcdef0",
    "public_ip": "203.0.113.12",
    "private_ip": "10.0.1.100"
  },
  "error_message": null,
  "timeout_seconds": 600,
  "started_at": "2025-10-25T01:30:00.000Z",
  "completed_at": "2025-10-25T01:35:00.000Z",
  "created_at": "2025-10-25T01:30:00.000Z",
  "updated_at": "2025-10-25T01:35:00.000Z",
  "created_by": "user-001",
  "updated_by": "user-001",
  "agent_id": 1,
  "agent_name": "EC2 Management Agent",
  "is_running": false,
  "is_completed": true,
  "is_successful": true,
  "duration_seconds": 300,
  "can_be_cancelled": false,
  "can_be_retried": false
}
```

#### POST `/api/v1/tasks/{task_id}/execute`

Task를 실행합니다.

**Request:**
```json
{
  "task_id": "task-001",
  "agent_id": 1
}
```

**Response:**
```json
{
  "success": true,
  "message": "Task execution started",
  "task_id": "task-001",
  "assigned_agent_id": 1,
  "estimated_completion_time": "2025-10-25T01:35:00.000Z",
  "timestamp": "2025-10-25T01:30:00.000Z"
}
```

#### PUT `/api/v1/tasks/{task_id}/progress`

Task의 진행률을 업데이트합니다.

**Request:**
```json
{
  "task_id": "task-001",
  "progress": 75,
  "message": "Instance is being configured",
  "output_data": {
    "instance_id": "i-1234567890abcdef0",
    "status": "configuring"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Progress updated successfully",
  "timestamp": "2025-10-25T01:32:30.000Z"
}
```

---

## 공통 응답 형식

### 성공 응답
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": { /* 응답 데이터 */ },
  "timestamp": "2025-10-25T01:30:00.000Z"
}
```

### 에러 응답
```json
{
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": [
    "agent_id is required",
    "name must be at least 1 character long"
  ],
  "timestamp": "2025-10-25T01:30:00.000Z",
  "path": "/api/v1/agents/",
  "method": "POST"
}
```

## 상태 코드

### Agent Status
- `active`: 활성 상태
- `inactive`: 비활성 상태
- `maintenance`: 유지보수 중
- `error`: 오류 상태

### Task Status
- `pending`: 대기 중
- `running`: 실행 중
- `completed`: 완료
- `failed`: 실패
- `cancelled`: 취소됨
- `timeout`: 타임아웃

### Task Type
- `custom`: 사용자 정의
- `ec2_create`: EC2 인스턴스 생성
- `ec2_delete`: EC2 인스턴스 삭제
- `s3_upload`: S3 파일 업로드
- `s3_download`: S3 파일 다운로드
- `vpc_create`: VPC 생성

## HTTP 상태 코드

- `200 OK`: 성공
- `201 Created`: 생성 성공
- `400 Bad Request`: 잘못된 요청
- `401 Unauthorized`: 인증 실패
- `403 Forbidden`: 권한 없음
- `404 Not Found`: 리소스 없음
- `422 Unprocessable Entity`: 유효성 검사 실패
- `500 Internal Server Error`: 서버 오류

## 예제 사용법

### 1. Multi-Agent 채팅
```javascript
// EC2 인스턴스 조회 요청
const response = await fetch('/api/v1/multi-agent/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    message: 'EC2 인스턴스 목록을 조회해주세요',
    thread_id: 'user-session-123',
    stream: false
  })
});

const result = await response.json();
console.log(result.response); // Agent 응답
```

### 2. Task 생성 및 실행
```javascript
// Task 생성
const taskResponse = await fetch('/api/v1/tasks/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    task_id: 'ec2-create-001',
    name: 'Create EC2 Instance',
    task_type: 'ec2_create',
    input_data: {
      instance_type: 't2.micro',
      ami_id: 'ami-0abcdef1234567890'
    }
  })
});

const task = await taskResponse.json();

// Task 실행
const executeResponse = await fetch(`/api/v1/tasks/${task.task_id}/execute`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    task_id: task.task_id
  })
});
```

### 3. 실시간 진행률 모니터링
```javascript
// Task 진행률 폴링
const pollTaskProgress = async (taskId) => {
  const response = await fetch(`/api/v1/tasks/${taskId}`);
  const task = await response.json();
  
  console.log(`Progress: ${task.progress}%`);
  
  if (!task.is_completed) {
    setTimeout(() => pollTaskProgress(taskId), 2000);
  } else {
    console.log('Task completed:', task.output_data);
  }
};
```

## 주의사항

1. **인증**: 현재 인증 시스템이 구현되지 않았습니다. 향후 JWT 토큰 기반 인증이 추가될 예정입니다.

2. **Rate Limiting**: 현재 Rate Limiting이 구현되지 않았습니다. 프로덕션 환경에서는 적절한 Rate Limiting을 구현해야 합니다.

3. **CORS**: 프론트엔드 도메인이 다를 경우 CORS 설정이 필요할 수 있습니다.

4. **WebSocket**: 실시간 업데이트가 필요한 경우 향후 WebSocket 지원이 추가될 예정입니다.

5. **파일 업로드**: 현재 파일 업로드 API는 구현되지 않았습니다. S3 작업은 메타데이터만 처리합니다.

## 변경 이력

- **v1.0.0** (2025-10-25): 초기 API 문서 작성
  - Multi-Agent System API
  - Agent 관리 API
  - Task 관리 API
  - 헬스체크 API
