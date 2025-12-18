"""
Base Agent with LangGraph Workflow
모든 서브 에이전트의 기본 클래스로 LangGraph 기반 워크플로우를 제공합니다.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, TypedDict
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# LangGraph imports
from langgraph.graph import StateGraph, START, END

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SubAgentState(TypedDict):
    """서브 에이전트 상태를 관리하는 TypedDict (LangGraph 호환)"""
    user_request: str
    context: Dict[str, Any]
    thinking_result: Optional[Dict[str, Any]]
    extracted_parameters: Optional[Dict[str, Any]]
    missing_parameters: List[str]
    reask_message: Optional[str]
    is_dangerous_action: bool
    dangerous_action_confirmed: bool
    confirmation_message: Optional[str]
    action_result: Optional[Dict[str, Any]]
    verification_result: Optional[Dict[str, Any]]
    verification_passed: bool
    final_response: Optional[str]
    needs_clarification: bool
    action: Optional[str]
    messages: List[BaseMessage]


class BaseAgent(ABC):
    """LangGraph 기반 Base Agent 클래스"""
    
    def __init__(self, settings, aws_access_key: str = None, aws_secret_key: str = None, region: str = "us-east-1"):
        # Settings 객체가 MultiAgentSettings인지 확인하고 적절히 처리
        if hasattr(settings, 'multi_agent'):
            multi_agent_settings = settings.multi_agent
        else:
            multi_agent_settings = settings
        
        self.settings = multi_agent_settings
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.region = region
        
        # LLM 초기화
        model_id = multi_agent_settings.bedrock_model_id
        
        # Claude 모델인지 확인
        is_claude = "claude" in model_id.lower()
        
        # Inference Profile 사용 여부 확인
        use_inference_profile = getattr(multi_agent_settings, 'bedrock_use_inference_profile', False)
        # Inference Profile ID 형식 감지 (리전.프로바이더.모델 형식 또는 특정 패턴)
        is_inference_profile_id = (
            use_inference_profile or 
            "." in model_id and len(model_id.split(".")) >= 3 or
            "claude-haiku-4-5" in model_id.lower() or
            "claude-sonnet-4-5" in model_id.lower() or
            "claude-opus-4-5" in model_id.lower()
        )
        
        if is_claude:
            # Claude 모델은 model_kwargs만 사용 (최상위 레벨 파라미터 제거)
            # Inference Profile을 사용하는 경우 model_id를 그대로 사용
            # ChatBedrock은 Inference Profile ID를 자동으로 감지하여 처리합니다
            self.llm = ChatBedrock(
                model_id=model_id,
                aws_access_key_id=aws_access_key or multi_agent_settings.aws_access_key_id,
                aws_secret_access_key=aws_secret_key or multi_agent_settings.aws_secret_access_key,
                region_name=region or multi_agent_settings.aws_region,
                model_kwargs={
                    "temperature": multi_agent_settings.bedrock_temperature,
                    "max_tokens": multi_agent_settings.bedrock_max_tokens,
                }
            )
            if is_inference_profile_id:
                logger.info(f"⚠️ {self.get_agent_type()} Agent - Inference Profile 모드로 사용: {model_id}")
        else:
            self.llm = ChatBedrock(
                model_id=model_id,
                temperature=multi_agent_settings.bedrock_temperature,
                max_tokens=multi_agent_settings.bedrock_max_tokens,
                aws_access_key_id=aws_access_key or multi_agent_settings.aws_access_key_id,
                aws_secret_access_key=aws_secret_key or multi_agent_settings.aws_secret_access_key,
                region_name=region or multi_agent_settings.aws_region
            )
        
        logger.info(f"{self.get_agent_type()} Agent - Bedrock LLM 초기화 완료: {model_id}")
        
        # JSON 파서 설정
        self.json_parser = JsonOutputParser()
        
        # LangGraph 워크플로우 구성
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """LangGraph 워크플로우 구성"""
        
        # 1. 생각 노드
        def think_node(state: SubAgentState) -> SubAgentState:
            """LLM을 사용한 사고 과정"""
            logger.info(f"{self.get_agent_type()} Agent - 생각 노드 실행 중...")
            
            try:
                user_request = state.get("user_request", "")
                system_prompt = self.get_system_prompt()
                
                thinking_prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt + "\n\n사용자의 요청을 분석하고 어떤 작업을 수행해야 할지 생각해보세요."),
                    ("human", "사용자 요청: {user_request}")
                ])
                
                messages = thinking_prompt.format_messages(user_request=user_request)
                response = self.llm.invoke(messages)
                
                thinking_text = response.content if hasattr(response, 'content') else str(response)
                
                state["thinking_result"] = {
                    "thinking": thinking_text,
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.info(f"{self.get_agent_type()} Agent - 생각 완료")
                
            except Exception as e:
                logger.error(f"생각 노드 실행 중 오류: {e}")
                state["thinking_result"] = {
                    "thinking": f"요청 분석 중 오류 발생: {str(e)}",
                    "error": str(e)
                }
            
            return state
        
        # 2. 파라미터 추출 노드
        def extract_parameters_node(state: SubAgentState) -> SubAgentState:
            """파라미터 추출"""
            logger.info(f"{self.get_agent_type()} Agent - 파라미터 추출 노드 실행 중...")
            
            try:
                user_request = state.get("user_request", "")
                thinking_result = state.get("thinking_result", {})
                
                extract_prompt = ChatPromptTemplate.from_messages([
                    ("system", self.get_system_prompt() + f"""

지원하는 액션 목록:
{json.dumps(self.get_available_actions(), ensure_ascii=False, indent=2)}

사용자 요청에서 액션과 필요한 파라미터를 추출하세요.
응답은 다음 JSON 형식으로 제공해야 합니다:
{{
    "action": "액션명",
    "parameters": {{
        "파라미터명": "값"
    }},
    "reasoning": "추출 이유"
}}"""),
                    ("human", "사용자 요청: {user_request}\n생각 결과: {thinking}")
                ])
                
                thinking_text = thinking_result.get("thinking", "")
                messages = extract_prompt.format_messages(
                    user_request=user_request,
                    thinking=thinking_text
                )
                response = self.llm.invoke(messages)
                
                response_text = response.content if hasattr(response, 'content') else str(response)
                
                # JSON 추출 시도
                try:
                    import re
                    json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(0)
                    
                    extracted_data = json.loads(response_text)
                    action = extracted_data.get("action")
                    parameters = extracted_data.get("parameters", {})
                    
                    state["action"] = action
                    state["extracted_parameters"] = parameters
                    
                    logger.info(f"{self.get_agent_type()} Agent - 파라미터 추출 완료: action={action}")
                    
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.warning(f"파라미터 추출 파싱 실패: {e}")
                    state["extracted_parameters"] = {}
                    state["action"] = None
                
            except Exception as e:
                logger.error(f"파라미터 추출 노드 실행 중 오류: {e}")
                state["extracted_parameters"] = {}
                state["action"] = None
            
            return state
        
        # 3. 파라미터 체크 노드
        def check_parameters_node(state: SubAgentState) -> SubAgentState:
            """필수 파라미터 체크"""
            logger.info(f"{self.get_agent_type()} Agent - 파라미터 체크 노드 실행 중...")
            
            try:
                action = state.get("action")
                parameters = state.get("extracted_parameters", {})
                
                if not action:
                    state["needs_clarification"] = True
                    state["missing_parameters"] = ["action"]
                    return state
                
                required_params = self.get_required_parameters(action)
                missing = [param for param in required_params if param not in parameters or not parameters.get(param)]
                
                if missing:
                    state["needs_clarification"] = True
                    state["missing_parameters"] = missing
                    logger.info(f"{self.get_agent_type()} Agent - 부족한 파라미터: {missing}")
                else:
                    state["needs_clarification"] = False
                    state["missing_parameters"] = []
                
            except Exception as e:
                logger.error(f"파라미터 체크 노드 실행 중 오류: {e}")
                state["needs_clarification"] = True
                state["missing_parameters"] = []
            
            return state
        
        # 4. 재질문 노드
        def reask_node(state: SubAgentState) -> SubAgentState:
            """재질문 생성"""
            logger.info(f"{self.get_agent_type()} Agent - 재질문 노드 실행 중...")
            
            try:
                missing_params = state.get("missing_parameters", [])
                action = state.get("action", "작업")
                
                reask_prompt = ChatPromptTemplate.from_messages([
                    ("system", self.get_system_prompt() + "\n\n부족한 정보를 사용자에게 친절하게 질문하세요."),
                    ("human", "작업: {action}\n부족한 파라미터: {missing_params}\n\n사용자에게 질문할 메시지를 생성하세요.")
                ])
                
                messages = reask_prompt.format_messages(
                    action=action,
                    missing_params=", ".join(missing_params)
                )
                response = self.llm.invoke(messages)
                
                reask_message = response.content if hasattr(response, 'content') else str(response)
                state["reask_message"] = reask_message
                
                logger.info(f"{self.get_agent_type()} Agent - 재질문 생성 완료")
                
            except Exception as e:
                logger.error(f"재질문 노드 실행 중 오류: {e}")
                state["reask_message"] = f"다음 정보가 필요합니다: {', '.join(state.get('missing_parameters', []))}"
            
            return state
        
        # 5. 위험 작업 체크 노드
        def check_risk_node(state: SubAgentState) -> SubAgentState:
            """위험 작업 감지 및 확인 요청 생성"""
            logger.info(f"{self.get_agent_type()} Agent - 위험 작업 체크 노드 실행 중...")
            
            try:
                action = state.get("action")
                dangerous_actions = self.get_dangerous_actions()
                
                if action in dangerous_actions:
                    state["is_dangerous_action"] = True
                    state["dangerous_action_confirmed"] = False
                    
                    # 확인 메시지 생성
                    confirm_prompt = ChatPromptTemplate.from_messages([
                        ("system", self.get_system_prompt() + "\n\n위험한 작업에 대해 사용자에게 확인을 요청하는 메시지를 생성하세요. 작업의 위험성과 영향 범위를 명확히 설명하세요."),
                        ("human", "작업: {action}\n파라미터: {parameters}\n\n확인 요청 메시지를 생성하세요.")
                    ])
                    
                    parameters = state.get("extracted_parameters", {})
                    messages = confirm_prompt.format_messages(
                        action=action,
                        parameters=json.dumps(parameters, ensure_ascii=False)
                    )
                    response = self.llm.invoke(messages)
                    
                    confirmation_message = response.content if hasattr(response, 'content') else str(response)
                    state["confirmation_message"] = confirmation_message
                    
                    logger.info(f"{self.get_agent_type()} Agent - 위험 작업 감지: {action}")
                else:
                    state["is_dangerous_action"] = False
                    state["dangerous_action_confirmed"] = True  # 위험하지 않으면 바로 실행 가능
                
            except Exception as e:
                logger.error(f"위험 작업 체크 노드 실행 중 오류: {e}")
                state["is_dangerous_action"] = False
                state["dangerous_action_confirmed"] = True
            
            return state
        
        # 6. 위험 작업 확인 노드
        def confirm_dangerous_action_node(state: SubAgentState) -> SubAgentState:
            """위험 작업 사용자 확인 처리"""
            logger.info(f"{self.get_agent_type()} Agent - 위험 작업 확인 노드 실행 중...")
            
            # 사용자 확인은 Supervisor Agent를 통해 처리되므로
            # 여기서는 상태만 확인
            confirmed = state.get("dangerous_action_confirmed", False)
            
            if not confirmed:
                logger.info(f"{self.get_agent_type()} Agent - 위험 작업 확인 대기 중...")
            
            return state
        
        # 7. 작업 실행 노드
        def execute_action_node(state: SubAgentState) -> SubAgentState:
            """작업 실행"""
            logger.info(f"{self.get_agent_type()} Agent - 작업 실행 노드 실행 중...")
            
            try:
                action = state.get("action")
                parameters = state.get("extracted_parameters", {})
                
                if not action:
                    state["action_result"] = {
                        "success": False,
                        "error": "액션이 지정되지 않았습니다."
                    }
                    return state
                
                # 실제 작업 실행
                result = self.execute_action(action, parameters)
                state["action_result"] = result
                
                logger.info(f"{self.get_agent_type()} Agent - 작업 실행 완료: {action}")
                
            except Exception as e:
                logger.error(f"작업 실행 노드 실행 중 오류: {e}")
                state["action_result"] = {
                    "success": False,
                    "error": str(e)
                }
            
            return state
        
        # 8. 결과 검증 노드
        def verify_result_node(state: SubAgentState) -> SubAgentState:
            """실행 결과 검증"""
            logger.info(f"{self.get_agent_type()} Agent - 결과 검증 노드 실행 중...")
            
            try:
                action = state.get("action")
                parameters = state.get("extracted_parameters", {})
                action_result = state.get("action_result", {})
                
                if not action_result.get("success"):
                    state["verification_passed"] = False
                    state["verification_result"] = {
                        "passed": False,
                        "reason": "작업 실행 실패"
                    }
                    return state
                
                # 결과 검증
                verification = self.verify_action_result(action, parameters, action_result)
                state["verification_result"] = verification
                state["verification_passed"] = verification.get("passed", False)
                
                logger.info(f"{self.get_agent_type()} Agent - 결과 검증 완료: {verification.get('passed')}")
                
            except Exception as e:
                logger.error(f"결과 검증 노드 실행 중 오류: {e}")
                state["verification_passed"] = False
                state["verification_result"] = {
                    "passed": False,
                    "error": str(e)
                }
            
            return state
        
        # 9. 재시도/롤백 노드
        def retry_or_rollback_node(state: SubAgentState) -> SubAgentState:
            """재시도 또는 롤백 처리"""
            logger.info(f"{self.get_agent_type()} Agent - 재시도/롤백 노드 실행 중...")
            
            # 현재는 간단하게 오류 메시지만 설정
            # 향후 재시도 로직 추가 가능
            verification_result = state.get("verification_result", {})
            action_result = state.get("action_result", {})
            
            if not state.get("verification_passed", False):
                error_msg = verification_result.get("reason", "결과 검증 실패")
                state["final_response"] = f"작업 실행 후 검증에 실패했습니다: {error_msg}"
            
            return state
        
        # 10. 응답 생성 노드
        def generate_response_node(state: SubAgentState) -> SubAgentState:
            """최종 응답 생성"""
            logger.info(f"{self.get_agent_type()} Agent - 응답 생성 노드 실행 중...")
            
            try:
                action_result = state.get("action_result", {})
                verification_passed = state.get("verification_passed", False)
                
                if verification_passed and action_result.get("success"):
                    # 성공 응답 생성
                    response_prompt = ChatPromptTemplate.from_messages([
                        ("system", self.get_system_prompt() + "\n\n작업이 성공적으로 완료되었습니다. 사용자에게 친절하게 결과를 알려주세요."),
                        ("human", "작업 결과: {result}\n\n사용자에게 전달할 응답을 생성하세요.")
                    ])
                    
                    messages = response_prompt.format_messages(
                        result=json.dumps(action_result, ensure_ascii=False, indent=2)
                    )
                    response = self.llm.invoke(messages)
                    final_response = response.content if hasattr(response, 'content') else str(response)
                    
                    state["final_response"] = final_response
                else:
                    # 실패 응답
                    error_msg = action_result.get("error", "알 수 없는 오류")
                    state["final_response"] = f"작업 처리 중 오류가 발생했습니다: {error_msg}"
                
                logger.info(f"{self.get_agent_type()} Agent - 응답 생성 완료")
                
            except Exception as e:
                logger.error(f"응답 생성 노드 실행 중 오류: {e}")
                state["final_response"] = "응답 생성 중 오류가 발생했습니다."
            
            return state
        
        # 그래프 구성
        graph = StateGraph(SubAgentState)
        
        # 노드 추가
        graph.add_node("think", think_node)
        graph.add_node("extract_parameters", extract_parameters_node)
        graph.add_node("check_parameters", check_parameters_node)
        graph.add_node("reask", reask_node)
        graph.add_node("check_risk", check_risk_node)
        graph.add_node("confirm_dangerous_action", confirm_dangerous_action_node)
        graph.add_node("execute_action", execute_action_node)
        graph.add_node("verify_result", verify_result_node)
        graph.add_node("retry_or_rollback", retry_or_rollback_node)
        graph.add_node("generate_response", generate_response_node)
        
        # 엣지 추가
        graph.add_edge(START, "think")
        graph.add_edge("think", "extract_parameters")
        graph.add_edge("extract_parameters", "check_parameters")
        
        # 조건부 엣지: 파라미터 체크 후
        def should_reask(state: SubAgentState) -> str:
            """재질문 필요 여부 결정"""
            if state.get("needs_clarification", False):
                return "reask"
            return "check_risk"
        
        graph.add_conditional_edges(
            "check_parameters",
            should_reask,
            {
                "reask": "reask",
                "check_risk": "check_risk"
            }
        )
        
        # 재질문 후에는 다시 파라미터 추출로 (사용자 응답을 받은 후)
        graph.add_edge("reask", END)  # 재질문은 Supervisor를 통해 처리되므로 여기서 종료
        
        # 위험 작업 체크 후
        def should_confirm(state: SubAgentState) -> str:
            """위험 작업 확인 필요 여부 결정"""
            if state.get("is_dangerous_action", False) and not state.get("dangerous_action_confirmed", False):
                return "confirm_dangerous_action"
            return "execute_action"
        
        graph.add_conditional_edges(
            "check_risk",
            should_confirm,
            {
                "confirm_dangerous_action": "confirm_dangerous_action",
                "execute_action": "execute_action"
            }
        )
        
        # 위험 작업 확인 후 실행
        graph.add_edge("confirm_dangerous_action", "execute_action")
        graph.add_edge("execute_action", "verify_result")
        
        # 결과 검증 후
        def should_retry(state: SubAgentState) -> str:
            """재시도/롤백 필요 여부 결정"""
            if not state.get("verification_passed", False):
                return "retry_or_rollback"
            return "generate_response"
        
        graph.add_conditional_edges(
            "verify_result",
            should_retry,
            {
                "retry_or_rollback": "retry_or_rollback",
                "generate_response": "generate_response"
            }
        )
        
        graph.add_edge("retry_or_rollback", "generate_response")
        graph.add_edge("generate_response", END)
        
        return graph.compile()
    
    async def process_request(self, user_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """사용자 요청을 처리하는 메인 메서드 (LangGraph 사용)"""
        logger.info(f"{self.get_agent_type()} Agent 요청 처리 시작: {user_request[:50]}...")
        
        try:
            # 초기 상태 설정
            initial_state = SubAgentState(
                user_request=user_request,
                context=context or {},
                thinking_result=None,
                extracted_parameters=None,
                missing_parameters=[],
                reask_message=None,
                is_dangerous_action=False,
                dangerous_action_confirmed=False,
                confirmation_message=None,
                action_result=None,
                verification_result=None,
                verification_passed=False,
                final_response=None,
                needs_clarification=False,
                action=None,
                messages=[HumanMessage(content=user_request)]
            )
            
            # LangGraph 실행
            final_state = await self.graph.ainvoke(initial_state)
            
            # 결과 반환
            if final_state.get("needs_clarification"):
                return {
                    "success": False,
                    "needs_clarification": True,
                    "reask_message": final_state.get("reask_message"),
                    "missing_parameters": final_state.get("missing_parameters", [])
                }
            
            if final_state.get("is_dangerous_action") and not final_state.get("dangerous_action_confirmed"):
                return {
                    "success": False,
                    "needs_confirmation": True,
                    "confirmation_message": final_state.get("confirmation_message"),
                    "action": final_state.get("action"),
                    "parameters": final_state.get("extracted_parameters", {})
                }
            
            return {
                "success": final_state.get("verification_passed", False),
                "response": final_state.get("final_response", "처리가 완료되었습니다."),
                "agent_type": self.get_agent_type(),
                "action_result": final_state.get("action_result"),
                "verification_result": final_state.get("verification_result")
            }
            
        except Exception as e:
            logger.error(f"{self.get_agent_type()} Agent 요청 처리 중 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"{self.get_agent_type()} 요청 처리 중 시스템 오류가 발생했습니다."
            }
    
    # 추상 메서드 정의
    @abstractmethod
    def get_agent_type(self) -> str:
        """에이전트 타입 반환"""
        pass
    
    def get_system_prompt(self) -> str:
        """시스템 프롬프트 (기본 제공, 오버라이드 가능)"""
        return f"""당신은 AWS {self.get_agent_type().upper()} 리소스를 관리하는 전문 에이전트입니다.
사용자의 요청을 분석하여 적절한 작업을 수행하고 결과를 사용자 친화적으로 제공합니다."""
    
    @abstractmethod
    def get_required_parameters(self, action: str) -> List[str]:
        """액션별 필수 파라미터 목록"""
        pass
    
    def get_dangerous_actions(self) -> List[str]:
        """위험 작업 목록 (기본 제공, 오버라이드 가능)"""
        return []
    
    @abstractmethod
    def execute_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """실제 작업 실행"""
        pass
    
    def verify_action_result(self, action: str, parameters: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """결과 검증 (기본 제공, 오버라이드 가능)"""
        # 기본 검증: 성공 여부만 확인
        return {
            "passed": result.get("success", False),
            "reason": "기본 검증 통과" if result.get("success") else "작업 실행 실패"
        }
    
    @abstractmethod
    def get_available_actions(self) -> List[str]:
        """지원하는 액션 목록"""
        pass

