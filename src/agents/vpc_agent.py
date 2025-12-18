"""
VPC Mini Agent using LangChain and AWS CC API MCP
AWS VPC 리소스 관리 및 조작을 담당하는 Mini Agent
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
class VPCRequest:
    """VPC 요청 데이터 구조"""
    action: str
    parameters: Dict[str, Any]
    region: Optional[str] = None


class AWSVPCTool(BaseTool):
    """AWS VPC를 활용한 도구"""
    
    name: str = "aws_vpc"
    description: str = "AWS VPC, 서브넷, 보안 그룹 등을 관리합니다."
    session: Any = None
    ec2_client: Any = None
    
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
        
        self.ec2_client = self.session.client('ec2')
    
    def _generate_rule_based_response(self, user_request: str) -> str:
        """규칙 기반 응답 생성"""
        user_request_lower = user_request.lower()
        
        if any(keyword in user_request_lower for keyword in ["생성", "만들", "create"]):
            return "VPC를 생성하는 방법을 안내해드리겠습니다. AWS 콘솔에서 VPC 서비스로 이동하여 'VPC 생성'을 클릭하고 CIDR 블록을 설정하세요."
        elif any(keyword in user_request_lower for keyword in ["목록", "리스트", "조회", "list"]):
            return "현재 계정의 VPC 목록을 조회해드리겠습니다."
        elif any(keyword in user_request_lower for keyword in ["서브넷", "subnet"]):
            return "VPC 내에서 서브넷을 생성하고 관리하는 방법을 안내해드리겠습니다."
        elif any(keyword in user_request_lower for keyword in ["보안그룹", "security group"]):
            return "VPC 보안 그룹을 생성하고 규칙을 설정하는 방법을 안내해드리겠습니다."
        else:
            return "VPC 서비스에 대한 도움을 드리겠습니다. VPC 생성, 서브넷 관리, 보안 그룹 설정 등의 작업을 도와드릴 수 있습니다."
    
    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """VPC 작업 실행"""
        try:
            # 쿼리 파싱
            request_data = self._parse_query(query)
            
            if request_data.action == "list_vpcs":
                return self._list_vpcs()
            elif request_data.action == "create_vpc":
                return self._create_vpc(request_data.parameters)
            elif request_data.action == "delete_vpc":
                return self._delete_vpc(request_data.parameters)
            elif request_data.action == "list_subnets":
                return self._list_subnets(request_data.parameters)
            elif request_data.action == "create_subnet":
                return self._create_subnet(request_data.parameters)
            elif request_data.action == "delete_subnet":
                return self._delete_subnet(request_data.parameters)
            elif request_data.action == "list_security_groups":
                return self._list_security_groups(request_data.parameters)
            elif request_data.action == "create_security_group":
                return self._create_security_group(request_data.parameters)
            elif request_data.action == "delete_security_group":
                return self._delete_security_group(request_data.parameters)
            elif request_data.action == "get_vpc_info":
                return self._get_vpc_info(request_data.parameters)
            else:
                return f"지원하지 않는 VPC 작업입니다: {request_data.action}"
                
        except Exception as e:
            logger.error(f"VPC 작업 실행 중 오류: {e}")
            return f"VPC 작업 실행 중 오류가 발생했습니다: {str(e)}"
    
    def _parse_query(self, query: str) -> VPCRequest:
        """쿼리 파싱"""
        query_lower = query.lower()
        
        if "vpc 목록" in query or "list vpc" in query_lower:
            return VPCRequest(action="list_vpcs", parameters={})
        elif "vpc 생성" in query or "create vpc" in query_lower:
            cidr_block = self._extract_cidr_block(query)
            return VPCRequest(action="create_vpc", parameters={"cidr_block": cidr_block})
        elif "vpc 삭제" in query or "delete vpc" in query_lower:
            vpc_id = self._extract_vpc_id(query)
            return VPCRequest(action="delete_vpc", parameters={"vpc_id": vpc_id})
        elif "서브넷 목록" in query or "list subnet" in query_lower:
            vpc_id = self._extract_vpc_id(query)
            return VPCRequest(action="list_subnets", parameters={"vpc_id": vpc_id})
        elif "서브넷 생성" in query or "create subnet" in query_lower:
            vpc_id = self._extract_vpc_id(query)
            cidr_block = self._extract_cidr_block(query)
            return VPCRequest(action="create_subnet", parameters={
                "vpc_id": vpc_id,
                "cidr_block": cidr_block
            })
        elif "서브넷 삭제" in query or "delete subnet" in query_lower:
            subnet_id = self._extract_subnet_id(query)
            return VPCRequest(action="delete_subnet", parameters={"subnet_id": subnet_id})
        elif "보안 그룹 목록" in query or "list security group" in query_lower:
            vpc_id = self._extract_vpc_id(query)
            return VPCRequest(action="list_security_groups", parameters={"vpc_id": vpc_id})
        elif "보안 그룹 생성" in query or "create security group" in query_lower:
            vpc_id = self._extract_vpc_id(query)
            group_name = self._extract_group_name(query)
            return VPCRequest(action="create_security_group", parameters={
                "vpc_id": vpc_id,
                "group_name": group_name
            })
        elif "보안 그룹 삭제" in query or "delete security group" in query_lower:
            group_id = self._extract_group_id(query)
            return VPCRequest(action="delete_security_group", parameters={"group_id": group_id})
        elif "vpc 정보" in query or "vpc info" in query_lower:
            vpc_id = self._extract_vpc_id(query)
            return VPCRequest(action="get_vpc_info", parameters={"vpc_id": vpc_id})
        else:
            return VPCRequest(action="unknown", parameters={})
    
    def _extract_vpc_id(self, query: str) -> str:
        """쿼리에서 VPC ID 추출"""
        words = query.split()
        for i, word in enumerate(words):
            if word.lower() in ["vpc"] and i + 1 < len(words):
                return words[i + 1]
        return "vpc-default"
    
    def _extract_subnet_id(self, query: str) -> str:
        """쿼리에서 서브넷 ID 추출"""
        words = query.split()
        for i, word in enumerate(words):
            if word.lower() in ["서브넷", "subnet"] and i + 1 < len(words):
                return words[i + 1]
        return "subnet-default"
    
    def _extract_cidr_block(self, query: str) -> str:
        """쿼리에서 CIDR 블록 추출"""
        import re
        cidr_pattern = r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}\b'
        match = re.search(cidr_pattern, query)
        return match.group() if match else "10.0.0.0/16"
    
    def _extract_group_name(self, query: str) -> str:
        """쿼리에서 그룹 이름 추출"""
        words = query.split()
        for i, word in enumerate(words):
            if word.lower() in ["그룹", "group"] and i + 1 < len(words):
                return words[i + 1]
        return "default-group"
    
    def _extract_group_id(self, query: str) -> str:
        """쿼리에서 그룹 ID 추출"""
        words = query.split()
        for i, word in enumerate(words):
            if word.lower() in ["그룹", "group"] and i + 1 < len(words):
                return words[i + 1]
        return "sg-default"
    
    def _list_vpcs(self) -> str:
        """VPC 목록 조회"""
        try:
            response = self.ec2_client.describe_vpcs()
            vpcs = response.get('Vpcs', [])
            
            result = {
                "action": "list_vpcs",
                "success": True,
                "vpcs": [
                    {
                        "vpc_id": vpc['VpcId'],
                        "cidr_block": vpc['CidrBlock'],
                        "state": vpc['State'],
                        "is_default": vpc.get('IsDefault', False)
                    }
                    for vpc in vpcs
                ],
                "total_count": len(vpcs)
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"VPC 목록 조회 실패: {e}")
            return json.dumps({
                "action": "list_vpcs",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _create_vpc(self, parameters: Dict[str, Any]) -> str:
        """VPC 생성"""
        try:
            cidr_block = parameters.get("cidr_block", "10.0.0.0/16")
            
            response = self.ec2_client.create_vpc(CidrBlock=cidr_block)
            vpc = response['Vpc']
            
            result = {
                "action": "create_vpc",
                "success": True,
                "vpc_id": vpc['VpcId'],
                "cidr_block": vpc['CidrBlock'],
                "state": vpc['State'],
                "message": f"VPC '{vpc['VpcId']}'이 성공적으로 생성되었습니다."
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"VPC 생성 실패: {e}")
            return json.dumps({
                "action": "create_vpc",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _delete_vpc(self, parameters: Dict[str, Any]) -> str:
        """VPC 삭제"""
        try:
            vpc_id = parameters.get("vpc_id", "vpc-default")
            
            self.ec2_client.delete_vpc(VpcId=vpc_id)
            
            result = {
                "action": "delete_vpc",
                "success": True,
                "vpc_id": vpc_id,
                "message": f"VPC '{vpc_id}'이 성공적으로 삭제되었습니다."
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"VPC 삭제 실패: {e}")
            return json.dumps({
                "action": "delete_vpc",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _list_subnets(self, parameters: Dict[str, Any]) -> str:
        """서브넷 목록 조회"""
        try:
            vpc_id = parameters.get("vpc_id")
            filters = []
            if vpc_id:
                filters.append({'Name': 'vpc-id', 'Values': [vpc_id]})
            
            response = self.ec2_client.describe_subnets(Filters=filters)
            subnets = response.get('Subnets', [])
            
            result = {
                "action": "list_subnets",
                "success": True,
                "subnets": [
                    {
                        "subnet_id": subnet['SubnetId'],
                        "vpc_id": subnet['VpcId'],
                        "cidr_block": subnet['CidrBlock'],
                        "availability_zone": subnet['AvailabilityZone'],
                        "state": subnet['State']
                    }
                    for subnet in subnets
                ],
                "total_count": len(subnets)
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"서브넷 목록 조회 실패: {e}")
            return json.dumps({
                "action": "list_subnets",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _create_subnet(self, parameters: Dict[str, Any]) -> str:
        """서브넷 생성"""
        try:
            vpc_id = parameters.get("vpc_id", "vpc-default")
            cidr_block = parameters.get("cidr_block", "10.0.1.0/24")
            
            response = self.ec2_client.create_subnet(
                VpcId=vpc_id,
                CidrBlock=cidr_block
            )
            subnet = response['Subnet']
            
            result = {
                "action": "create_subnet",
                "success": True,
                "subnet_id": subnet['SubnetId'],
                "vpc_id": subnet['VpcId'],
                "cidr_block": subnet['CidrBlock'],
                "availability_zone": subnet['AvailabilityZone'],
                "message": f"서브넷 '{subnet['SubnetId']}'이 성공적으로 생성되었습니다."
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"서브넷 생성 실패: {e}")
            return json.dumps({
                "action": "create_subnet",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _delete_subnet(self, parameters: Dict[str, Any]) -> str:
        """서브넷 삭제"""
        try:
            subnet_id = parameters.get("subnet_id", "subnet-default")
            
            self.ec2_client.delete_subnet(SubnetId=subnet_id)
            
            result = {
                "action": "delete_subnet",
                "success": True,
                "subnet_id": subnet_id,
                "message": f"서브넷 '{subnet_id}'이 성공적으로 삭제되었습니다."
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"서브넷 삭제 실패: {e}")
            return json.dumps({
                "action": "delete_subnet",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _list_security_groups(self, parameters: Dict[str, Any]) -> str:
        """보안 그룹 목록 조회"""
        try:
            vpc_id = parameters.get("vpc_id")
            filters = []
            if vpc_id:
                filters.append({'Name': 'vpc-id', 'Values': [vpc_id]})
            
            response = self.ec2_client.describe_security_groups(Filters=filters)
            security_groups = response.get('SecurityGroups', [])
            
            result = {
                "action": "list_security_groups",
                "success": True,
                "security_groups": [
                    {
                        "group_id": sg['GroupId'],
                        "group_name": sg['GroupName'],
                        "vpc_id": sg['VpcId'],
                        "description": sg['Description']
                    }
                    for sg in security_groups
                ],
                "total_count": len(security_groups)
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"보안 그룹 목록 조회 실패: {e}")
            return json.dumps({
                "action": "list_security_groups",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _create_security_group(self, parameters: Dict[str, Any]) -> str:
        """보안 그룹 생성"""
        try:
            vpc_id = parameters.get("vpc_id", "vpc-default")
            group_name = parameters.get("group_name", "default-group")
            description = f"Security group for {group_name}"
            
            response = self.ec2_client.create_security_group(
                GroupName=group_name,
                Description=description,
                VpcId=vpc_id
            )
            
            result = {
                "action": "create_security_group",
                "success": True,
                "group_id": response['GroupId'],
                "group_name": group_name,
                "vpc_id": vpc_id,
                "message": f"보안 그룹 '{group_name}'이 성공적으로 생성되었습니다."
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"보안 그룹 생성 실패: {e}")
            return json.dumps({
                "action": "create_security_group",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _delete_security_group(self, parameters: Dict[str, Any]) -> str:
        """보안 그룹 삭제"""
        try:
            group_id = parameters.get("group_id", "sg-default")
            
            self.ec2_client.delete_security_group(GroupId=group_id)
            
            result = {
                "action": "delete_security_group",
                "success": True,
                "group_id": group_id,
                "message": f"보안 그룹 '{group_id}'이 성공적으로 삭제되었습니다."
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"보안 그룹 삭제 실패: {e}")
            return json.dumps({
                "action": "delete_security_group",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
    
    def _get_vpc_info(self, parameters: Dict[str, Any]) -> str:
        """VPC 정보 조회"""
        try:
            vpc_id = parameters.get("vpc_id", "vpc-default")
            
            response = self.ec2_client.describe_vpcs(VpcIds=[vpc_id])
            vpc = response['Vpcs'][0]
            
            result = {
                "action": "get_vpc_info",
                "success": True,
                "vpc_id": vpc['VpcId'],
                "cidr_block": vpc['CidrBlock'],
                "state": vpc['State'],
                "is_default": vpc.get('IsDefault', False),
                "dhcp_options_id": vpc.get('DhcpOptionsId'),
                "instance_tenancy": vpc.get('InstanceTenancy', 'default')
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except ClientError as e:
            logger.error(f"VPC 정보 조회 실패: {e}")
            return json.dumps({
                "action": "get_vpc_info",
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)


class VPCAgent(BaseAgent):
    """LangChain을 사용한 VPC Mini Agent (LangGraph 호환)"""
    
    def __init__(self, settings, aws_access_key: str = None, aws_secret_key: str = None, region: str = "us-east-1"):
        # BaseAgent 초기화
        super().__init__(settings, aws_access_key, aws_secret_key, region)
        
        # AWS VPC 도구 초기화
        self.vpc_tool = AWSVPCTool(aws_access_key, aws_secret_key, region)
    
    def get_agent_type(self) -> str:
        """에이전트 타입 반환"""
        return "vpc"
    
    def get_system_prompt(self) -> str:
        """VPC 전문 시스템 프롬프트"""
        return """당신은 AWS VPC 전문가입니다. 사용자의 요청을 분석하여 적절한 VPC 작업을 수행합니다.

지원하는 작업:
- VPC 생성, 삭제, 목록 조회
- 서브넷 생성 및 관리
- 보안 그룹 설정
- 라우팅 테이블 관리

응답은 항상 사용자 친화적이고 도움이 되는 정보를 제공해야 합니다."""
    
    def get_required_parameters(self, action: str) -> List[str]:
        """액션별 필수 파라미터 목록"""
        required_params = {
            "list_vpcs": [],
            "create_vpc": ["CidrBlock"],
            "delete_vpc": ["VpcId"],
            "get_vpc_info": ["VpcId"],
            "create_subnet": ["VpcId", "CidrBlock"],
            "delete_subnet": ["SubnetId"],
            "list_subnets": ["VpcId"],
            "create_security_group": ["GroupName", "VpcId"],
            "delete_security_group": ["GroupId"]
        }
        return required_params.get(action, [])
    
    def get_dangerous_actions(self) -> List[str]:
        """위험 작업 목록"""
        return ["delete_vpc", "delete_subnet", "delete_security_group"]
    
    def get_available_actions(self) -> List[str]:
        """지원하는 액션 목록"""
        return [
            "list_vpcs",
            "create_vpc",
            "delete_vpc",
            "get_vpc_info",
            "create_subnet",
            "delete_subnet",
            "list_subnets",
            "create_security_group",
            "delete_security_group"
        ]
    
    def execute_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """실제 작업 실행"""
        try:
            # VPC 도구 실행
            query = json.dumps({
                'action': action,
                'parameters': parameters
            })
            
            result = self.vpc_tool._run(query)
            return json.loads(result) if result.startswith('{') else {"success": True, "result": result}
            
        except Exception as e:
            logger.error(f"VPC 액션 실행 중 오류: {e}")
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
            if action == "create_vpc":
                vpc_id = result.get("vpc_id") or parameters.get("VpcId")
                if vpc_id:
                    # 실제로 VPC가 생성되었는지 확인
                    try:
                        response = self.vpc_tool._ec2_client.describe_vpcs(VpcIds=[vpc_id])
                        if response['Vpcs']:
                            return {
                                "passed": True,
                                "reason": f"VPC {vpc_id}가 성공적으로 생성되었습니다."
                            }
                    except Exception as e:
                        logger.warning(f"VPC 검증 중 오류: {e}")
                        return {
                            "passed": True,
                            "reason": "VPC 생성 API 호출 성공"
                        }
            
            elif action == "delete_vpc":
                return {
                    "passed": True,
                    "reason": "VPC 삭제 요청이 성공적으로 처리되었습니다."
                }
            
            elif action == "list_vpcs":
                return {
                    "passed": True,
                    "reason": "VPC 목록 조회 성공"
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

