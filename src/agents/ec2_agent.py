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
from langchain_aws import ChatBedrock
from langchain_core.tools import BaseTool, tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.callbacks import CallbackManagerForToolRun

# AWS CC API MCP 관련 import (실제 구현에서는 MCP 클라이언트를 사용)
import requests
import boto3
from botocore.exceptions import ClientError

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
        """EC2 인스턴스 생성 (AWS Cloud Control API 사용)"""
        try:
            # AMI ID가 제공되지 않거나 "auto"인 경우 최신 Amazon Linux 2 AMI 조회
            ami_id = parameters.get('ami_id') or parameters.get('ImageId')
            if not ami_id or ami_id == 'ami-0abcdef1234567890' or ami_id == 'auto':
                ami_id = self._get_latest_amazon_linux_ami()
            
            # AWS Cloud Control API를 사용한 인스턴스 생성 (올바른 리소스 모델 사용)
            resource_model = {
                "ImageId": ami_id,
                "InstanceType": parameters.get('instance_type') or parameters.get('InstanceType', 't2.micro'),
                "Tags": [
                    {
                        "Key": "Name",
                        "Value": parameters.get('Name', 'EC2-Instance-Created-by-Agent')
                    }
                ]
            }
            
            # 선택적 파라미터 추가 (Cloud Control API 호환)
            if parameters.get('KeyName'):
                resource_model["KeyName"] = parameters.get('KeyName')
            if parameters.get('SecurityGroupIds'):
                resource_model["SecurityGroupIds"] = parameters.get('SecurityGroupIds')
            if parameters.get('SubnetId'):
                resource_model["SubnetId"] = parameters.get('SubnetId')
            
            logger.info(f"EC2 인스턴스 생성 시도 - AMI: {ami_id}, Type: {resource_model['InstanceType']}")
            
            # Cloud Control API를 사용한 리소스 생성
            response = self._cloudcontrol_client.create_resource(
                TypeName='AWS::EC2::Instance',
                DesiredState=json.dumps(resource_model)
            )
            
            # 응답에서 인스턴스 ID 추출 (Cloud Control API 응답 구조 확인)
            if 'ResourceDescription' in response:
                resource_description = json.loads(response['ResourceDescription']['Properties'])
                instance_id = resource_description.get('InstanceId')
            else:
                # Cloud Control API 응답이 예상과 다른 경우
                logger.warning(f"Cloud Control API 응답 구조가 예상과 다름: {response}")
                instance_id = response.get('Identifier', 'unknown')
            
            # datetime 객체를 문자열로 변환하여 JSON 직렬화 문제 해결
            def convert_datetime(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: convert_datetime(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_datetime(item) for item in obj]
                return obj
            
            safe_response = convert_datetime(response)
            
            return json.dumps({
                "success": True,
                "instance_id": instance_id,
                "message": f"인스턴스 {instance_id}가 성공적으로 생성되었습니다.",
                "ami_id": ami_id,
                "instance_type": resource_model['InstanceType'],
                "response": safe_response
            })
            
        except Exception as e:
            logger.error(f"Cloud Control API 인스턴스 생성 중 오류: {e}")
            
            # 폴백: 일반 EC2 API 사용
            try:
                logger.info("EC2 API로 폴백 시도...")
                return self._create_instance_ec2_fallback(parameters, ami_id)
            except Exception as fallback_error:
                logger.error(f"EC2 API 폴백도 실패: {fallback_error}")
                return json.dumps({"error": str(e), "fallback_error": str(fallback_error)})
    
    def _create_instance_ec2_fallback(self, parameters: Dict[str, Any], ami_id: str) -> str:
        """EC2 API 폴백 메서드"""
        try:
            # 기본 파라미터 설정
            run_instances_params = {
                'ImageId': ami_id,
                'MinCount': 1,
                'MaxCount': 1,
                'InstanceType': parameters.get('instance_type') or parameters.get('InstanceType', 't2.micro'),
                'TagSpecifications': [
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': parameters.get('Name', 'EC2-Instance-Created-by-Agent')}
                        ]
                    }
                ]
            }
            
            # 선택적 파라미터 추가
            if parameters.get('KeyName'):
                run_instances_params['KeyName'] = parameters.get('KeyName')
            if parameters.get('SecurityGroupIds'):
                run_instances_params['SecurityGroupIds'] = parameters.get('SecurityGroupIds')
            if parameters.get('SubnetId'):
                run_instances_params['SubnetId'] = parameters.get('SubnetId')
            
            # None 값 제거
            run_instances_params = {k: v for k, v in run_instances_params.items() if v is not None}
            
            logger.info(f"EC2 API 폴백 - AMI: {ami_id}, Params: {run_instances_params}")
            
            response = self._ec2_client.run_instances(**run_instances_params)
            instance_id = response['Instances'][0]['InstanceId']
            
            # datetime 객체를 문자열로 변환하여 JSON 직렬화 문제 해결
            def convert_datetime(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: convert_datetime(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_datetime(item) for item in obj]
                return obj
            
            safe_response = convert_datetime(response)
            
            return json.dumps({
                "success": True,
                "instance_id": instance_id,
                "message": f"인스턴스 {instance_id}가 EC2 API로 생성되었습니다.",
                "ami_id": ami_id,
                "instance_type": run_instances_params['InstanceType'],
                "response": safe_response
            })
            
        except Exception as e:
            logger.error(f"EC2 API 폴백 실패: {e}")
            raise e
    
    def _get_latest_amazon_linux_ami(self) -> str:
        """최신 Amazon Linux 2 AMI ID 조회"""
        try:
            # 여러 리전의 실제 Amazon Linux 2 AMI ID들 (2024년 기준)
            fallback_amis = {
                'ap-northeast-2': 'ami-0c02fb55956c7d3ee',  # Seoul - Amazon Linux 2
                'us-east-1': 'ami-0c02fb55956c7d3ee',       # N. Virginia - Amazon Linux 2
                'us-west-2': 'ami-0c02fb55956c7d3ee',       # Oregon - Amazon Linux 2
                'eu-west-1': 'ami-0c02fb55956c7d3ee',       # Ireland - Amazon Linux 2
            }
            
            # 현재 리전의 기본 AMI 사용
            default_ami = fallback_amis.get(self._region, 'ami-0c02fb55956c7d3ee')
            
            # 실제 AMI 조회 시도
            try:
                response = self._ec2_client.describe_images(
                    Owners=['amazon'],
                    Filters=[
                        {'Name': 'name', 'Values': ['amzn2-ami-hvm-*']},
                        {'Name': 'architecture', 'Values': ['x86_64']},
                        {'Name': 'state', 'Values': ['available']},
                        {'Name': 'virtualization-type', 'Values': ['hvm']}
                    ]
                )
                
                if response['Images']:
                    # 최신 AMI 선택 (CreationDate 기준)
                    latest_ami = max(response['Images'], key=lambda x: x['CreationDate'])
                    logger.info(f"최신 Amazon Linux 2 AMI 발견: {latest_ami['ImageId']}")
                    return latest_ami['ImageId']
                    
            except Exception as e:
                logger.warning(f"AMI 조회 실패, 기본 AMI 사용: {e}")
            
            logger.info(f"기본 AMI 사용: {default_ami}")
            return default_ami
                
        except Exception as e:
            logger.error(f"AMI 조회 중 오류: {e}")
            # 최종 폴백
            return 'ami-0c02fb55956c7d3ee'
    
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
            instance_id = parameters.get('instance_id')
            
            # instance_id가 "auto"인 경우 이름으로 인스턴스 찾기
            if instance_id == "auto":
                instance_ids = self._find_instances_by_name("EC2-Instance-Created-by-Agent")
            elif instance_id and instance_id != "auto":
                instance_ids = [instance_id]
            
            if not instance_ids:
                return json.dumps({"error": "삭제할 인스턴스를 찾을 수 없습니다."})
            
            # datetime 변환 함수
            def convert_datetime(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: convert_datetime(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_datetime(item) for item in obj]
                return obj
            
            response = self._ec2_client.terminate_instances(InstanceIds=instance_ids)
            safe_response = convert_datetime(response)
            
            return json.dumps({
                "success": True,
                "message": f"인스턴스 {instance_ids}가 종료되었습니다.",
                "response": safe_response
            })
            
        except ClientError as e:
            logger.error(f"인스턴스 종료 중 오류: {e}")
            return json.dumps({"error": str(e)})
    
    def _find_instances_by_name(self, name: str) -> List[str]:
        """이름으로 인스턴스 ID 찾기"""
        try:
            response = self._ec2_client.describe_instances(
                Filters=[
                    {
                        'Name': 'tag:Name',
                        'Values': [name]
                    },
                    {
                        'Name': 'instance-state-name',
                        'Values': ['running', 'stopped', 'stopping', 'pending']
                    }
                ]
            )
            
            instance_ids = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instance_ids.append(instance['InstanceId'])
            
            logger.info(f"이름 '{name}'으로 찾은 인스턴스: {instance_ids}")
            return instance_ids
            
        except Exception as e:
            logger.error(f"이름으로 인스턴스 찾기 중 오류: {e}")
            return []
    
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
        # Settings 객체가 MultiAgentSettings인지 확인하고 적절히 처리
        if hasattr(settings, 'multi_agent'):
            # 전체 Settings 객체인 경우
            multi_agent_settings = settings.multi_agent
        else:
            # 이미 MultiAgentSettings 객체인 경우
            multi_agent_settings = settings
        
        # LLM Provider 설정에 따라 LLM 초기화 (Bedrock 전용)
        self.llm = ChatBedrock(
            model_id=multi_agent_settings.bedrock_model_id,
            temperature=multi_agent_settings.bedrock_temperature,
            max_tokens=multi_agent_settings.bedrock_max_tokens,
            aws_access_key_id=aws_access_key or multi_agent_settings.aws_access_key_id,
            aws_secret_access_key=aws_secret_key or multi_agent_settings.aws_secret_access_key,
            region_name=region or multi_agent_settings.aws_region
        )
        logger.info(f"EC2 Agent - Bedrock LLM 초기화 완료: {multi_agent_settings.bedrock_model_id}")
        
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
    
    async def process_request(self, user_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """사용자 요청을 처리하는 메인 메서드 (LLM 기반)"""
        logger.info(f"EC2 Agent 요청 처리 시작: {user_request[:50]}...")
        
        try:
            # LLM 기반 요청 분석
            action_data = await self._analyze_request_llm_based(user_request)
            
            if action_data and 'action' in action_data:
                # 실제 AWS API 호출
                aws_result = await self._execute_aws_action(action_data)
                
                if aws_result.get('success'):
                    final_response = self._create_success_response(aws_result, action_data)
                else:
                    final_response = self._create_error_response(aws_result, action_data)
                
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
    
    async def _execute_aws_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """AWS 액션 실행"""
        try:
            action = action_data.get('action')
            parameters = action_data.get('parameters', {})
            
            # AWS CC Tool을 사용하여 액션 실행
            query = json.dumps({
                'action': action,
                'parameters': parameters
            })
            
            result = self.aws_tool._run(query)
            return json.loads(result)
            
        except Exception as e:
            logger.error(f"AWS 액션 실행 중 오류: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _analyze_request_llm_based(self, user_request: str) -> dict:
        """LLM 기반 요청 분석"""
        try:
            # LLM을 사용하여 요청 분석
            analysis_prompt = ChatPromptTemplate.from_messages([
                ("system", """당신은 AWS EC2 리소스를 관리하는 전문 Agent입니다.
사용자의 요청을 분석하여 적절한 EC2 작업을 결정하세요.

지원하는 작업:
1. list_instances: EC2 인스턴스 목록 조회
2. create_instance: EC2 인스턴스 생성
3. start_instance: EC2 인스턴스 시작
4. stop_instance: EC2 인스턴스 중지
5. terminate_instance: EC2 인스턴스 종료/삭제
6. describe_instance: EC2 인스턴스 상세 정보 조회

요청에서 인스턴스 ID(i-로 시작), 인스턴스 타입(t2.micro 등), AMI ID 등을 추출하세요.
응답은 반드시 다음 JSON 형식으로 제공해야 합니다:
{{
    "action": "작업명",
    "parameters": {{
        "InstanceIds": ["i-xxx"] (해당되는 경우),
        "instance_type": "t2.micro" (생성 시),
        "ami_id": "auto" (생성 시, 자동으로 최신 AMI 조회)
    }},
    "reasoning": "선택 이유"
}}"""),
                ("human", "사용자 요청: {user_request}")
            ])
            
            # LLM 호출
            messages = analysis_prompt.format_messages(user_request=user_request)
            response = self.llm.invoke(messages)
            
            # 응답 파싱
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # JSON 추출 시도
            try:
                import re
                json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(0)
                
                action_data = json.loads(response_text)
                
                # 인스턴스 ID 추출 (요청에서 직접 찾기)
                instance_ids = self._extract_instance_ids(user_request)
                if instance_ids and 'parameters' in action_data:
                    if action_data['action'] in ['stop_instance', 'start_instance', 'terminate_instance', 'describe_instance']:
                        action_data['parameters']['InstanceIds'] = instance_ids
                
                logger.info(f"LLM 분석 결과: {action_data.get('action')} - {action_data.get('reasoning', '')}")
                return action_data
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"LLM 응답 파싱 실패, 규칙 기반 폴백 사용: {e}")
                # 폴백: 규칙 기반 분석
                return self._analyze_request_rule_based_fallback(user_request)
                
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
                logger.warning(f"LLM 기반 요청 분석 중 오류: {error_msg}")
            
            # 하이브리드 폴백: Embedding → Keywords
            fallback_result = None
            
            # 1. Embedding 기반 의도 분류 시도
            try:
                from ..utils.intent_classifier import (
                    classify_intent_hybrid,
                    map_intent_to_action
                )
                
                intent, classify_method, intent_confidence = classify_intent_hybrid(user_request)
                if intent and intent_confidence >= 0.65:
                    action = map_intent_to_action(intent)
                    if action:
                        # EC2 관련 액션만 처리
                        if action.startswith('list_instances') or action == 'list_instances':
                            fallback_result = {
                                "action": "list_instances",
                                "parameters": {},
                                "reasoning": f"Embedding 기반 폴백: {intent} → {action}",
                                "confidence": intent_confidence
                            }
                        elif action == 'create_instance':
                            fallback_result = {
                                "action": "create_instance",
                                "parameters": {
                                    "instance_type": "t2.micro",
                                    "ami_id": "auto"
                                },
                                "reasoning": f"Embedding 기반 폴백: {intent} → {action}",
                                "confidence": intent_confidence
                            }
                        elif action in ['stop_instance', 'start_instance', 'terminate_instance']:
                            instance_ids = self._extract_instance_ids(user_request)
                            fallback_result = {
                                "action": action,
                                "parameters": {
                                    "InstanceIds": instance_ids if instance_ids else []
                                },
                                "reasoning": f"Embedding 기반 폴백: {intent} → {action}",
                                "confidence": intent_confidence
                            }
                        
                        if fallback_result:
                            logger.info(
                                f"✅ Embedding 기반 폴백 성공: '{user_request}' → {intent} → {action} "
                                f"(신뢰도: {intent_confidence:.2f})"
                            )
            except ImportError:
                logger.warning("Embedding 기반 의도 분류 모듈을 사용할 수 없습니다. 규칙 기반 폴백 사용.")
            except Exception as embed_error:
                logger.warning(f"Embedding 기반 의도 분류 실패: {embed_error}. 규칙 기반 폴백 사용.")
            
            # 2. Embedding 실패 시 규칙 기반 폴백
            if not fallback_result:
                logger.info("규칙 기반 폴백으로 전환하여 요청 분석 시도")
                fallback_result = self._analyze_request_rule_based_fallback(user_request)
                logger.info(f"규칙 기반 폴백 결과: {fallback_result.get('action')} - {fallback_result.get('parameters', {})}")
            
            return fallback_result
    
    def _analyze_request_rule_based_fallback(self, user_request: str) -> dict:
        """규칙 기반 요청 분석 (폴백용)"""
        user_request_lower = user_request.lower()
        
        # 인스턴스 생성
        if any(keyword in user_request_lower for keyword in ["생성", "만들", "create", "launch"]):
            return {
                "action": "create_instance",
                "parameters": {
                    "instance_type": "t2.micro",
                    "ami_id": "auto"
                }
            }
        
        # 인스턴스 중지
        elif any(keyword in user_request_lower for keyword in ["중지", "정지", "stop", "shutdown"]):
            instance_ids = self._extract_instance_ids(user_request)
            return {
                "action": "stop_instance",
                "parameters": {
                    "InstanceIds": instance_ids if instance_ids else []
                }
            }
        
        # 인스턴스 시작
        elif any(keyword in user_request_lower for keyword in ["시작", "start"]):
            instance_ids = self._extract_instance_ids(user_request)
            return {
                "action": "start_instance",
                "parameters": {
                    "InstanceIds": instance_ids if instance_ids else []
                }
            }
        
        # 인스턴스 삭제/종료
        elif any(keyword in user_request_lower for keyword in ["삭제", "지워", "종료", "terminate", "delete", "remove"]):
            instance_ids = self._extract_instance_ids(user_request)
            return {
                "action": "terminate_instance",
                "parameters": {
                    "instance_id": "auto" if not instance_ids else instance_ids[0]
                }
            }
        
        # 인스턴스 상세 정보 조회 (특정 인스턴스 ID가 있는 경우)
        elif self._extract_instance_ids(user_request):
            instance_ids = self._extract_instance_ids(user_request)
            return {
                "action": "describe_instance",
                "parameters": {
                    "InstanceIds": instance_ids
                }
            }
        
        # EC2 정보/목록 조회 (기본 동작)
        # "정보", "알려줘", "목록", "리스트", "조회", "보여" 등의 키워드가 있거나
        # EC2 관련 요청인데 구체적인 액션이 없는 경우
        elif any(keyword in user_request_lower for keyword in [
            "정보", "info", "알려줘", "알려", "보여줘", "보여",
            "목록", "리스트", "조회", "list", "show", "상태", "status"
        ]):
            return {
                "action": "list_instances",
                "parameters": {}
            }
        
        # 기본 응답: EC2 관련 요청이지만 구체적인 액션이 없으면 목록 조회
        else:
            logger.info("구체적인 액션을 찾지 못함, 기본으로 인스턴스 목록 조회")
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
    
    def _create_error_response(self, aws_data: Dict[str, Any], action_data: Dict[str, Any]) -> Dict[str, Any]:
        """오류 응답 생성"""
        action = action_data.get('action')
        error_msg = aws_data.get('error', '알 수 없는 오류')
        
        return {
            "success": False,
            "agent_type": "ec2",
            "response": f"EC2 {action} 작업 중 오류가 발생했습니다: {error_msg}",
            "action": action,
            "error": error_msg,
            "confidence": 0.5
        }
    
    def _create_success_response(self, aws_data: Dict[str, Any], action_data: Dict[str, Any]) -> Dict[str, Any]:
        """성공 응답 생성"""
        action = action_data.get('action')
        
        if action == 'list_instances':
            instances = aws_data.get('instances', [])
            count = aws_data.get('count', 0)
            
            if count == 0:
                response_text = "현재 실행 중인 EC2 인스턴스가 없습니다."
            else:
                instance_list = []
                for instance in instances:
                    instance_info = f"• {instance['InstanceId']} ({instance['InstanceType']}) - {instance['State']}"
                    if instance.get('PublicIpAddress') != 'N/A':
                        instance_info += f" - Public IP: {instance['PublicIpAddress']}"
                    instance_list.append(instance_info)
                
                response_text = f"EC2 인스턴스 목록 ({count}개):\n" + "\n".join(instance_list)
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
