# 환경변수 관리 가이드

이 문서는 AgenticCP Agent 서비스의 환경변수 설정 및 관리 방법을 설명합니다.

## 📁 환경변수 파일 구조

```
├── env.example          # 기본 환경변수 템플릿
├── env.dev.example      # 개발 환경용 템플릿
├── env.prod.example     # 프로덕션 환경용 템플릿
├── .env                 # 실제 환경변수 파일 (gitignore됨)
├── .env.dev             # 개발 환경 실제 파일 (gitignore됨)
└── .env.prod            # 프로덕션 환경 실제 파일 (gitignore됨)
```

## 🚀 빠른 시작

### 개발 환경 설정

```bash
# 개발 환경 파일 복사
cp env.dev.example .env.dev

# 환경변수 파일 편집
nano .env.dev

# 개발 환경 실행
docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d
```

### 프로덕션 환경 설정

```bash
# 프로덕션 환경 파일 복사
cp env.prod.example .env.prod

# 환경변수 파일 편집 (보안 설정 필수)
nano .env.prod

# 프로덕션 환경 실행
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

## 🔧 환경변수 카테고리

### 1. 애플리케이션 기본 설정

| 변수명 | 설명 | 기본값 | 필수 |
|--------|------|--------|------|
| `APP_NAME` | 애플리케이션 이름 | AgenticCP Agent | ❌ |
| `APP_VERSION` | 애플리케이션 버전 | 0.1.0 | ❌ |
| `DEBUG` | 디버그 모드 | false | ❌ |
| `ENVIRONMENT` | 환경 (development/production) | development | ❌ |

### 2. 서버 설정

| 변수명 | 설명 | 기본값 | 필수 |
|--------|------|--------|------|
| `HOST` | 서버 호스트 | 0.0.0.0 | ❌ |
| `PORT` | 서버 포트 | 8000 | ❌ |
| `WORKERS` | 워커 프로세스 수 | 1 | ❌ |

### 3. 데이터베이스 설정

| 변수명 | 설명 | 기본값 | 필수 |
|--------|------|--------|------|
| `POSTGRES_DB` | PostgreSQL 데이터베이스명 | agenticcp_agent | ✅ |
| `POSTGRES_USER` | PostgreSQL 사용자명 | agenticcp | ✅ |
| `POSTGRES_PASSWORD` | PostgreSQL 비밀번호 | - | ✅ |
| `POSTGRES_PORT` | PostgreSQL 포트 | 5432 | ❌ |
| `POSTGRES_CONTAINER_NAME` | PostgreSQL 컨테이너명 | agenticcp-agent-postgres | ❌ |

### 4. Redis 설정

| 변수명 | 설명 | 기본값 | 필수 |
|--------|------|--------|------|
| `REDIS_PORT` | Redis 포트 | 6379 | ❌ |
| `REDIS_CONTAINER_NAME` | Redis 컨테이너명 | agenticcp-agent-redis | ❌ |

### 5. 보안 설정

| 변수명 | 설명 | 기본값 | 필수 |
|--------|------|--------|------|
| `SECRET_KEY` | JWT 비밀키 | - | ✅ |
| `ALGORITHM` | JWT 알고리즘 | HS256 | ❌ |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 액세스 토큰 만료 시간(분) | 30 | ❌ |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 리프레시 토큰 만료 시간(일) | 7 | ❌ |

### 6. CORS 설정

| 변수명 | 설명 | 기본값 | 필수 |
|--------|------|--------|------|
| `CORS_ORIGINS` | 허용된 오리진 목록 | ["http://localhost:3000"] | ❌ |
| `CORS_CREDENTIALS` | 자격 증명 허용 | true | ❌ |
| `CORS_METHODS` | 허용된 HTTP 메서드 | ["GET", "POST", "PUT", "DELETE"] | ❌ |

### 7. Multi-Agent System 설정

| 변수명 | 설명 | 기본값 | 필수 |
|--------|------|--------|------|
| `MULTI_AGENT_LLM_PROVIDER` | LLM 제공자 (openai/bedrock) | bedrock | ❌ |
| `MULTI_AGENT_OPENAI_API_KEY` | OpenAI API 키 | - | 조건부 |
| `MULTI_AGENT_OPENAI_MODEL` | OpenAI 모델명 | gpt-4o-mini | ❌ |
| `MULTI_AGENT_BEDROCK_MODEL_ID` | Bedrock 모델 ID | amazon.titan-embed-text-v2:0 | ❌ |

### 8. AWS 설정

| 변수명 | 설명 | 기본값 | 필수 |
|--------|------|--------|------|
| `MULTI_AGENT_AWS_ACCESS_KEY_ID` | AWS 액세스 키 ID | - | 조건부 |
| `MULTI_AGENT_AWS_SECRET_ACCESS_KEY` | AWS 시크릿 액세스 키 | - | 조건부 |
| `MULTI_AGENT_AWS_REGION` | AWS 리전 | ap-northeast-2 | ❌ |
| `MULTI_AGENT_AWS_PROFILE` | AWS 프로필명 | default | ❌ |

## 🔒 보안 가이드

### 필수 보안 설정

1. **강력한 비밀번호 사용**
   ```bash
   # PostgreSQL 비밀번호 (최소 16자, 특수문자 포함)
   POSTGRES_PASSWORD=MyStr0ng!P@ssw0rd123
   
   # JWT 비밀키 (최소 32자, 랜덤 문자열)
   SECRET_KEY=$(openssl rand -base64 32)
   ```

2. **프로덕션 환경에서 민감한 정보 보호**
   ```bash
   # .env.prod 파일을 .gitignore에 추가
   echo ".env.prod" >> .gitignore
   
   # 파일 권한 제한
   chmod 600 .env.prod
   ```

3. **CORS 설정 제한**
   ```bash
   # 개발 환경
   CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"]
   
   # 프로덕션 환경
   CORS_ORIGINS=["https://yourdomain.com", "https://api.yourdomain.com"]
   ```

## 🐳 Docker Compose 환경별 실행

### 개발 환경

```bash
# 개발 환경 실행
docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d

# 로그 확인
docker-compose -f docker-compose.dev.yml logs -f

# 서비스 중지
docker-compose -f docker-compose.dev.yml down
```

### 프로덕션 환경

```bash
# 프로덕션 환경 실행
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 헬스체크 확인
docker-compose -f docker-compose.prod.yml ps

# 서비스 중지
docker-compose -f docker-compose.prod.yml down
```

### 환경변수 오버라이드

```bash
# 특정 환경변수만 오버라이드하여 실행
POSTGRES_PASSWORD=newpassword docker-compose -f docker-compose.prod.yml up -d

# 여러 환경변수 오버라이드
export POSTGRES_PASSWORD=newpassword
export SECRET_KEY=newsecretkey
docker-compose -f docker-compose.prod.yml up -d
```

## 🔍 환경변수 검증

### 필수 환경변수 확인 스크립트

```bash
#!/bin/bash
# check-env.sh

required_vars=(
    "POSTGRES_DB"
    "POSTGRES_USER" 
    "POSTGRES_PASSWORD"
    "SECRET_KEY"
)

missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ 필수 환경변수가 설정되지 않았습니다:"
    printf '%s\n' "${missing_vars[@]}"
    exit 1
else
    echo "✅ 모든 필수 환경변수가 설정되었습니다."
fi
```

### 환경변수 테스트

```bash
# 환경변수 파일 로드 및 테스트
source .env.prod
./check-env.sh
```

## 🚨 문제 해결

### 일반적인 문제들

1. **환경변수가 적용되지 않는 경우**
   ```bash
   # 환경변수 파일이 올바르게 로드되는지 확인
   docker-compose config
   
   # 컨테이너 내부에서 환경변수 확인
   docker exec -it agenticcp-agent-prod env | grep POSTGRES
   ```

2. **데이터베이스 연결 실패**
   ```bash
   # PostgreSQL 컨테이너 상태 확인
   docker-compose ps postgres
   
   # PostgreSQL 로그 확인
   docker-compose logs postgres
   ```

3. **Redis 연결 실패**
   ```bash
   # Redis 컨테이너 상태 확인
   docker-compose ps redis
   
   # Redis 연결 테스트
   docker exec -it agenticcp-agent-redis-prod redis-cli ping
   ```

## 📝 환경변수 템플릿 커스터마이징

### 새로운 환경변수 추가

1. **env.example에 추가**
   ```bash
   # 새로운 설정 추가
   NEW_FEATURE_ENABLED=true
   NEW_FEATURE_TIMEOUT=30
   ```

2. **Docker Compose 파일에 추가**
   ```yaml
   environment:
     - NEW_FEATURE_ENABLED=${NEW_FEATURE_ENABLED:-false}
     - NEW_FEATURE_TIMEOUT=${NEW_FEATURE_TIMEOUT:-30}
   ```

3. **환경별 파일에 추가**
   ```bash
   # env.dev.example
   NEW_FEATURE_ENABLED=true
   NEW_FEATURE_TIMEOUT=10
   
   # env.prod.example  
   NEW_FEATURE_ENABLED=false
   NEW_FEATURE_TIMEOUT=60
   ```

## 🔄 환경변수 마이그레이션

### 기존 설정에서 새 설정으로 마이그레이션

```bash
# 1. 기존 환경변수 백업
cp .env .env.backup

# 2. 새로운 템플릿으로 업데이트
cp env.dev.example .env.new

# 3. 기존 값들을 새 파일에 복사
# (수동으로 중요한 값들 이전)

# 4. 새 파일로 교체
mv .env.new .env
```

이 가이드를 따라하면 AgenticCP Agent 서비스를 다양한 환경에서 안전하고 효율적으로 관리할 수 있습니다.
