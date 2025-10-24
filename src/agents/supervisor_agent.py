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


class AgentState(dict):
    """Agent 상태를 관리하는 클래스 (LangGraph 0.0.8 호환)"""
    def __init__(self, **kwargs):
        super().__init__()
        self.update({
            "messages": kwargs.get("messages", []),
            "next_agent": kwargs.get("next_agent"),
            "agent_result": kwargs.get("agent_result"),
            "user_request": kwargs.get("user_request"),
            "context": kwargs.get("context"),
            "timestamp": kwargs.get("timestamp"),
            "thread_id": kwargs.get("thread_id"),
            "routing_result": kwargs.get("routing_result"),
            "llm_output": kwargs.get("llm_output"),
            "final_response": kwargs.get("final_response")
        })


class SupervisorAgent:
    """LangGraph를 사용한 Supervisor Agent"""
    
    def __init__(self, settings, aws_access_key: str = None, aws_secret_key: str = None, region: str = "us-east-1"):
        # LLM Provider 설정에 따라 LLM 초기화 (Bedrock 전용)
        self.llm = ChatBedrock(
            model_id=settings.bedrock_model_id,
            temperature=settings.bedrock_temperature,
            max_tokens=settings.bedrock_max_tokens,
            aws_access_key_id=aws_access_key or settings.aws_access_key_id,
            aws_secret_access_key=aws_secret_key or settings.aws_secret_access_key,
            region_name=region or settings.aws_region
        )
        logger.info(f"Bedrock LLM 초기화 완료: {settings.bedrock_model_id}")
        
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
            """사용자 요청을 분석하여 적절한 Agent 결정"""
            logger.info("사용자 요청 분석 중...")
            
            try:
                # 규칙 기반 Agent 선택 (임베딩 모델 대신)
                user_request = state["user_request"].lower()
                
                if any(keyword in user_request for keyword in ["ec2", "aws", "인스턴스", "서버", "클라우드", "ami", "보안그룹"]):
                    agent_type = "ec2"
                    reasoning = "EC2 관련 키워드가 감지되어 EC2 Agent로 라우팅합니다."
                    confidence = 0.9
                elif any(keyword in user_request for keyword in ["s3", "버킷", "객체", "파일", "스토리지", "업로드", "다운로드"]):
                    agent_type = "s3"
                    reasoning = "S3 관련 키워드가 감지되어 S3 Agent로 라우팅합니다."
                    confidence = 0.9
                elif any(keyword in user_request for keyword in ["vpc", "서브넷", "보안그룹", "네트워크", "cidr", "가용영역"]):
                    agent_type = "vpc"
                    reasoning = "VPC 관련 키워드가 감지되어 VPC Agent로 라우팅합니다."
                    confidence = 0.9
                else:
                    agent_type = "general"
                    reasoning = "일반적인 대화로 판단되어 General Agent로 라우팅합니다."
                    confidence = 0.7
                
                analysis = {
                    "agent_type": agent_type,
                    "reasoning": reasoning,
                    "confidence": confidence,
                    "context": {"method": "rule_based", "keywords_found": True}
                }
                
                state["routing_result"] = analysis
                state["next_agent"] = agent_type
                state["context"] = analysis.get("context", {})
                state["context"]["confidence"] = confidence
                
                logger.info(f"요청 분석 완료: {agent_type} - {reasoning}")
                
            except Exception as e:
                logger.error(f"요청 분석 중 오류 발생: {e}")
                state["next_agent"] = AgentType.GENERAL.value
                state["context"] = {"error": str(e), "confidence": 0.5}
            
            return state
        
        # 2. Agent 라우팅 노드
        def route_to_agent(state: AgentState) -> AgentState:
            """분석 결과에 따라 적절한 Agent로 라우팅"""
            logger.info(f"Agent 라우팅: {state['next_agent']}")
            
            try:
                agent_type = state['next_agent']
                
                if agent_type == AgentType.EC2.value:
                    result = self._handle_ec2_request(state['user_request'], state['context'])
                elif agent_type == AgentType.S3.value:
                    result = asyncio.run(self._handle_s3_request(state['user_request'], state['context']))
                elif agent_type == AgentType.VPC.value:
                    result = asyncio.run(self._handle_vpc_request(state['user_request'], state['context']))
                else:
                    result = self._handle_general_request(state['user_request'], state['context'])
                
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
                if state['agent_result'] and state['agent_result'].get("success"):
                    final_message = state['agent_result'].get('response', '처리가 완료되었습니다.')
                    state['final_response'] = final_message
                    
                    # 대화 기록에 응답 추가
                    self._add_to_history(
                        state['thread_id'], 
                        "assistant", 
                        final_message, 
                        {
                            "agent_used": state['next_agent'],
                            "confidence": state['context'].get('confidence', 0.5) if state['context'] else 0.5
                        }
                    )
                    
                    # AIMessage 추가
                    state['messages'].append(AIMessage(content=final_message))
                else:
                    error_msg = state['agent_result'].get("error", "알 수 없는 오류") if state['agent_result'] else "처리 결과를 가져올 수 없습니다."
                    final_message = f"죄송합니다. 요청 처리 중 오류가 발생했습니다: {error_msg}"
                    state['final_response'] = final_message
                    
                    # 대화 기록에 오류 응답 추가
                    self._add_to_history(
                        state['thread_id'], 
                        "assistant", 
                        final_message, 
                        {
                            "agent_used": state['next_agent'],
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
        
        return graph.compile(checkpointer=self.memory)
    
    def _handle_ec2_request(self, user_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
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
            
            # EC2 Agent에게 요청 전달
            result = ec2_agent.process_request(user_request)
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
        """규칙 기반 일반 응답 생성"""
        user_request_lower = user_request.lower()
        
        if any(keyword in user_request_lower for keyword in ["안녕", "hello", "hi"]):
            return "안녕하세요! Amazon Titan Text Embeddings V2를 사용한 Multi-Agent System입니다. EC2, S3, VPC 관리나 일반적인 질문에 도움을 드릴 수 있습니다."
        elif any(keyword in user_request_lower for keyword in ["도움", "help", "도움말"]):
            return "Multi-Agent System에서 다음과 같은 도움을 드릴 수 있습니다:\n- EC2 인스턴스 관리\n- S3 버킷 및 객체 관리\n- VPC 네트워크 설정\n- 일반적인 AWS 관련 질문"
        elif any(keyword in user_request_lower for keyword in ["설명", "소개", "introduction"]):
            return "이 시스템은 Amazon Titan Text Embeddings V2 모델을 기반으로 한 Multi-Agent System입니다. Supervisor Agent가 사용자 요청을 분석하여 적절한 전문 Agent(EC2, S3, VPC)로 라우팅합니다."
        else:
            return "안녕하세요! Multi-Agent System에 오신 것을 환영합니다. EC2, S3, VPC 관련 질문이나 일반적인 도움이 필요하시면 언제든 말씀해주세요."
    
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
            
            # LangGraph 실행
            config = {"configurable": {"thread_id": thread_id}}
            final_state = self.graph.invoke(initial_state, config=config)
            
            # 결과 반환
            if final_state["agent_result"] and final_state["agent_result"].get("success"):
                result = {
                    "success": True,
                    "response": final_state["final_response"],
                    "agent_used": final_state["next_agent"],
                    "context": final_state["context"],
                    "confidence": final_state["context"].get("confidence", 0.5) if final_state["context"] else 0.5,
                    "routing_info": final_state["routing_result"]
                }
            else:
                error_msg = final_state["agent_result"].get("error", "알 수 없는 오류") if final_state["agent_result"] else "처리 결과를 가져올 수 없습니다."
                result = {
                    "success": False,
                    "response": final_state["final_response"],
                    "error": error_msg,
                    "agent_used": final_state["next_agent"],
                    "routing_info": final_state["routing_result"]
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
            
            # LangGraph 비동기 실행
            config = {"configurable": {"thread_id": thread_id}}
            final_state = await self.graph.ainvoke(initial_state, config=config)
            
            # 결과 반환 (동기 버전과 동일)
            if final_state["agent_result"] and final_state["agent_result"].get("success"):
                result = {
                    "success": True,
                    "response": final_state["final_response"],
                    "agent_used": final_state["next_agent"],
                    "context": final_state["context"],
                    "confidence": final_state["context"].get("confidence", 0.5) if final_state["context"] else 0.5,
                    "routing_info": final_state["routing_result"]
                }
            else:
                error_msg = final_state["agent_result"].get("error", "알 수 없는 오류") if final_state["agent_result"] else "처리 결과를 가져올 수 없습니다."
                result = {
                    "success": False,
                    "response": final_state["final_response"],
                    "error": error_msg,
                    "agent_used": final_state["next_agent"],
                    "routing_info": final_state["routing_result"]
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
            
            # LangGraph 스트리밍 실행
            config = {"configurable": {"thread_id": thread_id}}
            for chunk in self.graph.stream(initial_state, config=config):
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
        """LangGraph 상태 조회"""
        try:
            config = {"configurable": {"thread_id": thread_id}}
            state = self.graph.get_state(config)
            return {"state": state.values, "metadata": state.metadata}
            
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
