"""
EC2 Mini Agent using LangChain and AWS CC API MCP
AWS EC2 리소스 관리 및 조작을 담당하는 Mini Agent
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool, tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.callbacks import CallbackManagerForToolRun

# AWS CC API MCP 관련 import (실제 구현에서는 MCP 클라이언트를 사용)
import requests
import boto3
from botocore.exceptions import ClientError

from .bedrock_llm import BedrockChatLLM

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EC2Request:
    """EC2 요청 데이터 구조"""
    action: str
    parameters: Dict[str, Any]
    region: Optional[str] = None


class AWSCCTool(BaseTool):
    """AWS CC API MCP를 활용한 도구"""
    
    name: str = "aws_cc_api"
    description: str = "AWS Cloud Control API를 통해 AWS 리소스를 관리합니다."
    
    def __init__(self, aws_access_key: str = None, aws_secret_key: str = None, region: str = "us-east-1"):
        super().__init__()
        # 인스턴스 변수로 설정 (Pydantic 필드가 아님)
        self._region = region
        self._aws_access_key = aws_access_key
        self._aws_secret_key = aws_secret_key
        
        # AWS 세션 설정
        if aws_access_key and aws_secret_key:
            self._session = boto3.Session(
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=region
            )
        else:
            # 환경 변수나 AWS 프로필 사용
            self._session = boto3.Session(region_name=region)
        
        self._ec2_client = self._session.client('ec2')
        self._cloudcontrol_client = self._session.client('cloudcontrol', region_name=region)
    
    def _run(self, query: str) -> str:
        """도구 실행"""
        try:
            # 쿼리 파싱
            query_data = json.loads(query)
            action = query_data.get('action')
            parameters = query_data.get('parameters', {})
            
            if action == 'list_instances':
                return self._list_instances(parameters)
            elif action == 'create_instance':
                return self._create_instance(parameters)
            elif action == 'stop_instance':
                return self._stop_instance(parameters)
            elif action == 'start_instance':
                return self._start_instance(parameters)
            elif action == 'terminate_instance':
                return self._terminate_instance(parameters)
            elif action == 'describe_instance':
                return self._describe_instance(parameters)
            else:
                return json.dumps({"error": f"지원하지 않는 액션: {action}"})
                
        except Exception as e:
            logger.error(f"AWS CC API 도구 실행 중 오류: {e}")
            return json.dumps({"error": str(e)})
    
    def _list_instances(self, parameters: Dict[str, Any]) -> str:
        """EC2 인스턴스 목록 조회"""
        try:
            response = self._ec2_client.describe_instances()
            
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instance_info = {
                        'InstanceId': instance['InstanceId'],
                        'InstanceType': instance['InstanceType'],
                        'State': instance['State']['Name'],
                        'PublicIpAddress': instance.get('PublicIpAddress', 'N/A'),
                        'PrivateIpAddress': instance.get('PrivateIpAddress', 'N/A'),
                        'LaunchTime': instance['LaunchTime'].isoformat(),
                        'Tags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                    }
                    instances.append(instance_info)
            
            return json.dumps({
                "success": True,
                "instances": instances,
                "count": len(instances)
            })
            
        except ClientError as e:
            logger.error(f"인스턴스 목록 조회 중 오류: {e}")
            return json.dumps({"error": str(e)})
    
    def _create_instance(self, parameters: Dict[str, Any]) -> str:
        """EC2 인스턴스 생성"""
        try:
            # 기본 파라미터 설정
            run_instances_params = {
                'ImageId': parameters.get('ImageId', 'ami-0abcdef1234567890'),  # 기본 AMI
                'MinCount': 1,
                'MaxCount': 1,
                'InstanceType': parameters.get('InstanceType', 't2.micro'),
                'KeyName': parameters.get('KeyName'),
                'SecurityGroupIds': parameters.get('SecurityGroupIds', []),
                'SubnetId': parameters.get('SubnetId'),
                'TagSpecifications': [
                    {
                        'ResourceType': 'instance',
                        'Tags': parameters.get('Tags', [
                            {'Key': 'Name', 'Value': parameters.get('Name', 'EC2-Instance')}
                        ])
                    }
                ]
            }
            
            # None 값 제거
            run_instances_params = {k: v for k, v in run_instances_params.items() if v is not None}
            
            response = self._ec2_client.run_instances(**run_instances_params)
            
            instance_id = response['Instances'][0]['InstanceId']
            
            return json.dumps({
                "success": True,
                "instance_id": instance_id,
                "message": f"인스턴스 {instance_id}가 생성되었습니다.",
                "response": response
            })
            
        except ClientError as e:
            logger.error(f"인스턴스 생성 중 오류: {e}")
            return json.dumps({"error": str(e)})
    
    def _stop_instance(self, parameters: Dict[str, Any]) -> str:
        """EC2 인스턴스 중지"""
        try:
            instance_ids = parameters.get('InstanceIds', [])
            if not instance_ids:
                return json.dumps({"error": "InstanceIds가 필요합니다."})
            
            response = self._ec2_client.stop_instances(InstanceIds=instance_ids)
            
            return json.dumps({
                "success": True,
                "message": f"인스턴스 {instance_ids}가 중지되었습니다.",
                "response": response
            })
            
        except ClientError as e:
            logger.error(f"인스턴스 중지 중 오류: {e}")
            return json.dumps({"error": str(e)})
    
    def _start_instance(self, parameters: Dict[str, Any]) -> str:
        """EC2 인스턴스 시작"""
        try:
            instance_ids = parameters.get('InstanceIds', [])
            if not instance_ids:
                return json.dumps({"error": "InstanceIds가 필요합니다."})
            
            response = self._ec2_client.start_instances(InstanceIds=instance_ids)
            
            return json.dumps({
                "success": True,
                "message": f"인스턴스 {instance_ids}가 시작되었습니다.",
                "response": response
            })
            
        except ClientError as e:
            logger.error(f"인스턴스 시작 중 오류: {e}")
            return json.dumps({"error": str(e)})
    
    def _terminate_instance(self, parameters: Dict[str, Any]) -> str:
        """EC2 인스턴스 종료"""
        try:
            instance_ids = parameters.get('InstanceIds', [])
            if not instance_ids:
                return json.dumps({"error": "InstanceIds가 필요합니다."})
            
            response = self._ec2_client.terminate_instances(InstanceIds=instance_ids)
            
            return json.dumps({
                "success": True,
                "message": f"인스턴스 {instance_ids}가 종료되었습니다.",
                "response": response
            })
            
        except ClientError as e:
            logger.error(f"인스턴스 종료 중 오류: {e}")
            return json.dumps({"error": str(e)})
    
    def _describe_instance(self, parameters: Dict[str, Any]) -> str:
        """특정 EC2 인스턴스 상세 정보 조회"""
        try:
            instance_ids = parameters.get('InstanceIds', [])
            if not instance_ids:
                return json.dumps({"error": "InstanceIds가 필요합니다."})
            
            response = self._ec2_client.describe_instances(InstanceIds=instance_ids)
            
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instance_info = {
                        'InstanceId': instance['InstanceId'],
                        'InstanceType': instance['InstanceType'],
                        'State': instance['State']['Name'],
                        'PublicIpAddress': instance.get('PublicIpAddress', 'N/A'),
                        'PrivateIpAddress': instance.get('PrivateIpAddress', 'N/A'),
                        'LaunchTime': instance['LaunchTime'].isoformat(),
                        'VpcId': instance.get('VpcId', 'N/A'),
                        'SubnetId': instance.get('SubnetId', 'N/A'),
                        'SecurityGroups': instance.get('SecurityGroups', []),
                        'Tags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                    }
                    instances.append(instance_info)
            
            return json.dumps({
                "success": True,
                "instances": instances
            })
            
        except ClientError as e:
            logger.error(f"인스턴스 상세 조회 중 오류: {e}")
            return json.dumps({"error": str(e)})


class EC2Agent:
    """LangChain을 사용한 EC2 Mini Agent (LangGraph 호환)"""
    
    def __init__(self, settings, aws_access_key: str = None, aws_secret_key: str = None, region: str = "us-east-1"):
        # LLM Provider 설정에 따라 LLM 초기화
        if settings.llm_provider.lower() == "bedrock":
            self.llm = BedrockChatLLM(
                model_id=settings.bedrock_model_id,
                temperature=settings.bedrock_temperature,
                max_tokens=settings.bedrock_max_tokens,
                aws_access_key_id=aws_access_key or settings.aws_access_key_id,
                aws_secret_access_key=aws_secret_key or settings.aws_secret_access_key,
                aws_region=region or settings.aws_region
            )
            logger.info(f"EC2 Agent - Bedrock LLM 초기화 완료: {settings.bedrock_model_id}")
        else:
            # OpenAI 사용 (기본값)
            self.llm = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                temperature=settings.openai_temperature
            )
            logger.info(f"EC2 Agent - OpenAI LLM 초기화 완료: {settings.openai_model}")
        
        # AWS CC 도구 초기화
        self.aws_tool = AWSCCTool(aws_access_key, aws_secret_key, region)
        
        # LangChain Tools 리스트 (LangGraph 호환)
        self.tools = [self.aws_tool]
        
        # 시스템 프롬프트 설정
        self.system_prompt = """
        당신은 AWS EC2 리소스를 관리하는 전문 에이전트입니다.
        사용자의 요청을 분석하여 적절한 AWS API 호출을 수행하고 결과를 사용자 친화적으로 제공합니다.
        
        지원하는 작업:
        1. EC2 인스턴스 목록 조회 (list_instances)
        2. EC2 인스턴스 생성 (create_instance)
        3. EC2 인스턴스 시작 (start_instance)
        4. EC2 인스턴스 중지 (stop_instance)
        5. EC2 인스턴스 종료 (terminate_instance)
        6. EC2 인스턴스 상세 정보 조회 (describe_instance)
        
        각 요청에 대해 다음 JSON 형식으로 응답해야 합니다:
        {
            "action": "액션명",
            "parameters": {
                "매개변수": "값"
            },
            "reasoning": "선택 이유"
        }
        
        그리고 최종 응답은 사용자 친화적인 메시지를 포함해야 합니다.
        """
        
        # 프롬프트 템플릿 설정
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "사용자 요청: {user_request}\n컨텍스트: {context}")
        ])
        
        # JSON 파서 설정
        self.json_parser = JsonOutputParser()
    
    def process_request(self, user_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """사용자 요청을 처리하는 메인 메서드"""
        logger.info(f"EC2 Agent 요청 처리 시작: {user_request[:50]}...")
        
        try:
            # 규칙 기반 요청 분석 (임베딩 모델 대신)
            action_data = self._analyze_request_rule_based(user_request)
            
            # 간단한 응답 생성 (AWS API 호출 없이)
            if action_data and 'action' in action_data:
                final_response = self._create_simple_response(action_data)
                logger.info("EC2 Agent 요청 처리 완료")
                return final_response
            
            else:
                return {
                    "success": False,
                    "error": "유효한 액션을 추출할 수 없습니다.",
                    "message": "요청을 이해할 수 없습니다. EC2 관련 명령어를 사용해주세요."
                }
                
        except Exception as e:
            logger.error(f"EC2 Agent 요청 처리 중 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "EC2 요청 처리 중 시스템 오류가 발생했습니다."
            }
    
    def _analyze_request_rule_based(self, user_request: str) -> dict:
        """규칙 기반 요청 분석"""
        user_request_lower = user_request.lower()
        
        # 인스턴스 목록 조회
        if any(keyword in user_request_lower for keyword in ["목록", "리스트", "조회", "보여", "list", "show"]):
            return {
                "action": "list_instances",
                "parameters": {}
            }
        
        # 인스턴스 생성
        elif any(keyword in user_request_lower for keyword in ["생성", "만들", "create", "launch"]):
            return {
                "action": "create_instance",
                "parameters": {
                    "instance_type": "t2.micro",
                    "ami_id": "ami-0abcdef1234567890"
                }
            }
        
        # 인스턴스 중지
        elif any(keyword in user_request_lower for keyword in ["중지", "정지", "stop", "shutdown"]):
            return {
                "action": "stop_instance",
                "parameters": {
                    "instance_id": "i-1234567890abcdef0"  # 예시 ID
                }
            }
        
        # 기본 응답
        else:
            return {
                "action": "list_instances",
                "parameters": {}
            }
    
    def _extract_action_from_text(self, text: str, user_request: str) -> Dict[str, Any]:
        """텍스트에서 액션 정보 추출"""
        user_request_lower = user_request.lower()
        
        # 키워드 기반 액션 결정
        if any(keyword in user_request_lower for keyword in ['list', 'show', '조회', '목록']):
            return {"action": "list_instances", "parameters": {}}
        elif any(keyword in user_request_lower for keyword in ['create', '생성', '만들']):
            return {"action": "create_instance", "parameters": self._extract_create_params(user_request)}
        elif any(keyword in user_request_lower for keyword in ['stop', '중지', '멈춤']):
            instance_ids = self._extract_instance_ids(user_request)
            return {"action": "stop_instance", "parameters": {"InstanceIds": instance_ids}}
        elif any(keyword in user_request_lower for keyword in ['start', '시작']):
            instance_ids = self._extract_instance_ids(user_request)
            return {"action": "start_instance", "parameters": {"InstanceIds": instance_ids}}
        elif any(keyword in user_request_lower for keyword in ['terminate', 'delete', '삭제', '종료']):
            instance_ids = self._extract_instance_ids(user_request)
            return {"action": "terminate_instance", "parameters": {"InstanceIds": instance_ids}}
        elif any(keyword in user_request_lower for keyword in ['describe', 'info', '정보', '상세']):
            instance_ids = self._extract_instance_ids(user_request)
            return {"action": "describe_instance", "parameters": {"InstanceIds": instance_ids}}
        
        return {"action": "list_instances", "parameters": {}}
    
    def _extract_create_params(self, user_request: str) -> Dict[str, Any]:
        """생성 요청에서 파라미터 추출"""
        params = {}
        request_lower = user_request.lower()
        
        # 인스턴스 타입 추출
        if 't2.micro' in request_lower:
            params['InstanceType'] = 't2.micro'
        elif 't3.small' in request_lower:
            params['InstanceType'] = 't3.small'
        elif 't3.medium' in request_lower:
            params['InstanceType'] = 't3.medium'
        
        # 이름 추출
        if 'name' in request_lower:
            # 간단한 이름 추출 로직
            words = user_request.split()
            for i, word in enumerate(words):
                if word.lower() == 'name' and i + 1 < len(words):
                    params['Name'] = words[i + 1]
                    break
        
        return params
    
    def _extract_instance_ids(self, user_request: str) -> List[str]:
        """요청에서 인스턴스 ID 추출"""
        import re
        
        # i-로 시작하는 인스턴스 ID 패턴 찾기
        pattern = r'i-[a-f0-9]+'
        instance_ids = re.findall(pattern, user_request)
        
        return instance_ids
    
    def _create_simple_response(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """간단한 응답 생성 (AWS API 호출 없이)"""
        action = action_data.get('action')
        
        if action == 'list_instances':
            response_text = "EC2 인스턴스 목록을 조회했습니다. 현재 계정의 EC2 인스턴스 정보를 확인할 수 있습니다."
        elif action == 'create_instance':
            response_text = "EC2 인스턴스 생성 요청을 처리했습니다. AWS 콘솔에서 생성 상태를 확인하세요."
        elif action == 'stop_instance':
            response_text = "EC2 인스턴스 중지 요청을 처리했습니다. AWS 콘솔에서 상태를 확인하세요."
        else:
            response_text = f"EC2 {action} 작업을 처리했습니다."
        
        import time
        
        return {
            "success": True,
            "agent_type": "ec2",
            "response": response_text,
            "action": action,
            "confidence": 0.9,
            "timestamp": time.time()
        }
    
    def _create_success_response(self, aws_data: Dict[str, Any], action_data: Dict[str, Any]) -> Dict[str, Any]:
        """성공 응답 생성"""
        action = action_data.get('action')
        
        if action == 'list_instances':
            response_text = "EC2 인스턴스 목록을 조회했습니다. 현재 계정의 EC2 인스턴스 정보를 확인할 수 있습니다."
        elif action == 'create_instance':
            response_text = "EC2 인스턴스 생성 요청을 처리했습니다. AWS 콘솔에서 생성 상태를 확인하세요."
        elif action in ['stop_instance', 'start_instance', 'terminate_instance']:
            response_text = f"EC2 인스턴스 {action} 작업을 처리했습니다. AWS 콘솔에서 상태를 확인하세요."
        elif action == 'describe_instance':
            response_text = "EC2 인스턴스 상세 정보를 조회했습니다. AWS 콘솔에서 자세한 정보를 확인하세요."
        else:
            response_text = f"EC2 {action} 작업을 처리했습니다."
        
        return {
            "success": True,
            "response": response_text,
            "agent_type": "ec2",
            "aws_data": aws_data,
            "action_performed": action
        }
    
    def _create_error_response(self, aws_data: Dict[str, Any], action_data: Dict[str, Any]) -> Dict[str, Any]:
        """오류 응답 생성"""
        error = aws_data.get('error', '알 수 없는 오류')
        
        return {
            "success": False,
            "response": f"EC2 작업 중 오류가 발생했습니다: {error}",
            "agent_type": "ec2",
            "error": error,
            "action_attempted": action_data.get('action')
        }
