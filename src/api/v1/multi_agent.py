"""
Multi-Agent System API 라우터

Supervisor Agent와 EC2 Mini Agent를 통합하여 사용자 요청을 처리하는 API 엔드포인트
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

from ...agents.supervisor_agent import SupervisorAgent
from ...agents.ec2_agent import EC2Agent
from ...config.settings import get_settings

# 라우터 생성
router = APIRouter(tags=["Multi-Agent System"])

# 로깅 설정
logging.basicConfig(level=logging.INFO)
agent_logger = logging.getLogger(__name__)


class MultiAgentRequest(BaseModel):
    """Multi-Agent System 요청 모델"""
    message: str = Field(..., description="사용자 메시지", min_length=1, max_length=1000)
    thread_id: str = Field(default="default", description="대화 스레드 ID")
    stream: bool = Field(default=False, description="스트리밍 응답 여부")
    context: Optional[Dict[str, Any]] = Field(default=None, description="추가 컨텍스트 정보")


class MultiAgentResponse(BaseModel):
    """Multi-Agent System 응답 모델"""
    success: bool = Field(..., description="요청 처리 성공 여부")
    response: Optional[str] = Field(default=None, description="에이전트 응답")
    agent_used: Optional[str] = Field(default=None, description="사용된 에이전트")
    confidence: Optional[float] = Field(default=None, description="신뢰도 점수")
    routing_info: Optional[Dict[str, Any]] = Field(default=None, description="라우팅 정보")
    thread_id: str = Field(..., description="대화 스레드 ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="응답 시간")
    processing_time: Optional[float] = Field(default=None, description="처리 시간(초)")


class ConversationHistoryResponse(BaseModel):
    """대화 기록 응답 모델"""
    thread_id: str = Field(..., description="대화 스레드 ID")
    messages: List[Dict[str, Any]] = Field(..., description="대화 메시지 목록")
    total_count: int = Field(..., description="총 메시지 수")


class AgentStatusResponse(BaseModel):
    """에이전트 상태 응답 모델"""
    supervisor_agent: bool = Field(..., description="Supervisor Agent 상태")
    ec2_agent: bool = Field(..., description="EC2 Agent 상태")
    available_agents: List[str] = Field(..., description="사용 가능한 에이전트 목록")
    system_health: str = Field(..., description="시스템 상태")


class MultiAgentSystem:
    """Multi-Agent System 관리 클래스"""
    
    def __init__(self):
        from dotenv import load_dotenv
        import os
        load_dotenv()  # 환경 변수 명시적 로드
        
        # 환경 변수 직접 확인
        self.llm_provider = os.getenv('MULTI_AGENT_LLM_PROVIDER', 'bedrock')
        self.aws_access_key_id = os.getenv('MULTI_AGENT_AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('MULTI_AGENT_AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('MULTI_AGENT_AWS_REGION', 'ap-northeast-2')
        self.openai_api_key = os.getenv('MULTI_AGENT_OPENAI_API_KEY')
        
        # Settings 객체는 나중에 필요할 때 로드
        self.settings = None
        self.supervisor_agent: Optional[SupervisorAgent] = None
        self.ec2_agent: Optional[EC2Agent] = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """시스템 초기화"""
        try:
            if self._initialized:
                return True
            
            agent_logger.info("🚀 Multi-Agent System 초기화 중...")
            
            # OpenAI API 키 확인 (Bedrock 사용 시에는 AWS 자격 증명 확인)
            agent_logger.info(f"🔧 LLM Provider: {self.llm_provider}")
            agent_logger.info(f"🔧 AWS Access Key: {self.aws_access_key_id[:10] if self.aws_access_key_id else 'None'}...")
            agent_logger.info(f"🔧 AWS Secret Key: {self.aws_secret_access_key[:10] if self.aws_secret_access_key else 'None'}...")
            
            if self.llm_provider.lower() == "bedrock":
                if not self.aws_access_key_id or not self.aws_secret_access_key:
                    raise ValueError("Bedrock 사용 시 AWS 자격 증명이 설정되지 않았습니다.")
            else:
                if not self.openai_api_key or self.openai_api_key == "your-openai-api-key-here":
                    raise ValueError("OpenAI API 키가 설정되지 않았습니다.")
            
            # Settings 객체 로드 (필요한 경우)
            if self.settings is None:
                self.settings = get_settings()
            
            # Supervisor Agent 초기화
            self.supervisor_agent = SupervisorAgent(
                settings=self.settings.multi_agent,
                aws_access_key=self.aws_access_key_id,
                aws_secret_key=self.aws_secret_access_key,
                region=self.aws_region
            )
            
            # EC2 Agent 초기화
            self.ec2_agent = EC2Agent(
                settings=self.settings.multi_agent,
                aws_access_key=self.aws_access_key_id,
                aws_secret_key=self.aws_secret_access_key,
                region=self.aws_region
            )
            
            self._initialized = True
            agent_logger.info("✅ Multi-Agent System 초기화 완료!")
            return True
            
        except Exception as e:
            agent_logger.error(f"❌ Multi-Agent System 초기화 실패: {e}")
            return False
    
    async def process_request(self, request: MultiAgentRequest) -> MultiAgentResponse:
        """사용자 요청 처리"""
        if not self._initialized:
            await self.initialize()
        
        if not self.supervisor_agent:
            raise HTTPException(
                status_code=500,
                detail="Multi-Agent System이 초기화되지 않았습니다."
            )
        
        start_time = datetime.now()
        
        try:
            agent_logger.info(f"📝 요청 처리 중: {request.message[:50]}...")
            
            # 요청 처리
            result = await self.supervisor_agent.process_request_async(
                request.message, 
                request.thread_id
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # 응답 생성
            response = MultiAgentResponse(
                success=result.get("success", False),
                response=result.get("response"),
                agent_used=result.get("agent_used"),
                confidence=result.get("confidence"),
                routing_info=result.get("routing_info"),
                thread_id=request.thread_id,
                processing_time=processing_time
            )
            
            agent_logger.info(f"✅ 요청 처리 완료 (소요시간: {processing_time:.2f}초)")
            return response
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            agent_logger.error(f"❌ 요청 처리 실패: {e}")
            
            return MultiAgentResponse(
                success=False,
                response=f"요청 처리 중 오류가 발생했습니다: {str(e)}",
                thread_id=request.thread_id,
                processing_time=processing_time
            )
    
    async def get_conversation_history(self, thread_id: str) -> ConversationHistoryResponse:
        """대화 기록 조회"""
        if not self._initialized:
            await self.initialize()
        
        if not self.supervisor_agent:
            raise HTTPException(
                status_code=500,
                detail="Multi-Agent System이 초기화되지 않았습니다."
            )
        
        try:
            history = self.supervisor_agent.get_conversation_history(thread_id)
            
            return ConversationHistoryResponse(
                thread_id=thread_id,
                messages=history,
                total_count=len(history)
            )
            
        except Exception as e:
            agent_logger.error(f"❌ 대화 기록 조회 실패: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"대화 기록 조회 중 오류가 발생했습니다: {str(e)}"
            )
    
    async def get_system_status(self) -> AgentStatusResponse:
        """시스템 상태 조회"""
        try:
            await self.initialize()
            
            return AgentStatusResponse(
                supervisor_agent=self.supervisor_agent is not None,
                ec2_agent=self.ec2_agent is not None,
                available_agents=["supervisor", "ec2", "s3", "vpc", "general"],
                system_health="healthy" if self._initialized else "initializing"
            )
            
        except Exception as e:
            agent_logger.error(f"❌ 시스템 상태 조회 실패: {e}")
            return AgentStatusResponse(
                supervisor_agent=False,
                ec2_agent=False,
                available_agents=[],
                system_health="error"
            )


# 전역 Multi-Agent System 인스턴스
# Multi-Agent System 인스턴스 (지연 초기화)
multi_agent_system: Optional[MultiAgentSystem] = None

def get_multi_agent_system() -> MultiAgentSystem:
    """Multi-Agent System 인스턴스 가져오기 (지연 초기화)"""
    global multi_agent_system
    if multi_agent_system is None:
        multi_agent_system = MultiAgentSystem()
    return multi_agent_system


@router.post("/chat", response_model=MultiAgentResponse)
async def chat_with_agents(request: MultiAgentRequest):
    """
    Multi-Agent System과 대화
    
    사용자 메시지를 받아서 적절한 에이전트로 라우팅하여 응답을 생성합니다.
    """
    try:
        result = await get_multi_agent_system().process_request(request)
        return result
    except Exception as e:
        logger.error(f"Multi-Agent 채팅 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_with_agents_stream(request: MultiAgentRequest):
    """
    Multi-Agent System과 스트리밍 대화
    
    실시간으로 응답을 스트리밍합니다.
    """
    try:
        if not request.stream:
            request.stream = True
        
        async def generate_response():
            try:
                # 스트리밍 응답 생성 (실제 구현에서는 스트리밍 로직 추가)
                result = await get_multi_agent_system().process_request(request)
                
                # JSON 형태로 스트리밍
                yield f"data: {result.json()}\n\n"
                
            except Exception as e:
                error_response = MultiAgentResponse(
                    success=False,
                    response=f"스트리밍 중 오류 발생: {str(e)}",
                    thread_id=request.thread_id
                )
                yield f"data: {error_response.json()}\n\n"
        
        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
        
    except Exception as e:
        logger.error(f"Multi-Agent 스트리밍 채팅 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{thread_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(thread_id: str):
    """
    대화 기록 조회
    
    특정 스레드의 대화 기록을 조회합니다.
    """
    try:
        result = await get_multi_agent_system().get_conversation_history(thread_id)
        return result
    except Exception as e:
        logger.error(f"대화 기록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{thread_id}")
async def clear_conversation_history(thread_id: str):
    """
    대화 기록 삭제
    
    특정 스레드의 대화 기록을 삭제합니다.
    """
    try:
        if not get_multi_agent_system().supervisor_agent:
            raise HTTPException(status_code=500, detail="시스템이 초기화되지 않았습니다.")
        
        get_multi_agent_system().supervisor_agent.clear_thread(thread_id)
        
        return {"success": True, "message": f"스레드 '{thread_id}'의 대화 기록이 삭제되었습니다."}
        
    except Exception as e:
        logger.error(f"대화 기록 삭제 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=AgentStatusResponse)
async def get_system_status():
    """
    시스템 상태 조회
    
    Multi-Agent System의 상태와 사용 가능한 에이전트를 확인합니다.
    """
    try:
        result = await get_multi_agent_system().get_system_status()
        return result
    except Exception as e:
        logger.error(f"시스템 상태 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialize")
async def initialize_system():
    """
    시스템 초기화
    
    Multi-Agent System을 수동으로 초기화합니다.
    """
    try:
        success = await get_multi_agent_system().initialize()
        
        if success:
            return {"success": True, "message": "Multi-Agent System이 성공적으로 초기화되었습니다."}
        else:
            raise HTTPException(status_code=500, detail="시스템 초기화에 실패했습니다.")
            
    except Exception as e:
        logger.error(f"시스템 초기화 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def list_available_agents():
    """
    사용 가능한 에이전트 목록 조회
    
    현재 사용 가능한 에이전트들의 목록과 설명을 반환합니다.
    """
    agents_info = {
        "agents": [
            {
                "name": "supervisor",
                "description": "사용자 요청을 분석하고 적절한 Mini Agent로 라우팅하는 Supervisor Agent",
                "capabilities": ["요청 분석", "에이전트 라우팅", "대화 관리", "상태 추적"]
            },
            {
                "name": "ec2",
                "description": "AWS EC2 인스턴스 관리 및 조작을 담당하는 EC2 Mini Agent",
                "capabilities": ["EC2 인스턴스 생성", "인스턴스 목록 조회", "인스턴스 상태 확인", "AWS 리소스 관리"]
            },
            {
                "name": "s3",
                "description": "AWS S3 버킷 및 객체 관리 및 조작을 담당하는 S3 Mini Agent",
                "capabilities": ["S3 버킷 생성", "버킷 목록 조회", "객체 업로드/다운로드", "버킷 정책 관리"]
            },
            {
                "name": "vpc",
                "description": "AWS VPC, 서브넷, 보안 그룹 관리 및 조작을 담당하는 VPC Mini Agent",
                "capabilities": ["VPC 생성", "서브넷 관리", "보안 그룹 관리", "네트워크 설정"]
            },
            {
                "name": "general",
                "description": "일반적인 대화 및 질문을 처리하는 General Agent",
                "capabilities": ["일반 대화", "정보 제공", "질문 답변", "도움말 제공"]
            }
        ],
        "total_count": 5
    }
    
    return agents_info