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
    
    @staticmethod
    def _extract_json_from_text(text: str) -> Optional[str]:
        """텍스트에서 JSON을 추출하는 헬퍼 함수
        
        마크다운 코드 블록을 제거하고 중첩된 JSON을 올바르게 추출합니다.
        """
        import re
        
        # 1. 마크다운 코드 블록 제거 (```json ... ``` 또는 ``` ... ```)
        text = re.sub(r'```(?:json)?\s*\n?(.*?)\n?```', r'\1', text, flags=re.DOTALL)
        
        # 2. 중첩된 JSON 추출을 위한 스택 기반 파싱
        json_start = -1
        brace_count = 0
        
        for i, char in enumerate(text):
            if char == '{':
                if json_start == -1:
                    json_start = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and json_start != -1:
                    # 완전한 JSON 객체 찾음
                    json_str = text[json_start:i+1]
                    # 유효한 JSON인지 확인
                    try:
                        json.loads(json_str)
                        return json_str
                    except json.JSONDecodeError:
                        # 다음 JSON 객체 찾기 위해 계속
                        json_start = -1
                        brace_count = 0
        
        # 3. 스택 기반 파싱이 실패한 경우, 첫 번째 { 부터 마지막 } 까지 시도
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_str = text[first_brace:last_brace+1]
            try:
                json.loads(json_str)
                return json_str
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _safe_extract_llm_content(self, response: Any) -> str:
        """LLM 응답에서 content를 안전하게 추출하는 헬퍼 함수
        
        다양한 LLM 응답 형식을 처리하고, 오류 발생 시 상세한 정보를 로깅합니다.
        """
        import traceback
        try:
            # 응답 타입과 내용을 먼저 로깅
            logger.info(f"{self.get_agent_type()} Agent - LLM 응답 타입: {type(response)}")
            logger.info(f"{self.get_agent_type()} Agent - LLM 응답 repr: {repr(response)[:500]}")
            
            # 1. content 속성이 있는 경우
            if hasattr(response, 'content'):
                try:
                    content = response.content
                    logger.info(f"{self.get_agent_type()} Agent - content 타입: {type(content)}")
                    if content is None:
                        logger.warning(f"{self.get_agent_type()} Agent - LLM 응답 content가 None입니다.")
                        return ""
                    return str(content)
                except (AttributeError, KeyError) as e:
                    logger.error(f"{self.get_agent_type()} Agent - content 속성 접근 오류: {e}, 타입: {type(e).__name__}")
                    logger.error(f"{self.get_agent_type()} Agent - 스택 트레이스: {traceback.format_exc()}")
                    # 계속 진행
            
            # 2. 문자열인 경우
            if isinstance(response, str):
                return response
            
            # 3. dict 형태인 경우 - 안전하게 처리
            if isinstance(response, dict):
                logger.info(f"{self.get_agent_type()} Agent - dict 키 목록: {list(response.keys())}")
                try:
                    # content 키 확인
                    if 'content' in response:
                        content = response['content']
                        if content is not None:
                            return str(content)
                    
                    # text 키 확인
                    if 'text' in response:
                        text = response['text']
                        if text is not None:
                            return str(text)
                    
                    # dict 전체를 문자열로 변환
                    logger.debug(f"{self.get_agent_type()} Agent - LLM 응답이 dict 형태입니다: {list(response.keys())}")
                    return json.dumps(response, ensure_ascii=False)
                except (KeyError, TypeError) as e:
                    logger.error(f"{self.get_agent_type()} Agent - dict 처리 중 오류: {e}, 타입: {type(e).__name__}")
                    logger.error(f"{self.get_agent_type()} Agent - dict 키: {list(response.keys()) if isinstance(response, dict) else 'N/A'}")
                    logger.error(f"{self.get_agent_type()} Agent - 스택 트레이스: {traceback.format_exc()}")
                    # dict 전체를 문자열로 변환 시도
                    try:
                        return json.dumps(response, ensure_ascii=False)
                    except:
                        return str(response)
            
            # 4. 기타 경우 - 문자열로 변환 시도
            try:
                response_str = str(response)
                logger.debug(f"{self.get_agent_type()} Agent - LLM 응답을 문자열로 변환: {type(response).__name__}")
                return response_str
            except Exception as e:
                logger.debug(f"{self.get_agent_type()} Agent - 문자열 변환 실패: {e}")
                return f"응답 처리 중 오류 발생: {type(response).__name__}"
            
        except Exception as e:
            logger.error(f"{self.get_agent_type()} Agent - LLM 응답 content 추출 중 오류: {e}")
            logger.error(f"{self.get_agent_type()} Agent - 오류 타입: {type(e).__name__}")
            logger.error(f"{self.get_agent_type()} Agent - 응답 객체 타입: {type(response)}")
            logger.error(f"{self.get_agent_type()} Agent - 응답 객체: {response}")
            logger.error(f"{self.get_agent_type()} Agent - 전체 스택 트레이스: {traceback.format_exc()}")
            # 최후의 수단: 전체 응답을 문자열로 변환
            try:
                return str(response)
            except:
                return f"응답 처리 중 오류 발생: {str(e)}"
    
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
                logger.debug(f"{self.get_agent_type()} Agent - LLM 호출 시작 (생각 노드)")
                
                response = self.llm.invoke(messages)
                
                logger.info(f"{self.get_agent_type()} Agent - LLM 응답 수신 완료, 타입: {type(response).__name__}")
                logger.info(f"{self.get_agent_type()} Agent - LLM 응답 객체: {response}")
                logger.info(f"{self.get_agent_type()} Agent - LLM 응답 속성: {dir(response) if hasattr(response, '__dict__') else 'N/A'}")
                
                # 안전한 content 추출
                thinking_text = self._safe_extract_llm_content(response)
                
                logger.info(f"{self.get_agent_type()} Agent - 추출된 thinking 텍스트 길이: {len(thinking_text)}")
                
                state["thinking_result"] = {
                    "thinking": thinking_text,
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.info(f"{self.get_agent_type()} Agent - 생각 완료")
                
            except Exception as e:
                import traceback
                logger.error(f"생각 노드 실행 중 오류: {e}")
                logger.error(f"생각 노드 오류 타입: {type(e).__name__}")
                logger.error(f"생각 노드 전체 스택 트레이스: {traceback.format_exc()}")
                state["thinking_result"] = {
                    "thinking": f"요청 분석 중 오류 발생: {str(e)}",
                    "error": str(e),
                    "error_type": type(e).__name__
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
응답은 반드시 순수 JSON 형식으로만 제공해야 합니다. 마크다운 코드 블록(```json ... ```)이나 다른 텍스트 없이 JSON만 반환하세요.

응답 형식:
{{{{
    "action": "액션명",
    "parameters": {{{{
        "파라미터명": "값"
    }}}},
    "reasoning": "추출 이유"
}}}}

중요: 응답은 순수 JSON만 포함해야 하며, 마크다운 코드 블록이나 설명 텍스트를 포함하지 마세요."""),
                    ("human", "사용자 요청: {user_request}\n생각 결과: {thinking}")
                ])
                
                thinking_text = thinking_result.get("thinking", "")
                messages = extract_prompt.format_messages(
                    user_request=user_request,
                    thinking=thinking_text
                )
                logger.debug(f"{self.get_agent_type()} Agent - LLM 호출 시작 (파라미터 추출 노드)")
                response = self.llm.invoke(messages)
                
                logger.debug(f"{self.get_agent_type()} Agent - LLM 응답 수신 완료, 타입: {type(response).__name__}")
                logger.debug(f"{self.get_agent_type()} Agent - LLM 응답 객체: {response}")
                logger.debug(f"{self.get_agent_type()} Agent - LLM 응답 속성: {dir(response) if hasattr(response, '__dict__') else 'N/A'}")
                
                # 안전한 content 추출
                response_text = self._safe_extract_llm_content(response)
                
                logger.debug(f"{self.get_agent_type()} Agent - 추출된 응답 텍스트 길이: {len(response_text)}")
                logger.debug(f"{self.get_agent_type()} Agent - 추출된 응답 텍스트 (처음 500자): {response_text[:500]}")
                
                # JSON 추출 시도
                try:
                    # 개선된 JSON 추출 로직 사용
                    json_str = self._extract_json_from_text(response_text)
                    
                    if json_str is None:
                        logger.warning(f"{self.get_agent_type()} Agent - JSON을 찾을 수 없습니다. 원본 응답: {response_text[:500]}")
                        raise ValueError(f"JSON을 찾을 수 없습니다. 원본 응답: {response_text[:200]}")
                    
                    logger.debug(f"{self.get_agent_type()} Agent - 추출된 JSON 문자열: {json_str[:200]}")
                    
                    extracted_data = json.loads(json_str)
                    action = extracted_data.get("action")
                    parameters = extracted_data.get("parameters", {})
                    
                    state["action"] = action
                    state["extracted_parameters"] = parameters
                    
                    logger.info(f"{self.get_agent_type()} Agent - 파라미터 추출 완료: action={action}")
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"파라미터 추출 JSON 파싱 실패: {e}")
                    logger.warning(f"JSON 파싱 오류 위치: line {e.lineno}, column {e.colno if hasattr(e, 'colno') else 'N/A'}")
                    logger.debug(f"원본 LLM 응답: {response_text}")
                    logger.debug(f"추출 시도한 JSON 문자열: {self._extract_json_from_text(response_text) if response_text else None}")
                    state["extracted_parameters"] = {}
                    state["action"] = None
                except ValueError as e:
                    logger.warning(f"파라미터 추출 값 오류: {e}")
                    logger.debug(f"원본 LLM 응답: {response_text}")
                    state["extracted_parameters"] = {}
                    state["action"] = None
                except KeyError as e:
                    logger.warning(f"파라미터 추출 키 오류: {e}")
                    logger.debug(f"원본 LLM 응답: {response_text}")
                    state["extracted_parameters"] = {}
                    state["action"] = None
                
            except Exception as e:
                logger.error(f"파라미터 추출 노드 실행 중 오류: {e}")
                logger.error(f"파라미터 추출 노드 오류 타입: {type(e).__name__}")
                logger.debug(f"파라미터 추출 노드 오류 상세: {str(e)}", exc_info=True)
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
                
                logger.debug(f"{self.get_agent_type()} Agent - LLM 호출 시작 (재질문 노드)")
                response = self.llm.invoke(messages)
                
                logger.debug(f"{self.get_agent_type()} Agent - LLM 응답 수신 완료, 타입: {type(response).__name__}")
                logger.debug(f"{self.get_agent_type()} Agent - LLM 응답 객체: {response}")
                logger.debug(f"{self.get_agent_type()} Agent - LLM 응답 속성: {dir(response) if hasattr(response, '__dict__') else 'N/A'}")
                
                # 안전한 content 추출
                reask_message = self._safe_extract_llm_content(response)
                
                logger.debug(f"{self.get_agent_type()} Agent - 추출된 재질문 메시지 길이: {len(reask_message)}")
                
                state["reask_message"] = reask_message
                
                logger.info(f"{self.get_agent_type()} Agent - 재질문 생성 완료")
                
            except Exception as e:
                logger.error(f"재질문 노드 실행 중 오류: {e}")
                logger.error(f"재질문 노드 오류 타입: {type(e).__name__}")
                logger.debug(f"재질문 노드 오류 상세: {str(e)}", exc_info=True)
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
                    
                    logger.debug(f"{self.get_agent_type()} Agent - LLM 호출 시작 (위험 작업 체크 노드)")
                    response = self.llm.invoke(messages)
                    
                    logger.debug(f"{self.get_agent_type()} Agent - LLM 응답 수신 완료, 타입: {type(response).__name__}")
                    
                    # 안전한 content 추출
                    confirmation_message = self._safe_extract_llm_content(response)
                    
                    logger.debug(f"{self.get_agent_type()} Agent - 추출된 확인 메시지 길이: {len(confirmation_message)}")
                    
                    state["confirmation_message"] = confirmation_message
                    
                    logger.info(f"{self.get_agent_type()} Agent - 위험 작업 감지: {action}")
                else:
                    state["is_dangerous_action"] = False
                    state["dangerous_action_confirmed"] = True  # 위험하지 않으면 바로 실행 가능
                
            except Exception as e:
                logger.error(f"위험 작업 체크 노드 실행 중 오류: {e}")
                logger.error(f"위험 작업 체크 노드 오류 타입: {type(e).__name__}")
                logger.debug(f"위험 작업 체크 노드 오류 상세: {str(e)}", exc_info=True)
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
                import re
                action_result = state.get("action_result", {})
                verification_passed = state.get("verification_passed", False)
                
                if verification_passed and action_result.get("success"):
                    # action_result에 message가 있으면 우선 사용
                    if action_result.get("message"):
                        state["final_response"] = action_result.get("message")
                    else:
                        # LLM을 사용하여 간결한 응답 생성
                        action = state.get("action", "")
                        response_prompt = ChatPromptTemplate.from_messages([
                            ("system", """당신은 AWS 리소스 관리 전문가입니다. 
작업 결과를 사용자에게 간결하고 명확하게 알려주세요.
중요: 
- JSON 형식이 아닌 일반 텍스트로만 응답하세요
- reasoning 태그나 JSON 구조를 사용하지 마세요
- 2-3문장으로 간결하게 작성하세요
- 핵심 정보(인스턴스 ID, 상태 등)만 포함하세요"""),
                            ("human", "작업: {action}\n작업 결과: {result}\n\n위 결과를 바탕으로 간결하고 명확한 응답을 생성하세요. 2-3문장으로만 작성하세요.")
                        ])
                        
                        messages = response_prompt.format_messages(
                            action=action,
                            result=json.dumps(action_result, ensure_ascii=False, indent=2)
                        )
                        
                        logger.debug(f"{self.get_agent_type()} Agent - LLM 호출 시작 (응답 생성 노드)")
                        response = self.llm.invoke(messages)
                        
                        logger.debug(f"{self.get_agent_type()} Agent - LLM 응답 수신 완료, 타입: {type(response).__name__}")
                        
                        # 안전한 content 추출
                        final_response = self._safe_extract_llm_content(response)
                        
                        # reasoning 태그나 JSON 구조가 포함되어 있으면 제거
                        # <reasoning>...</reasoning> 태그 제거
                        final_response = re.sub(r'<reasoning>.*?</reasoning>', '', final_response, flags=re.DOTALL)
                        # JSON 구조 제거 (중괄호로 시작하는 부분)
                        json_match = re.search(r'\{.*\}', final_response, re.DOTALL)
                        if json_match:
                            # JSON 부분만 제거하고 나머지 텍스트만 사용
                            final_response = final_response.replace(json_match.group(0), '').strip()
                        
                        logger.debug(f"{self.get_agent_type()} Agent - 추출된 최종 응답 길이: {len(final_response)}")
                        
                        state["final_response"] = final_response.strip()
                else:
                    # 실패 응답
                    error_msg = action_result.get("error", "알 수 없는 오류")
                    state["final_response"] = f"작업 처리 중 오류가 발생했습니다: {error_msg}"
                
                logger.info(f"{self.get_agent_type()} Agent - 응답 생성 완료")
                
            except Exception as e:
                logger.error(f"응답 생성 노드 실행 중 오류: {e}")
                logger.error(f"응답 생성 노드 오류 타입: {type(e).__name__}")
                logger.debug(f"응답 생성 노드 오류 상세: {str(e)}", exc_info=True)
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

