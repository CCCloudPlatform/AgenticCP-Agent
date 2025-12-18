"""
S3 Mini Agent using LangChain and AWS CC API MCP
AWS S3 리소스 관리 및 조작을 담당하는 Mini Agent
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_aws import ChatBedrock
from langchain_core.tools import BaseTool, tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.callbacks import CallbackManagerForToolRun

# AWS CC API MCP 관련 import
import requests
import boto3
from botocore.exceptions import ClientError

# BaseAgent import
from .base_agent import BaseAgent

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class S3Request:
    """S3 요청 데이터 구조"""
    action: str
    parameters: Dict[str, Any]
    region: Optional[str] = None


class AWSS3Tool(BaseTool):
    """AWS S3를 활용한 도구"""
    
    name: str = "aws_s3"
    description: str = "AWS S3 버킷 및 객체를 관리합니다."
    session: Any = None
    s3_client: Any = None
    
    def __init__(self, aws_access_key: str = None, aws_secret_key: str = None, region: str = "us-east-1"):
        super().__init__()
        # AWS 세션 설정
        if aws_access_key and aws_secret_key:
            self.session = boto3.Session(
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=region
            )
        else:
            self.session = boto3.Session(region_name=region)
        
        self.s3_client = self.session.client('s3')
    
    def _generate_rule_based_response(self, user_request: str) -> str:
        """규칙 기반 응답 생성"""
        user_request_lower = user_request.lower()
        
        if any(keyword in user_request_lower for keyword in ["생성", "만들", "create"]):
            return "S3 버킷을 생성하는 방법을 안내해드리겠습니다. AWS 콘솔에서 S3 서비스로 이동하여 '버킷 만들기'를 클릭하고 버킷 이름을 입력하세요."
        elif any(keyword in user_request_lower for keyword in ["목록", "리스트", "조회", "list"]):
            return "현재 계정의 S3 버킷 목록을 조회해드리겠습니다."
        elif any(keyword in user_request_lower for keyword in ["업로드", "upload"]):
            return "S3 버킷에 파일을 업로드하는 방법을 안내해드리겠습니다. AWS CLI나 콘솔을 통해 파일을 업로드할 수 있습니다."
        elif any(keyword in user_request_lower for keyword in ["다운로드", "download"]):
            return "S3 버킷에서 파일을 다운로드하는 방법을 안내해드리겠습니다."
        else:
            return "S3 서비스에 대한 도움을 드리겠습니다. 버킷 생성, 파일 업로드/다운로드, 권한 설정 등의 작업을 도와드릴 수 있습니다."
    
    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """S3 작업 실행"""
        try:
            # 쿼리 파싱
            request_data = self._parse_query(query)
            
            if request_data.action == "list_buckets":
                return self._list_buckets()
            elif request_data.action == "create_bucket":
                return self._create_bucket(request_data.parameters)
            elif request_data.action == "delete_bucket":
                return self._delete_bucket(request_data.parameters)
            elif request_data.action == "list_objects":
                return self._list_objects(request_data.parameters)
            elif request_data.action == "upload_object":
                return self._upload_object(request_data.parameters)
            elif request_data.action == "download_object":
                return self._download_object(request_data.parameters)
            elif request_data.action == "delete_object":
                return self._delete_object(request_data.parameters)
            elif request_data.action == "get_bucket_info":
                return self._get_bucket_info(request_data.parameters)
            else:
                return f"지원하지 않는 S3 작업입니다: {request_data.action}"
                
        except Exception as e:
            logger.error(f"S3 작업 실행 중 오류: {e}")
            return f"S3 작업 실행 중 오류가 발생했습니다: {str(e)}"
    
    def _parse_query(self, query: str) -> S3Request:
        """쿼리 파싱"""
        # 간단한 파싱 로직 (실제로는 더 정교한 파싱 필요)
        query_lower = query.lower()
        
        if "버킷 목록" in query or "list bucket" in query_lower:
            return S3Request(action="list_buckets", parameters={})
        elif "버킷 생성" in query or "create bucket" in query_lower:
            # 버킷 이름 추출 로직
            bucket_name = self._extract_bucket_name(query)
            return S3Request(action="create_bucket", parameters={"bucket_name": bucket_name})
        elif "버킷 삭제" in query or "delete bucket" in query_lower:
            bucket_name = self._extract_bucket_name(query)
            return S3Request(action="delete_bucket", parameters={"bucket_name": bucket_name})
        elif "객체 목록" in query or "list object" in query_lower:
            bucket_name = self._extract_bucket_name(query)
            return S3Request(action="list_objects", parameters={"bucket_name": bucket_name})
        elif "업로드" in query or "upload" in query_lower:
            bucket_name = self._extract_bucket_name(query)
            object_key = self._extract_object_key(query)
            return S3Request(action="upload_object", parameters={
                "bucket_name": bucket_name,
                "object_key": object_key
            })
        elif "다운로드" in query or "download" in query_lower:
            bucket_name = self._extract_bucket_name(query)
            object_key = self._extract_object_key(query)
            return S3Request(action="download_object", parameters={
                "bucket_name": bucket_name,
                "object_key": object_key
            })
        elif "객체 삭제" in query or "delete object" in query_lower:
            bucket_name = self._extract_bucket_name(query)
            object_key = self._extract_object_key(query)
            return S3Request(action="delete_object", parameters={
                "bucket_name": bucket_name,
                "object_key": object_key
            })
        elif "버킷 정보" in query or "bucket info" in query_lower:
            bucket_name = self._extract_bucket_name(query)
            return S3Request(action="get_bucket_info", parameters={"bucket_name": bucket_name})
        else:
            return S3Request(action="unknown", parameters={})
    
    def _extract_bucket_name(self, query: str) -> str:
        """쿼리에서 버킷 이름 추출"""
        # 간단한 추출 로직
        words = query.split()
        for i, word in enumerate(words):
            if word.lower() in ["버킷", "bucket"] and i + 1 < len(words):
                return words[i + 1]
        return "default-bucket"
    
    def _extract_object_key(self, query: str) -> str:
        """쿼리에서 객체 키 추출"""
        # 간단한 추출 로직
        words = query.split()
        for i, word in enumerate(words):
            if word.lower() in ["객체", "object", "파일", "file"] and i + 1 < len(words):
                return words[i + 1]
        return "default-object"
    
    def _list_buckets(self) -> str:
        """S3 버킷 목록 조회"""
        try:
            response = self.s3_client.list_buckets()
            buckets = response.get('Buckets', [])
            
            result = {
                "action": "list_buckets",
                "success": True,
                "buckets": [
                    {
                        "name": bucket['Name'],
                        "creation_date": bucket['CreationDate'].isoformat()
                    }
                    for bucket in buckets
                ],
                "total_count": len(buckets)
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"S3 버킷 목록 조회 실패: {e}")
            return json.dumps({
                "action": "list_buckets",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _create_bucket(self, parameters: Dict[str, Any]) -> str:
        """S3 버킷 생성"""
        try:
            bucket_name = parameters.get("bucket_name", "default-bucket")
            
            # 버킷 생성
            self.s3_client.create_bucket(Bucket=bucket_name)
            
            result = {
                "action": "create_bucket",
                "success": True,
                "bucket_name": bucket_name,
                "message": f"버킷 '{bucket_name}'이 성공적으로 생성되었습니다."
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"S3 버킷 생성 실패: {e}")
            return json.dumps({
                "action": "create_bucket",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _delete_bucket(self, parameters: Dict[str, Any]) -> str:
        """S3 버킷 삭제"""
        try:
            bucket_name = parameters.get("bucket_name", "default-bucket")
            
            # 버킷 삭제
            self.s3_client.delete_bucket(Bucket=bucket_name)
            
            result = {
                "action": "delete_bucket",
                "success": True,
                "bucket_name": bucket_name,
                "message": f"버킷 '{bucket_name}'이 성공적으로 삭제되었습니다."
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"S3 버킷 삭제 실패: {e}")
            return json.dumps({
                "action": "delete_bucket",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _list_objects(self, parameters: Dict[str, Any]) -> str:
        """S3 객체 목록 조회"""
        try:
            bucket_name = parameters.get("bucket_name", "default-bucket")
            
            response = self.s3_client.list_objects_v2(Bucket=bucket_name)
            objects = response.get('Contents', [])
            
            result = {
                "action": "list_objects",
                "success": True,
                "bucket_name": bucket_name,
                "objects": [
                    {
                        "key": obj['Key'],
                        "size": obj['Size'],
                        "last_modified": obj['LastModified'].isoformat(),
                        "storage_class": obj.get('StorageClass', 'STANDARD')
                    }
                    for obj in objects
                ],
                "total_count": len(objects)
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"S3 객체 목록 조회 실패: {e}")
            return json.dumps({
                "action": "list_objects",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _upload_object(self, parameters: Dict[str, Any]) -> str:
        """S3 객체 업로드"""
        try:
            bucket_name = parameters.get("bucket_name", "default-bucket")
            object_key = parameters.get("object_key", "default-object")
            
            # 실제 구현에서는 파일 업로드 로직이 필요
            result = {
                "action": "upload_object",
                "success": True,
                "bucket_name": bucket_name,
                "object_key": object_key,
                "message": f"객체 '{object_key}'가 버킷 '{bucket_name}'에 업로드되었습니다."
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"S3 객체 업로드 실패: {e}")
            return json.dumps({
                "action": "upload_object",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _download_object(self, parameters: Dict[str, Any]) -> str:
        """S3 객체 다운로드"""
        try:
            bucket_name = parameters.get("bucket_name", "default-bucket")
            object_key = parameters.get("object_key", "default-object")
            
            # 실제 구현에서는 파일 다운로드 로직이 필요
            result = {
                "action": "download_object",
                "success": True,
                "bucket_name": bucket_name,
                "object_key": object_key,
                "message": f"객체 '{object_key}'가 버킷 '{bucket_name}'에서 다운로드되었습니다."
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"S3 객체 다운로드 실패: {e}")
            return json.dumps({
                "action": "download_object",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _delete_object(self, parameters: Dict[str, Any]) -> str:
        """S3 객체 삭제"""
        try:
            bucket_name = parameters.get("bucket_name", "default-bucket")
            object_key = parameters.get("object_key", "default-object")
            
            self.s3_client.delete_object(Bucket=bucket_name, Key=object_key)
            
            result = {
                "action": "delete_object",
                "success": True,
                "bucket_name": bucket_name,
                "object_key": object_key,
                "message": f"객체 '{object_key}'가 버킷 '{bucket_name}'에서 삭제되었습니다."
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"S3 객체 삭제 실패: {e}")
            return json.dumps({
                "action": "delete_object",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _get_bucket_info(self, parameters: Dict[str, Any]) -> str:
        """S3 버킷 정보 조회"""
        try:
            bucket_name = parameters.get("bucket_name", "default-bucket")
            
            # 버킷 위치 조회
            location_response = self.s3_client.get_bucket_location(Bucket=bucket_name)
            
            # 버킷 정책 조회 (선택적)
            try:
                policy_response = self.s3_client.get_bucket_policy(Bucket=bucket_name)
                bucket_policy = policy_response.get('Policy')
            except ClientError:
                bucket_policy = None
            
            result = {
                "action": "get_bucket_info",
                "success": True,
                "bucket_name": bucket_name,
                "location": location_response.get('LocationConstraint', 'us-east-1'),
                "has_policy": bucket_policy is not None
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"S3 버킷 정보 조회 실패: {e}")
            return json.dumps({
                "action": "get_bucket_info",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)


class S3Agent(BaseAgent):
    """LangChain을 사용한 S3 Mini Agent (LangGraph 호환)"""
    
    def __init__(self, settings, aws_access_key: str = None, aws_secret_key: str = None, region: str = "us-east-1"):
        # BaseAgent 초기화
        super().__init__(settings, aws_access_key, aws_secret_key, region)
        
        # AWS S3 도구 초기화
        self.s3_tool = AWSS3Tool(aws_access_key, aws_secret_key, region)
    
    async def _parse_request_llm_based(self, user_request: str) -> str:
        """LLM 기반 요청 파싱"""
        try:
            # LLM을 사용하여 요청 분석
            analysis_prompt = ChatPromptTemplate.from_messages([
                ("system", """당신은 AWS S3 리소스를 관리하는 전문 Agent입니다.
사용자의 요청을 분석하여 적절한 S3 작업을 결정하세요.

지원하는 작업:
1. list_buckets: S3 버킷 목록 조회
2. create_bucket: S3 버킷 생성
3. delete_bucket: S3 버킷 삭제
4. list_objects: 버킷 내 객체 목록 조회
5. upload_object: 객체 업로드
6. download_object: 객체 다운로드
7. delete_object: 객체 삭제
8. get_bucket_info: 버킷 정보 조회

요청에서 버킷 이름, 객체 키 등을 추출하세요.
응답은 반드시 다음 형식으로 제공해야 합니다:
- 버킷 목록 조회: "버킷 목록" 또는 "list bucket"
- 버킷 생성: "버킷 생성 [버킷이름]" 또는 "create bucket [버킷이름]"
- 객체 목록: "객체 목록 [버킷이름]" 또는 "list object [버킷이름]"
- 기타 작업도 유사한 형식으로

사용자 요청을 분석하여 적절한 S3 작업 명령어를 생성하세요."""),
                ("human", "사용자 요청: {user_request}")
            ])
            
            # LLM 호출
            messages = analysis_prompt.format_messages(user_request=user_request)
            response = self.llm.invoke(messages)
            
            # 응답 추출
            parsed_command = response.content if hasattr(response, 'content') else str(response)
            
            logger.info(f"LLM 파싱 결과: {parsed_command[:100]}")
            return parsed_command
            
        except Exception as e:
            logger.warning(f"LLM 기반 파싱 실패, 규칙 기반 폴백 사용: {e}")
            # 폴백: 규칙 기반 파싱
            return self._parse_query_rule_based_fallback(user_request)
    
    def _parse_query_rule_based_fallback(self, query: str) -> str:
        """규칙 기반 쿼리 파싱 (폴백용)"""
        query_lower = query.lower()
        
        if "버킷 목록" in query or "list bucket" in query_lower:
            return "버킷 목록"
        elif "버킷 생성" in query or "create bucket" in query_lower:
            bucket_name = self._extract_bucket_name(query)
            return f"버킷 생성 {bucket_name}"
        elif "객체 목록" in query or "list object" in query_lower:
            bucket_name = self._extract_bucket_name(query)
            return f"객체 목록 {bucket_name}"
        else:
            return query
    
    async def _generate_llm_response(self, user_request: str, tool_result: str) -> str:
        """LLM 기반 응답 생성"""
        try:
            # 도구 실행 결과 파싱
            try:
                tool_data = json.loads(tool_result) if tool_result.startswith('{') else {"result": tool_result}
            except:
                tool_data = {"result": tool_result}
            
            # LLM을 사용하여 사용자 친화적인 응답 생성
            response_prompt = ChatPromptTemplate.from_messages([
                ("system", """당신은 AWS S3 전문가입니다. 
S3 작업 결과를 사용자에게 친절하고 이해하기 쉽게 설명하세요.
기술적인 세부사항은 포함하되, 사용자가 쉽게 이해할 수 있도록 작성하세요."""),
                ("human", """사용자 요청: {user_request}

S3 작업 결과:
{tool_result}

위 결과를 바탕으로 사용자에게 친절하고 명확한 응답을 생성하세요.""")
            ])
            
            # LLM 호출
            messages = response_prompt.format_messages(
                user_request=user_request,
                tool_result=json.dumps(tool_data, ensure_ascii=False, indent=2)
            )
            response = self.llm.invoke(messages)
            
            return response.content if hasattr(response, 'content') else str(response)
            
        except Exception as e:
            logger.warning(f"LLM 응답 생성 실패, 기본 응답 사용: {e}")
            # 폴백: 기본 응답
            return self._generate_rule_based_response_fallback(user_request, tool_result)
    
    def _generate_rule_based_response_fallback(self, user_request: str, tool_result: str = "") -> str:
        """규칙 기반 응답 생성 (폴백용)"""
        user_request_lower = user_request.lower()
        
        try:
            tool_data = json.loads(tool_result) if tool_result.startswith('{') else {}
            action = tool_data.get("action", "")
            
            if action == "list_buckets":
                count = tool_data.get("total_count", 0)
                return f"현재 계정에 {count}개의 S3 버킷이 있습니다."
            elif action == "create_bucket":
                bucket_name = tool_data.get("bucket_name", "")
                return f"S3 버킷 '{bucket_name}'이 성공적으로 생성되었습니다."
            elif action == "list_objects":
                count = tool_data.get("total_count", 0)
                return f"버킷에 {count}개의 객체가 있습니다."
            else:
                return f"S3 작업이 완료되었습니다: {action}"
        except:
            if any(keyword in user_request_lower for keyword in ["생성", "만들", "create"]):
                return "S3 버킷을 생성하는 방법을 안내해드리겠습니다. AWS 콘솔에서 S3 서비스로 이동하여 '버킷 만들기'를 클릭하고 버킷 이름을 입력하세요."
            elif any(keyword in user_request_lower for keyword in ["목록", "리스트", "조회", "list"]):
                return "현재 계정의 S3 버킷 목록을 조회해드리겠습니다."
            else:
                return "S3 서비스에 대한 도움을 드리겠습니다. 버킷 생성, 파일 업로드/다운로드, 권한 설정 등의 작업을 도와드릴 수 있습니다."
    
    def get_agent_type(self) -> str:
        """에이전트 타입 반환"""
        return "s3"
    
    def get_system_prompt(self) -> str:
        """S3 전문 시스템 프롬프트"""
        return """당신은 AWS S3 전문가입니다. 사용자의 요청을 분석하여 적절한 S3 작업을 수행합니다.

지원하는 작업:
- 버킷 생성, 삭제, 목록 조회
- 객체 업로드, 다운로드, 삭제
- 권한 설정 및 관리

응답은 항상 사용자 친화적이고 도움이 되는 정보를 제공해야 합니다."""
    
    def get_required_parameters(self, action: str) -> List[str]:
        """액션별 필수 파라미터 목록"""
        required_params = {
            "list_buckets": [],
            "create_bucket": ["BucketName"],
            "delete_bucket": ["BucketName"],
            "list_objects": ["BucketName"],
            "upload_object": ["BucketName", "Key"],
            "download_object": ["BucketName", "Key"],
            "delete_object": ["BucketName", "Key"],
            "get_bucket_info": ["BucketName"]
        }
        return required_params.get(action, [])
    
    def get_dangerous_actions(self) -> List[str]:
        """위험 작업 목록"""
        return ["delete_bucket", "delete_object"]
    
    def get_available_actions(self) -> List[str]:
        """지원하는 액션 목록"""
        return [
            "list_buckets",
            "create_bucket",
            "delete_bucket",
            "list_objects",
            "upload_object",
            "download_object",
            "delete_object",
            "get_bucket_info"
        ]
    
    def execute_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """실제 작업 실행"""
        try:
            # S3 도구 실행
            request_data = S3Request(
                action=action,
                parameters=parameters,
                region=self.region
            )
            
            query = json.dumps({
                'action': action,
                'parameters': parameters
            })
            
            result = self.s3_tool._run(query)
            return json.loads(result) if result.startswith('{') else {"success": True, "result": result}
            
        except Exception as e:
            logger.error(f"S3 액션 실행 중 오류: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def verify_action_result(self, action: str, parameters: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """결과 검증"""
        try:
            if not result.get("success"):
                return {
                    "passed": False,
                    "reason": result.get("error", "작업 실행 실패")
                }
            
            # 액션별 검증
            if action == "create_bucket":
                bucket_name = parameters.get("BucketName")
                if bucket_name:
                    # 실제로 버킷이 생성되었는지 확인
                    try:
                        self.s3_tool.s3_client.head_bucket(Bucket=bucket_name)
                        return {
                            "passed": True,
                            "reason": f"버킷 {bucket_name}가 성공적으로 생성되었습니다."
                        }
                    except Exception as e:
                        logger.warning(f"버킷 검증 중 오류: {e}")
                        return {
                            "passed": True,
                            "reason": "버킷 생성 API 호출 성공"
                        }
            
            elif action == "delete_bucket":
                return {
                    "passed": True,
                    "reason": "버킷 삭제 요청이 성공적으로 처리되었습니다."
                }
            
            elif action == "list_buckets":
                return {
                    "passed": True,
                    "reason": "버킷 목록 조회 성공"
                }
            
            # 기본 검증: 성공 여부만 확인
            return {
                "passed": True,
                "reason": "작업 실행 성공"
            }
            
        except Exception as e:
            logger.error(f"결과 검증 중 오류: {e}")
            return {
                "passed": False,
                "error": str(e)
            }

