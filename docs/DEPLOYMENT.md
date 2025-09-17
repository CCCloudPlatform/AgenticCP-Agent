# AgenticCP Agent 배포 가이드

## 📋 개요

이 문서는 AgenticCP Agent 서비스를 다양한 환경에 배포하는 방법을 설명합니다.

## 🏗️ 배포 아키텍처

### 개발 환경
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │───▶│   PostgreSQL    │    │     Redis       │
│   (Port 8000)   │    │   (Port 5432)   │    │   (Port 6379)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 프로덕션 환경
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │───▶│   FastAPI App   │───▶│   PostgreSQL    │
│   (Nginx)       │    │   (Multiple)    │    │   (Cluster)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SSL/TLS       │    │   Redis         │    │   Monitoring    │
│   Certificate   │    │   (Cluster)     │    │   (Prometheus)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🐳 Docker 배포

### 1. Docker 이미지 빌드

```bash
# 개발용 이미지 빌드
docker build -t agenticcp-agent:dev .

# 프로덕션용 이미지 빌드
docker build -t agenticcp-agent:prod --target production .
```

### 2. Docker Compose 실행

```bash
# 개발 환경
docker-compose -f docker-compose.yml up -d

# 프로덕션 환경
docker-compose -f docker-compose.prod.yml up -d
```

### 3. 환경별 Docker Compose 파일

#### docker-compose.prod.yml
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: agenticcp_agent
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - agenticcp-network

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - agenticcp-network

  agent:
    build: .
    environment:
      - DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/agenticcp_agent
      - REDIS_URL=redis://redis:6379/0
      - ENVIRONMENT=production
      - DEBUG=false
    depends_on:
      - postgres
      - redis
    networks:
      - agenticcp-network
    restart: unless-stopped
    deploy:
      replicas: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - agent
    networks:
      - agenticcp-network

volumes:
  postgres_data:
  redis_data:

networks:
  agenticcp-network:
    driver: bridge
```

## ☁️ 클라우드 배포

### AWS 배포

#### 1. ECS 배포

```yaml
# task-definition.json
{
  "family": "agenticcp-agent",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "agenticcp-agent",
      "image": "your-account.dkr.ecr.region.amazonaws.com/agenticcp-agent:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "DATABASE_URL",
          "value": "postgresql+asyncpg://user:pass@rds-endpoint:5432/agenticcp_agent"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/agenticcp-agent",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### 2. RDS 설정

```bash
# RDS 인스턴스 생성
aws rds create-db-instance \
  --db-instance-identifier agenticcp-agent-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --master-username admin \
  --master-user-password your-password \
  --allocated-storage 20 \
  --vpc-security-group-ids sg-12345678 \
  --db-subnet-group-name your-subnet-group
```

#### 3. ElastiCache 설정

```bash
# Redis 클러스터 생성
aws elasticache create-cache-cluster \
  --cache-cluster-id agenticcp-agent-redis \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1 \
  --vpc-security-group-ids sg-12345678 \
  --subnet-group-name your-subnet-group
```

### GCP 배포

#### 1. Cloud Run 배포

```yaml
# cloudbuild.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/agenticcp-agent', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/agenticcp-agent']
  - name: 'gcr.io/cloud-builders/gcloud'
    args: [
      'run', 'deploy', 'agenticcp-agent',
      '--image', 'gcr.io/$PROJECT_ID/agenticcp-agent',
      '--region', 'us-central1',
      '--platform', 'managed',
      '--allow-unauthenticated'
    ]
```

#### 2. Cloud SQL 설정

```bash
# Cloud SQL 인스턴스 생성
gcloud sql instances create agenticcp-agent-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --root-password=your-password
```

### Azure 배포

#### 1. Container Instances 배포

```yaml
# azure-deploy.yaml
apiVersion: 2021-07-01
location: eastus
name: agenticcp-agent
properties:
  containers:
  - name: agenticcp-agent
    properties:
      image: your-registry.azurecr.io/agenticcp-agent:latest
      resources:
        requests:
          cpu: 1
          memoryInGb: 2
      ports:
      - port: 8000
        protocol: TCP
  osType: Linux
  restartPolicy: Always
  ipAddress:
    type: Public
    ports:
    - protocol: TCP
      port: 8000
```

## 🔧 환경 설정

### 1. 환경 변수

#### 개발 환경 (.env)
```bash
APP_NAME=AgenticCP Agent
APP_VERSION=0.1.0
DEBUG=true
ENVIRONMENT=development

DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/agenticcp_agent
REDIS_URL=redis://localhost:6379/0

SECRET_KEY=dev-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"]
```

#### 프로덕션 환경
```bash
APP_NAME=AgenticCP Agent
APP_VERSION=0.1.0
DEBUG=false
ENVIRONMENT=production

DATABASE_URL=postgresql+asyncpg://user:password@prod-db:5432/agenticcp_agent
REDIS_URL=redis://prod-redis:6379/0

SECRET_KEY=your-production-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

CORS_ORIGINS=["https://your-frontend.com"]
```

### 2. 데이터베이스 마이그레이션

```bash
# 마이그레이션 생성
alembic revision --autogenerate -m "Initial migration"

# 마이그레이션 실행
alembic upgrade head

# 마이그레이션 롤백
alembic downgrade -1
```

### 3. SSL/TLS 설정

#### Nginx 설정 (nginx.conf)
```nginx
upstream agenticcp_agent {
    server agent1:8000;
    server agent2:8000;
    server agent3:8000;
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;

    location / {
        proxy_pass http://agenticcp_agent;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 📊 모니터링 및 로깅

### 1. Prometheus 메트릭

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
ACTIVE_AGENTS = Gauge('active_agents_total', 'Number of active agents')
RUNNING_TASKS = Gauge('running_tasks_total', 'Number of running tasks')
```

### 2. 로그 설정

```yaml
# logging.yaml
version: 1
disable_existing_loggers: false

formatters:
  default:
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  json:
    format: '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: default
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: INFO
    formatter: json
    filename: logs/agent.log
    maxBytes: 10485760  # 10MB
    backupCount: 5

loggers:
  agenticcp_agent:
    level: INFO
    handlers: [console, file]
    propagate: false
```

### 3. 헬스체크 설정

```yaml
# kubernetes-health-check.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: health-check-config
data:
  health-check.sh: |
    #!/bin/bash
    curl -f http://localhost:8000/api/v1/health/liveness || exit 1
    curl -f http://localhost:8000/api/v1/health/readiness || exit 1
```

## 🔄 CI/CD 파이프라인

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      - name: Run tests
        run: |
          pytest --cov=src

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker image
        run: |
          docker build -t agenticcp-agent:${{ github.sha }} .
      - name: Push to registry
        run: |
          docker push your-registry/agenticcp-agent:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: |
          # 배포 스크립트 실행
          ./scripts/deploy.sh ${{ github.sha }}
```

## 🚀 배포 체크리스트

### 배포 전 확인사항

- [ ] 모든 테스트 통과
- [ ] 코드 리뷰 완료
- [ ] 환경 변수 설정 확인
- [ ] 데이터베이스 마이그레이션 준비
- [ ] SSL 인증서 유효성 확인
- [ ] 백업 계획 수립
- [ ] 롤백 계획 수립

### 배포 후 확인사항

- [ ] 서비스 정상 시작 확인
- [ ] 헬스체크 통과 확인
- [ ] API 엔드포인트 동작 확인
- [ ] 로그 정상 출력 확인
- [ ] 메트릭 수집 확인
- [ ] 알림 설정 확인

## 🔧 트러블슈팅

### 일반적인 문제

#### 1. 데이터베이스 연결 실패
```bash
# 연결 확인
psql -h your-db-host -U your-user -d agenticcp_agent

# 방화벽 확인
telnet your-db-host 5432
```

#### 2. Redis 연결 실패
```bash
# Redis 연결 확인
redis-cli -h your-redis-host ping

# 메모리 사용량 확인
redis-cli -h your-redis-host info memory
```

#### 3. 메모리 부족
```bash
# 메모리 사용량 확인
free -h
ps aux --sort=-%mem | head

# Docker 메모리 제한 확인
docker stats
```

### 로그 분석

```bash
# 애플리케이션 로그 확인
tail -f logs/agent.log

# 에러 로그 필터링
grep "ERROR" logs/agent.log

# 특정 시간대 로그 확인
grep "2024-01-01 10:" logs/agent.log
```

## 📞 지원

배포 관련 문제가 발생하면 다음을 확인하세요:

1. **로그 확인**: 애플리케이션 및 시스템 로그
2. **헬스체크**: `/api/v1/health` 엔드포인트
3. **메트릭**: Prometheus 메트릭 대시보드
4. **문서**: API 문서 및 설정 가이드
5. **이슈 트래커**: GitHub Issues

