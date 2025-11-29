"""
Supervisor Agent using LangGraph
사용자 요청을 분석하고 적절한 Mini Agent로 분기하는 역할
LangGraph를 사용한 실제 그래프 기반 워크플로우 구현
"""

from typing import Dict, List, Any, Optional, TypedDict, Literal
from dataclasses import dataclass
from enum import Enum
import json
import logging
import re
from datetime import datetime
import asyncio

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.tools import Tool

# LangGraph imports
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .agent_factory import AgentFactory

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentType(Enum):
    """사용 가능한 Agent 타입들"""
    EC2 = "ec2"
    S3 = "s3"
    VPC = "vpc"
    GENERAL = "general"


class AgentState(TypedDict):
    """Agent 상태를 관리하는 TypedDict (LangGraph 호환)"""
    messages: List[BaseMessage]
    next_agent: Optional[str]
    agent_result: Optional[Dict[str, Any]]
    user_request: str
    context: Dict[str, Any]
    timestamp: str
    thread_id: str
    routing_result: Optional[Dict[str, Any]]
    llm_output: Optional[str]
    final_response: Optional[str]


class SupervisorAgent:
    """LangGraph를 사용한 Supervisor Agent"""
    
    def __init__(self, settings, aws_access_key: str = None, aws_secret_key: str = None, region: str = "us-east-1"):
        # LLM Provider 설정에 따라 LLM 초기화 (Bedrock 전용)
        model_id = settings.bedrock_model_id
        
        # 임베딩 모델인지 확인 (텍스트 생성에 사용 불가)
        is_embedding_model = "embed" in model_id.lower() or "embedding" in model_id.lower()
        if is_embedding_model:
            logger.error(
                f"⚠️ 경고: {model_id}는 임베딩 모델입니다. 텍스트 생성에는 사용할 수 없습니다.\n"
                f"텍스트 생성 모델을 사용하세요:\n"
                f"- Claude: anthropic.claude-3-haiku-20240307-v1:0\n"
                f"- Titan Text: amazon.titan-text-express-v1 또는 amazon.titan-text-lite-v1\n"
                f"- Llama: meta.llama3-8b-instruct-v1:0\n"
                f"현재 임베딩 모델 ID는 bedrock_embedding_model_id 설정을 사용하세요."
            )
            raise ValueError(
                f"{model_id}는 임베딩 모델입니다. 텍스트 생성 모델을 MULTI_AGENT_BEDROCK_MODEL_ID에 설정하세요."
            )
        
        # Claude 모델인지 확인
        is_claude = "claude" in model_id.lower()
        
        if is_claude:
            # Claude 모델은 model_kwargs만 사용 (최상위 레벨 파라미터 제거)
            self.llm = ChatBedrock(
                model_id=model_id,
                aws_access_key_id=aws_access_key or settings.aws_access_key_id,
                aws_secret_access_key=aws_secret_key or settings.aws_secret_access_key,
                region_name=region or settings.aws_region,
                model_kwargs={
                    "temperature": settings.bedrock_temperature,
                    "max_tokens": settings.bedrock_max_tokens,
                }
            )
        else:
            # 다른 모델 (Titan Text, Llama 등)은 기본 설정 사용
            self.llm = ChatBedrock(
                model_id=model_id,
                temperature=settings.bedrock_temperature,
                max_tokens=settings.bedrock_max_tokens,
                aws_access_key_id=aws_access_key or settings.aws_access_key_id,
                aws_secret_access_key=aws_secret_key or settings.aws_secret_access_key,
                region_name=region or settings.aws_region
            )
        logger.info(f"Bedrock LLM 초기화 완료: {model_id}")
        
        # AWS 자격 증명 저장
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.region = region
        self.settings = settings
        
        # Agent Factory를 통한 에이전트 관리
        self.agent_factory = AgentFactory()
        self.conversation_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # 메모리 세이버 설정 (대화 상태 저장)
        self.memory = MemorySaver()
        
        # LangGraph 워크플로우 구성
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """LangGraph 워크플로우 구성"""
        
        # 1. 요청 분석 노드
        def analyze_request(state: AgentState) -> AgentState:
            """사용자 요청을 분석하여 적절한 Agent 결정 (LLM 기반)"""
            logger.info("사용자 요청 분석 중...")
            
            try:
                user_request = state.get("user_request", "")
                
                # LLM을 사용하여 요청 분석 및 Agent 라우팅
                routing_prompt = ChatPromptTemplate.from_messages([
                    ("system", """당신은 사용자 요청을 분석하여 적절한 전문 Agent로 라우팅하는 Supervisor Agent입니다.

사용 가능한 Agent:
1. ec2: EC2 인스턴스, 서버, AMI, 보안그룹, 인스턴스 생성/삭제/관리 관련
2. s3: S3 버킷, 객체, 파일 스토리지, 업로드/다운로드 관련
3. vpc: VPC, 서브넷, 네트워크, CIDR, 가용영역, 네트워크 설정 관련
4. general: 일반적인 대화, 질문, 또는 위 카테고리에 해당하지 않는 요청

사용자 요청의 의도와 맥락을 분석하여 가장 적절한 Agent를 선택하세요.
응답은 반드시 다음 JSON 형식으로 제공해야 합니다:
{{
    "agent_type": "ec2|s3|vpc|general",
    "reasoning": "선택 이유를 간단히 설명",
    "confidence": 0.0-1.0 사이의 숫자
}}"""),
                    ("human", "사용자 요청: {user_request}")
                ])
                
                # LLM 호출
                messages = routing_prompt.format_messages(user_request=user_request)
                response = self.llm.invoke(messages)
                
                # 응답 파싱
                response_text = response.content if hasattr(response, 'content') else str(response)
                
                # JSON 추출 시도
                try:
                    # JSON 부분만 추출 (마크다운 코드 블록 제거)
                    import re
                    json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(0)
                    
                    analysis = json.loads(response_text)
                    agent_type = analysis.get("agent_type", "general").lower()
                    reasoning = analysis.get("reasoning", "LLM 분석 결과")
                    confidence = float(analysis.get("confidence", 0.7))
                    
                    # 유효한 agent_type인지 확인
                    valid_agents = ["ec2", "s3", "vpc", "general"]
                    if agent_type not in valid_agents:
                        logger.warning(f"유효하지 않은 agent_type: {agent_type}, general로 폴백")
                        agent_type = "general"
                        confidence = 0.5
                    
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.warning(f"LLM 응답 파싱 실패, 규칙 기반 폴백 사용: {e}")
                    # 폴백: 간단한 키워드 기반 분석
                    user_request_lower = user_request.lower()
                    if any(kw in user_request_lower for kw in ["ec2", "인스턴스", "서버", "ami"]):
                        agent_type = "ec2"
                        reasoning = "키워드 기반 폴백: EC2 관련"
                        confidence = 0.7
                    elif any(kw in user_request_lower for kw in ["s3", "버킷", "객체", "스토리지"]):
                        agent_type = "s3"
                        reasoning = "키워드 기반 폴백: S3 관련"
                        confidence = 0.7
                    elif any(kw in user_request_lower for kw in ["vpc", "서브넷", "네트워크"]):
                        agent_type = "vpc"
                        reasoning = "키워드 기반 폴백: VPC 관련"
                        confidence = 0.7
                    else:
                        agent_type = "general"
                        reasoning = "키워드 기반 폴백: 일반 요청"
                        confidence = 0.5
                
                analysis = {
                    "agent_type": agent_type,
                    "reasoning": reasoning,
                    "confidence": confidence,
                    "context": {"method": "llm_based", "raw_response": response_text[:200]}
                }
                
                state["routing_result"] = analysis
                state["next_agent"] = agent_type
                state["context"] = analysis.get("context", {})
                state["context"]["confidence"] = confidence
                
                logger.info(f"요청 분석 완료 (LLM): {agent_type} - {reasoning} (신뢰도: {confidence:.2f})")
                
            except Exception as e:
                error_msg = str(e)
                
                # 예상된 오류인지 확인 (Bedrock use case form 제출 안 됨)
                is_expected_error = (
                    "use case details" in error_msg.lower() or
                    "resourcenotfoundexception" in error_msg.lower()
                )
                
                if is_expected_error:
                    logger.debug(
                        f"LLM 사용 불가 (예상된 오류): Bedrock use case form 미제출. "
                        f"Embedding 기반 폴백으로 전환합니다."
                    )
                else:
                    logger.warning(f"요청 분석 중 오류 발생: {e}")
                
                # LLM 실패 시 하이브리드 폴백: Embedding → Keywords
                user_request = state.get("user_request", "")
                
                agent_type = None
                reasoning = ""
                confidence = 0.5
                method = "keyword_fallback"
                
                # 1. Embedding 기반 의도 분류 시도
                try:
                    from ..utils.intent_classifier import (
                        classify_intent_hybrid,
                        map_intent_to_agent_type
                    )
                    
                    intent, classify_method, intent_confidence = classify_intent_hybrid(user_request)
                    if intent:
                        mapped_agent_type = map_intent_to_agent_type(intent)
                        if mapped_agent_type:
                            agent_type = mapped_agent_type
                            reasoning = f"Embedding 기반 폴백 (LLM 실패): {intent} → {agent_type}"
                            confidence = intent_confidence
                            method = f"embedding_{classify_method}"
                            logger.info(f"Embedding 기반 의도 분류 성공: {intent} → {agent_type} (신뢰도: {confidence:.2f})")
                except ImportError:
                    logger.warning("Embedding 기반 의도 분류 모듈을 사용할 수 없습니다. 키워드 폴백 사용.")
                except Exception as embed_error:
                    logger.warning(f"Embedding 기반 의도 분류 실패: {embed_error}. 키워드 폴백 사용.")
                
                # 2. Embedding 실패 시 키워드 기반 폴백
                if not agent_type:
                    user_request_lower = user_request.lower()
                    
                    if any(kw in user_request_lower for kw in ["ec2", "인스턴스", "서버", "ami", "ec2 정보", "ec2정보"]):
                        agent_type = "ec2"
                        reasoning = f"키워드 기반 폴백 (LLM 실패): EC2 관련 - {str(e)[:100]}"
                        confidence = 0.8
                    elif any(kw in user_request_lower for kw in ["s3", "버킷", "객체", "스토리지"]):
                        agent_type = "s3"
                        reasoning = f"키워드 기반 폴백 (LLM 실패): S3 관련 - {str(e)[:100]}"
                        confidence = 0.8
                    elif any(kw in user_request_lower for kw in ["vpc", "서브넷", "네트워크"]):
                        agent_type = "vpc"
                        reasoning = f"키워드 기반 폴백 (LLM 실패): VPC 관련 - {str(e)[:100]}"
                        confidence = 0.8
                    else:
                        agent_type = AgentType.GENERAL.value
                        reasoning = f"키워드 기반 폴백 (LLM 실패): 일반 요청 - {str(e)[:100]}"
                        confidence = 0.5
                
                state["next_agent"] = agent_type
                state["routing_result"] = {
                    "agent_type": agent_type,
                    "reasoning": reasoning,
                    "confidence": confidence,
                    "context": {"method": method, "error": str(e)}
                }
                state["context"] = {"error": str(e), "confidence": confidence, "method": method}
            
            return state
        
        # 2. Agent 라우팅 노드
        def route_to_agent(state: AgentState) -> AgentState:
            """분석 결과에 따라 적절한 Agent로 라우팅"""
            next_agent = state.get('next_agent', 'general')
            logger.info(f"Agent 라우팅: {next_agent}")
            
            try:
                agent_type = next_agent
                
                user_request = state.get('user_request', '')
                context = state.get('context', {})
                
                if agent_type == AgentType.EC2.value:
                    result = asyncio.run(self._handle_ec2_request(user_request, context))
                elif agent_type == AgentType.S3.value:
                    result = asyncio.run(self._handle_s3_request(user_request, context))
                elif agent_type == AgentType.VPC.value:
                    result = asyncio.run(self._handle_vpc_request(user_request, context))
                else:
                    result = self._handle_general_request(user_request, context)
                
                state['agent_result'] = result
                
            except Exception as e:
                logger.error(f"Agent 라우팅 중 오류: {e}")
                state['agent_result'] = {
                    "success": False,
                    "error": str(e),
                    "message": "Agent 라우팅 중 오류가 발생했습니다."
                }
            
            return state
        
        # 3. 응답 생성 노드
        def generate_response(state: AgentState) -> AgentState:
            """최종 응답 생성"""
            logger.info("최종 응답 구성 중...")
            
            try:
                agent_result = state.get('agent_result', {})
                thread_id = state.get('thread_id', 'default')
                next_agent = state.get('next_agent', 'general')
                context = state.get('context', {})
                
                if agent_result and agent_result.get("success"):
                    final_message = agent_result.get('response', '처리가 완료되었습니다.')
                    state['final_response'] = final_message
                    
                    # 대화 기록에 응답 추가
                    self._add_to_history(
                        thread_id, 
                        "assistant", 
                        final_message, 
                        {
                            "agent_used": next_agent,
                            "confidence": context.get('confidence', 0.5)
                        }
                    )
                    
                    # AIMessage 추가
                    state['messages'].append(AIMessage(content=final_message))
                else:
                    error_msg = agent_result.get("error", "알 수 없는 오류") if agent_result else "처리 결과를 가져올 수 없습니다."
                    final_message = f"죄송합니다. 요청 처리 중 오류가 발생했습니다: {error_msg}"
                    state['final_response'] = final_message
                    
                    # 대화 기록에 오류 응답 추가
                    self._add_to_history(
                        thread_id, 
                        "assistant", 
                        final_message, 
                        {
                            "agent_used": next_agent,
                            "error": error_msg
                        }
                    )
                    
                    state['messages'].append(AIMessage(content=final_message))
                
            except Exception as e:
                logger.error(f"응답 생성 중 오류: {e}")
                error_message = "응답 생성 중 오류가 발생했습니다."
                state['final_response'] = error_message
                state['messages'].append(AIMessage(content=error_message))
            
            return state
        
        # 4. 그래프 구성
        graph = StateGraph(AgentState)
        
        # 노드 추가
        graph.add_node("analyze_request", analyze_request)
        graph.add_node("route_to_agent", route_to_agent)
        graph.add_node("generate_response", generate_response)
        
        # 엣지 추가
        graph.add_edge(START, "analyze_request")
        graph.add_edge("analyze_request", "route_to_agent")
        graph.add_edge("route_to_agent", "generate_response")
        graph.add_edge("generate_response", END)
        
        # 체크포인터 없이 컴파일 (상태 관리 문제 해결)
        return graph.compile()
    
    async def _handle_ec2_request(self, user_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """EC2 Agent로 요청 처리"""
        logger.info("EC2 Agent로 요청 처리 중...")
        
        try:
            # Agent Factory를 통해 EC2 Agent 가져오기
            ec2_agent = self.agent_factory.create_agent(
                agent_type="ec2",
                settings=self.settings,
                aws_access_key=self.aws_access_key,
                aws_secret_key=self.aws_secret_key,
                region=self.region
            )
            
            if not ec2_agent:
                return {
                    "success": False,
                    "error": "EC2 Agent를 생성할 수 없습니다.",
                    "message": "EC2 Agent 초기화에 실패했습니다."
                }
            
            # EC2 Agent에게 요청 전달 (비동기)
            result = await ec2_agent.process_request(user_request)
            return result
            
        except Exception as e:
            logger.error(f"EC2 Agent 처리 중 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "EC2 Agent 처리 중 오류가 발생했습니다."
            }
    
    async def _handle_s3_request(self, user_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """S3 Agent로 요청 처리"""
        logger.info("S3 Agent로 요청 처리 중...")
        
        try:
            # S3 Agent 직접 생성 (AgentFactory 대신)
            from .s3_agent import S3Agent
            s3_agent = S3Agent(
                settings=self.settings,
                aws_access_key=self.aws_access_key,
                aws_secret_key=self.aws_secret_key,
                region=self.region
            )
            
            # S3 Agent에게 요청 전달
            result = await s3_agent.process_request(user_request)
            return result
            
        except Exception as e:
            logger.error(f"S3 Agent 처리 중 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "S3 Agent 처리 중 오류가 발생했습니다."
            }
    
    async def _handle_vpc_request(self, user_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """VPC Agent로 요청 처리"""
        logger.info("VPC Agent로 요청 처리 중...")
        
        try:
            # VPC Agent 직접 생성 (AgentFactory 대신)
            from .vpc_agent import VPCAgent
            vpc_agent = VPCAgent(
                settings=self.settings,
                aws_access_key=self.aws_access_key,
                aws_secret_key=self.aws_secret_key,
                region=self.region
            )
            
            # VPC Agent에게 요청 전달
            result = await vpc_agent.process_request(user_request)
            return result
            
        except Exception as e:
            logger.error(f"VPC Agent 처리 중 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "VPC Agent 처리 중 오류가 발생했습니다."
            }
    
    def _handle_general_request(self, user_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """일반 요청 처리 (규칙 기반)"""
        logger.info("일반 요청 처리 중...")
        
        try:
            # 규칙 기반 응답 생성
            response = self._generate_general_response(user_request)
            
            return {
                "success": True,
                "response": response,
                "agent_type": "general"
            }
            
        except Exception as e:
            logger.error(f"일반 요청 처리 중 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "요청 처리 중 오류가 발생했습니다."
            }
    
    def _generate_general_response(self, user_request: str) -> str:
        """일반 응답 생성 (규칙 기반 + LLM)"""
        user_request_lower = user_request.lower()
        
        # 설정에서 현재 사용 중인 모델 정보 가져오기
        model_name = self._get_model_display_name()
        
        # 규칙 기반 응답 (시스템 관련 질문)
        if any(keyword in user_request_lower for keyword in ["안녕", "hello", "hi"]):
            return f"안녕하세요! {model_name}를 사용한 Multi-Agent System입니다. EC2, S3, VPC 관리나 일반적인 질문에 도움을 드릴 수 있습니다."
        elif any(keyword in user_request_lower for keyword in ["도움", "help", "도움말"]):
            return "Multi-Agent System에서 다음과 같은 도움을 드릴 수 있습니다:\n- EC2 인스턴스 관리\n- S3 버킷 및 객체 관리\n- VPC 네트워크 설정\n- 일반적인 AWS 관련 질문"
        elif any(keyword in user_request_lower for keyword in ["설명", "소개", "introduction"]):
            return f"이 시스템은 {model_name} 모델을 기반으로 한 Multi-Agent System입니다. Supervisor Agent가 사용자 요청을 분석하여 적절한 전문 Agent(EC2, S3, VPC)로 라우팅합니다."
        
        # 일반적인 질문은 LLM을 사용하여 응답 생성
        try:
            return self._generate_llm_response(user_request)
        except Exception as e:
            logger.error(f"LLM 응답 생성 실패: {e}")
            # LLM 실패 시 기본 응답
            return f"죄송합니다. '{user_request}'에 대한 응답을 생성하는 중 오류가 발생했습니다. EC2, S3, VPC 관련 질문이나 다른 도움이 필요하시면 말씀해주세요."
    
    def _generate_llm_response(self, user_request: str) -> str:
        """LLM을 사용하여 일반 질문에 대한 응답 생성"""
        try:
            # 시스템 프롬프트 설정
            system_prompt = """당신은 친절하고 도움이 되는 AI 어시스턴트입니다. 
사용자의 질문에 정확하고 유용한 답변을 제공하세요. 
AWS 관련 질문이 아닌 일반적인 질문에도 자연스럽게 답변하세요.
답변은 간결하고 명확하게 작성하세요."""
            
            # LLM 호출 (동기 방식)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_request)
            ]
            
            response = self.llm.invoke(messages)
            
            # 응답 추출
            if hasattr(response, 'content'):
                return response.content
            elif isinstance(response, str):
                return response
            else:
                return str(response)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"LLM 응답 생성 중 오류: {error_msg}")
            
            # 모델이 chat을 지원하지 않는 경우 Titan Text로 폴백 시도
            if ("does not support chat" in error_msg.lower() or 
                "use case details" in error_msg.lower() or 
                "resourcenotfoundexception" in error_msg.lower()):
                logger.warning(f"현재 모델이 chat을 지원하지 않습니다. Titan Text 모델로 폴백 시도...")
                return self._try_fallback_to_titan(user_request)
            
            raise
    
    def _try_fallback_to_titan(self, user_request: str) -> str:
        """대체 모델로 폴백하여 응답 생성 (Titan Text는 chat 미지원이므로 다른 방법 사용)"""
        try:
            # Titan Text는 chat을 지원하지 않으므로, 대신 Meta Llama를 시도
            # 또는 다른 chat을 지원하는 모델 시도
            fallback_models = [
                "meta.llama3-8b-instruct-v1:0",
                "meta.llama3-70b-instruct-v1:0",
                "amazon.titan-text-express-v1:0",
            ]
            
            last_error = None
            for fallback_model_id in fallback_models:
                try:
                    logger.info(f"폴백 모델 시도: {fallback_model_id}")
                    
                    # Llama 모델인지 확인
                    is_llama = "llama" in fallback_model_id.lower()
                    is_titan = "titan" in fallback_model_id.lower()
                    
                    if is_llama:
                        # Llama 모델은 Claude와 유사하게 설정
                        fallback_llm = ChatBedrock(
                            model_id=fallback_model_id,
                            aws_access_key_id=self.aws_access_key or self.settings.aws_access_key_id,
                            aws_secret_access_key=self.aws_secret_key or self.settings.aws_secret_access_key,
                            region_name=self.region or self.settings.aws_region,
                            model_kwargs={
                                "temperature": self.settings.bedrock_temperature,
                                "max_gen_len": min(self.settings.bedrock_max_tokens, 2048),
                            }
                        )
                    else:
                        # Titan Text는 completion 모델이므로 ChatBedrock으로는 사용 불가
                        logger.warning(f"{fallback_model_id}는 chat을 지원하지 않습니다. 건너뜁니다.")
                        continue
                    
                    # 시스템 프롬프트 설정
                    system_prompt = """당신은 친절하고 도움이 되는 AI 어시스턴트입니다. 
사용자의 질문에 정확하고 유용한 답변을 제공하세요. 
AWS 관련 질문이 아닌 일반적인 질문에도 자연스럽게 답변하세요.
답변은 간결하고 명확하게 작성하세요."""
                    
                    messages = [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=user_request)
                    ]
                    
                    response = fallback_llm.invoke(messages)
                    
                    # 응답 추출
                    if hasattr(response, 'content'):
                        logger.info(f"폴백 모델 {fallback_model_id} 성공")
                        return response.content
                    elif isinstance(response, str):
                        return response
                    else:
                        return str(response)
                        
                except Exception as model_error:
                    logger.warning(f"폴백 모델 {fallback_model_id} 실패: {model_error}")
                    last_error = model_error
                    continue
            
            # 모든 폴백 모델 실패
            raise last_error if last_error else Exception("모든 폴백 모델 시도 실패")
                
        except Exception as fallback_error:
            logger.error(f"모든 폴백 모델 실패: {fallback_error}")
            return (
                f"죄송합니다. AI 모델 응답 생성에 실패했습니다.\n\n"
                f"원인: Claude 모델 사용을 위해 AWS Bedrock에서 Anthropic use case form 제출이 필요합니다.\n\n"
                f"해결 방법:\n"
                f"1. AWS 콘솔에서 Bedrock > Model access에서 Anthropic 모델에 대한 use case를 제출하세요.\n"
                f"   - https://console.aws.amazon.com/bedrock/ 에서 Model access 페이지로 이동\n"
                f"   - Anthropic Claude 모델을 선택하고 use case를 제출하세요.\n"
                f"2. 또는 환경변수 MULTI_AGENT_BEDROCK_MODEL_ID를 다른 chat을 지원하는 모델로 변경하세요.\n"
                f"   - 예: meta.llama3-8b-instruct-v1:0\n\n"
                f"현재 질문: {user_request}"
            )
    
    def _get_model_display_name(self) -> str:
        """설정에서 현재 사용 중인 모델의 표시 이름을 가져옵니다"""
        try:
            if self.settings.llm_provider == "openai":
                return self.settings.openai_model
            elif self.settings.llm_provider == "bedrock":
                # Bedrock 모델 ID에서 친숙한 이름 추출
                model_id = self.settings.bedrock_model_id
                # 모델 ID를 더 읽기 쉬운 형식으로 변환
                if "claude" in model_id.lower():
                    return "Amazon Bedrock Claude"
                elif "titan" in model_id.lower():
                    return "Amazon Titan"
                elif "llama" in model_id.lower():
                    return "Amazon Bedrock Llama"
                else:
                    # 모델 ID의 마지막 부분만 추출 (예: "anthropic.claude-3-haiku-20240307-v1:0" -> "Claude 3 Haiku")
                    parts = model_id.split(".")
                    if len(parts) > 1:
                        model_part = parts[-1].split(":")[0]
                        # 버전 정보 제거하고 읽기 쉽게 변환
                        model_name = model_part.replace("-", " ").title()
                        return f"Amazon Bedrock {model_name}"
                    return model_id
            else:
                return "AI 모델"
        except Exception as e:
            logger.warning(f"모델 이름 가져오기 실패: {e}, 기본값 사용")
            return "AI 모델"
    
    def _add_to_history(self, thread_id: str, message_type: str, content: str, metadata: Dict[str, Any] = None):
        """대화 기록에 메시지 추가"""
        if thread_id not in self.conversation_history:
            self.conversation_history[thread_id] = []
        
        self.conversation_history[thread_id].append({
            "type": message_type,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        })
        
        # 최대 기록 수 제한
        max_history = 100
        if len(self.conversation_history[thread_id]) > max_history:
            self.conversation_history[thread_id] = self.conversation_history[thread_id][-max_history:]
    
    def process_request(self, user_request: str, thread_id: str = "default") -> Dict[str, Any]:
        """사용자 요청을 처리하는 메인 메서드 (LangGraph 사용)"""
        logger.info(f"새로운 요청 처리 시작: {user_request[:50]}...")
        
        try:
            # 대화 기록에 사용자 요청 추가
            self._add_to_history(thread_id, "user", user_request)
            
            # 초기 상태 설정
            initial_state = AgentState(
                messages=[HumanMessage(content=user_request)],
                next_agent=None,
                agent_result=None,
                user_request=user_request,
                context=None,
                timestamp=datetime.now().isoformat(),
                thread_id=thread_id,
                routing_result=None,
                llm_output=None,
                final_response=None
            )
            
            # LangGraph 실행 (체크포인터 없이)
            final_state = self.graph.invoke(initial_state)
            
            # 결과 반환
            agent_result = final_state.get("agent_result", {})
            context = final_state.get("context", {})
            
            if agent_result and agent_result.get("success"):
                result = {
                    "success": True,
                    "response": final_state.get("final_response", "처리가 완료되었습니다."),
                    "agent_used": final_state.get("next_agent", "general"),
                    "context": context,
                    "confidence": context.get("confidence", 0.5),
                    "routing_info": final_state.get("routing_result")
                }
            else:
                error_msg = agent_result.get("error", "알 수 없는 오류") if agent_result else "처리 결과를 가져올 수 없습니다."
                result = {
                    "success": False,
                    "response": final_state.get("final_response", "요청 처리 중 오류가 발생했습니다."),
                    "error": error_msg,
                    "agent_used": final_state.get("next_agent", "general"),
                    "routing_info": final_state.get("routing_result")
                }
            
            logger.info("요청 처리 완료")
            return result
            
        except Exception as e:
            logger.error(f"요청 처리 중 오류 발생: {e}")
            error_response = "요청 처리 중 시스템 오류가 발생했습니다."
            
            # 대화 기록에 시스템 오류 추가
            self._add_to_history(thread_id, "system_error", error_response, {"error": str(e)})
            
            return {
                "success": False,
                "error": str(e),
                "message": error_response
            }
    
    async def process_request_async(self, user_request: str, thread_id: str = "default") -> Dict[str, Any]:
        """비동기 요청 처리 (LangGraph 사용)"""
        logger.info(f"비동기 요청 처리 시작: {user_request[:50]}...")
        
        try:
            # 대화 기록에 사용자 요청 추가
            self._add_to_history(thread_id, "user", user_request)
            
            # 초기 상태 설정
            initial_state = AgentState(
                messages=[HumanMessage(content=user_request)],
                next_agent=None,
                agent_result=None,
                user_request=user_request,
                context=None,
                timestamp=datetime.now().isoformat(),
                thread_id=thread_id,
                routing_result=None,
                llm_output=None,
                final_response=None
            )
            
            # LangGraph 비동기 실행 (체크포인터 없이)
            final_state = await self.graph.ainvoke(initial_state)
            
            # 결과 반환 (동기 버전과 동일)
            agent_result = final_state.get("agent_result", {})
            context = final_state.get("context", {})
            
            if agent_result and agent_result.get("success"):
                result = {
                    "success": True,
                    "response": final_state.get("final_response", "처리가 완료되었습니다."),
                    "agent_used": final_state.get("next_agent", "general"),
                    "context": context,
                    "confidence": context.get("confidence", 0.5),
                    "routing_info": final_state.get("routing_result")
                }
            else:
                error_msg = agent_result.get("error", "알 수 없는 오류") if agent_result else "처리 결과를 가져올 수 없습니다."
                result = {
                    "success": False,
                    "response": final_state.get("final_response", "요청 처리 중 오류가 발생했습니다."),
                    "error": error_msg,
                    "agent_used": final_state.get("next_agent", "general"),
                    "routing_info": final_state.get("routing_result")
                }
            
            logger.info("비동기 요청 처리 완료")
            return result
            
        except Exception as e:
            logger.error(f"비동기 요청 처리 중 오류 발생: {e}")
            error_response = "요청 처리 중 시스템 오류가 발생했습니다."
            
            # 대화 기록에 시스템 오류 추가
            self._add_to_history(thread_id, "system_error", error_response, {"error": str(e)})
            
            return {
                "success": False,
                "error": str(e),
                "message": error_response
            }
    
    def stream_request(self, user_request: str, thread_id: str = "default"):
        """스트리밍 요청 처리 (LangGraph 사용)"""
        logger.info(f"스트리밍 요청 처리 시작: {user_request[:50]}...")
        
        try:
            # 초기 상태 설정
            initial_state = AgentState(
                messages=[HumanMessage(content=user_request)],
                next_agent=None,
                agent_result=None,
                user_request=user_request,
                context=None,
                timestamp=datetime.now().isoformat(),
                thread_id=thread_id,
                routing_result=None,
                llm_output=None,
                final_response=None
            )
            
            # LangGraph 스트리밍 실행 (체크포인터 없이)
            for chunk in self.graph.stream(initial_state):
                yield chunk
                
        except Exception as e:
            logger.error(f"스트리밍 요청 처리 중 오류 발생: {e}")
            yield {
                "error": str(e),
                "message": "스트리밍 처리 중 오류가 발생했습니다."
            }
    
    def get_conversation_history(self, thread_id: str = "default") -> List[Dict[str, Any]]:
        """대화 기록 조회"""
        try:
            return self.conversation_history.get(thread_id, [])
            
        except Exception as e:
            logger.error(f"대화 기록 조회 중 오류: {e}")
            return []
    
    def get_graph_state(self, thread_id: str = "default") -> Dict[str, Any]:
        """LangGraph 상태 조회 (체크포인터 없이 사용)"""
        try:
            # 체크포인터를 사용하지 않으므로 빈 상태 반환
            return {"state": {}, "metadata": {}}
            
        except Exception as e:
            logger.error(f"그래프 상태 조회 중 오류: {e}")
            return {"error": str(e)}
    
    def clear_thread(self, thread_id: str = "default") -> bool:
        """특정 스레드의 대화 기록 및 상태 초기화"""
        try:
            if thread_id in self.conversation_history:
                del self.conversation_history[thread_id]
            
            # LangGraph 상태도 초기화 (메모리에서 제거)
            config = {"configurable": {"thread_id": thread_id}}
            # 현재 LangGraph에서는 직접적인 초기화 메서드가 없으므로 새로 시작
            
            logger.info(f"스레드 {thread_id} 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"스레드 초기화 중 오류: {e}")
            return False
