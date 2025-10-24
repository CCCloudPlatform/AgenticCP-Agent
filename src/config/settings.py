"""
애플리케이션 설정 관리

환경 변수를 통한 설정 관리 및 Pydantic을 활용한 타입 안전성 보장
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """데이터베이스 설정"""
    
    url: str = Field(default="postgresql+asyncpg://user:password@localhost:5432/agenticcp_agent", description="데이터베이스 URL")
    url_sync: str = Field(default="postgresql://user:password@localhost:5432/agenticcp_agent", description="동기 데이터베이스 URL")
    echo: bool = Field(default=False, description="SQL 쿼리 로깅 여부")
    pool_size: int = Field(default=10, description="연결 풀 크기")
    max_overflow: int = Field(default=20, description="최대 오버플로우")
    pool_timeout: int = Field(default=30, description="연결 풀 타임아웃")
    pool_recycle: int = Field(default=3600, description="연결 재활용 시간")
    
    model_config = SettingsConfigDict(env_prefix="DATABASE_")


class RedisSettings(BaseSettings):
    """Redis 설정"""
    
    url: str = Field(default="redis://localhost:6379/0", description="Redis URL")
    max_connections: int = Field(default=10, description="최대 연결 수")
    socket_timeout: int = Field(default=5, description="소켓 타임아웃")
    socket_connect_timeout: int = Field(default=5, description="소켓 연결 타임아웃")
    
    model_config = SettingsConfigDict(env_prefix="REDIS_")


class JWTSettings(BaseSettings):
    """JWT 설정"""
    
    secret_key: str = Field(default="your-secret-key-here-change-in-production", description="JWT 시크릿 키")
    algorithm: str = Field(default="HS256", description="JWT 알고리즘")
    access_token_expire_minutes: int = Field(default=30, description="액세스 토큰 만료 시간(분)")
    refresh_token_expire_days: int = Field(default=7, description="리프레시 토큰 만료 시간(일)")
    
    model_config = SettingsConfigDict(env_prefix="JWT_")


class CORSSettings(BaseSettings):
    """CORS 설정"""
    
    origins: List[str] = Field(default=["*"], description="허용된 오리진")
    credentials: bool = Field(default=True, description="자격 증명 허용")
    methods: List[str] = Field(default=["*"], description="허용된 HTTP 메서드")
    headers: List[str] = Field(default=["*"], description="허용된 헤더")
    
    model_config = SettingsConfigDict(env_prefix="CORS_")
    
    @validator("origins", pre=True)
    def parse_origins(cls, v):
        """문자열 리스트를 파싱"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


class APISettings(BaseSettings):
    """API 설정"""
    
    v1_prefix: str = Field(default="/api/v1", description="API v1 프리픽스")
    title: str = Field(default="AgenticCP Agent API", description="API 제목")
    description: str = Field(default="AgenticCP Agent 서비스 API 문서", description="API 설명")
    version: str = Field(default="0.1.0", description="API 버전")
    
    model_config = SettingsConfigDict(env_prefix="API_")


class LoggingSettings(BaseSettings):
    """로깅 설정"""
    
    level: str = Field(default="INFO", description="로그 레벨")
    format: str = Field(default="json", description="로그 포맷 (json/text)")
    file: Optional[str] = Field(default=None, description="로그 파일 경로")
    max_size: str = Field(default="100MB", description="로그 파일 최대 크기")
    backup_count: int = Field(default=5, description="백업 파일 개수")
    
    model_config = SettingsConfigDict(env_prefix="LOG_")


class AgentSettings(BaseSettings):
    """에이전트 설정"""
    
    id: str = Field(default="agent-001", description="에이전트 ID")
    name: str = Field(default="Default Agent", description="에이전트 이름")
    type: str = Field(default="general", description="에이전트 타입")
    max_concurrent_tasks: int = Field(default=10, description="최대 동시 작업 수")
    task_timeout_seconds: int = Field(default=300, description="작업 타임아웃(초)")
    
    model_config = SettingsConfigDict(env_prefix="AGENT_")


class ExternalServiceSettings(BaseSettings):
    """외부 서비스 설정"""
    
    core_service_url: str = Field(default="http://localhost:8080", description="Core 서비스 URL")
    core_service_api_key: str = Field(default="your-core-service-api-key", description="Core 서비스 API 키")
    timeout: int = Field(default=30, description="요청 타임아웃(초)")
    max_retries: int = Field(default=3, description="최대 재시도 횟수")
    
    model_config = SettingsConfigDict(env_prefix="EXTERNAL_SERVICE_")


class MultiAgentSettings(BaseSettings):
    """Multi-Agent System 설정"""
    
    # LLM Provider 설정
    llm_provider: str = Field(default="bedrock", description="LLM 제공자 (openai/bedrock)")
    
    # OpenAI 설정 (OpenAI 사용 시)
    openai_api_key: str = Field(default="your-openai-api-key-here", description="OpenAI API 키")
    openai_model: str = Field(default="gpt-4o-mini", description="사용할 OpenAI 모델")
    openai_temperature: float = Field(default=0.1, description="OpenAI 모델 온도")
    
    # AWS Bedrock 설정
    bedrock_model_id: str = Field(default="anthropic.claude-3-haiku-20240307-v1:0", description="Bedrock 모델 ID")
    bedrock_temperature: float = Field(default=0.1, description="Bedrock 모델 온도")
    bedrock_max_tokens: int = Field(default=4000, description="Bedrock 최대 토큰 수")
    bedrock_top_p: float = Field(default=0.9, description="Bedrock Top-P 값")
    bedrock_top_k: int = Field(default=250, description="Bedrock Top-K 값")
    
    # AWS 설정
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS Access Key ID")
    aws_secret_access_key: Optional[str] = Field(default=None, description="AWS Secret Access Key")
    aws_region: str = Field(default="us-east-1", description="AWS 기본 리전")
    aws_profile: Optional[str] = Field(default=None, description="AWS 프로필 이름")
    
    # 대화 관리 설정
    max_conversation_history: int = Field(default=100, description="최대 대화 기록 수")
    conversation_timeout: int = Field(default=3600, description="대화 타임아웃 (초)")
    
    # EC2 Agent 설정
    ec2_default_instance_type: str = Field(default="t2.micro", description="기본 EC2 인스턴스 타입")
    ec2_default_ami: str = Field(default="ami-0abcdef1234567890", description="기본 AMI ID")
    
    model_config = SettingsConfigDict(env_prefix="MULTI_AGENT_")


class Settings(BaseSettings):
    """전체 애플리케이션 설정"""
    
    # 기본 설정
    app_name: str = Field(default="AgenticCP Agent", description="애플리케이션 이름")
    app_version: str = Field(default="0.1.0", description="애플리케이션 버전")
    app_description: str = Field(default="Python FastAPI 기반 에이전트 서비스", description="애플리케이션 설명")
    debug: bool = Field(default=False, description="디버그 모드")
    environment: str = Field(default="development", description="환경 (development/staging/production)")
    
    # 서버 설정
    host: str = Field(default="0.0.0.0", description="서버 호스트")
    port: int = Field(default=8000, description="서버 포트")
    workers: int = Field(default=1, description="워커 프로세스 수")
    
    # 모니터링 설정
    enable_metrics: bool = Field(default=True, description="메트릭 활성화")
    metrics_path: str = Field(default="/metrics", description="메트릭 경로")
    health_check_path: str = Field(default="/health", description="헬스체크 경로")
    
    # 하위 설정
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    external_service: ExternalServiceSettings = Field(default_factory=ExternalServiceSettings)
    multi_agent: MultiAgentSettings = Field(default_factory=MultiAgentSettings)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @validator("environment")
    def validate_environment(cls, v):
        """환경 값 검증"""
        allowed_environments = ["development", "staging", "production"]
        if v not in allowed_environments:
            raise ValueError(f"환경은 {allowed_environments} 중 하나여야 합니다")
        return v
    
    @validator("debug", pre=True)
    def parse_debug(cls, v):
        """디버그 값 파싱"""
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return v
    
    @property
    def is_development(self) -> bool:
        """개발 환경 여부"""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """프로덕션 환경 여부"""
        return self.environment == "production"
    
    @property
    def database_url(self) -> str:
        """데이터베이스 URL 반환"""
        return self.database.url
    
    @property
    def database_url_sync(self) -> str:
        """동기 데이터베이스 URL 반환"""
        return self.database.url_sync


@lru_cache()
def get_settings() -> Settings:
    """설정 인스턴스 반환 (캐시됨)"""
    return Settings()

