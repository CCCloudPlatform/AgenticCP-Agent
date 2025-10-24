"""
Agent Factory

다양한 Mini Agent들을 생성하고 관리하는 팩토리 클래스
"""

import logging
from typing import Dict, Any, Optional, Type
from abc import ABC, abstractmethod

from .ec2_agent import EC2Agent
from .s3_agent import S3Agent
from .vpc_agent import VPCAgent
from .bedrock_llm import BedrockChatLLM

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base Agent 인터페이스"""
    
    @abstractmethod
    async def process_request(self, user_request: str) -> Dict[str, Any]:
        """사용자 요청 처리"""
        pass
    
    @abstractmethod
    def get_agent_type(self) -> str:
        """에이전트 타입 반환"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> list:
        """에이전트 기능 목록 반환"""
        pass


class AgentFactory:
    """Agent Factory 클래스"""
    
    _agents: Dict[str, Type[BaseAgent]] = {
        "ec2": EC2Agent,
        "s3": S3Agent,
        "vpc": VPCAgent,
    }
    
    _instances: Dict[str, BaseAgent] = {}
    
    @classmethod
    def create_agent(
        self, 
        agent_type: str, 
        settings,
        aws_access_key: str = None,
        aws_secret_key: str = None,
        region: str = "us-east-1"
    ) -> Optional[BaseAgent]:
        """에이전트 생성"""
        try:
            if agent_type not in self._agents:
                logger.error(f"지원하지 않는 에이전트 타입: {agent_type}")
                return None
            
            # 인스턴스 키 생성
            instance_key = f"{agent_type}_{region}"
            
            # 이미 생성된 인스턴스가 있으면 재사용
            if instance_key in self._instances:
                logger.info(f"기존 {agent_type} 에이전트 인스턴스 재사용")
                return self._instances[instance_key]
            
            # 새 인스턴스 생성
            agent_class = self._agents[agent_type]
            agent_instance = agent_class(
                settings=settings,
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key,
                region=region
            )
            
            # 인스턴스 저장
            self._instances[instance_key] = agent_instance
            
            logger.info(f"{agent_type} 에이전트 생성 완료")
            return agent_instance
            
        except Exception as e:
            logger.error(f"에이전트 생성 실패 ({agent_type}): {e}")
            return None
    
    @classmethod
    def get_available_agents(cls) -> Dict[str, Dict[str, Any]]:
        """사용 가능한 에이전트 목록 반환"""
        agents_info = {}
        
        for agent_type, agent_class in cls._agents.items():
            # 임시 인스턴스 생성하여 정보 수집
            try:
                temp_instance = agent_class(
                    openai_api_key="temp",
                    aws_access_key="temp",
                    aws_secret_key="temp"
                )
                
                agents_info[agent_type] = {
                    "name": agent_type.upper(),
                    "description": cls._get_agent_description(agent_type),
                    "capabilities": cls._get_agent_capabilities(agent_type),
                    "class_name": agent_class.__name__
                }
            except Exception as e:
                logger.warning(f"에이전트 정보 수집 실패 ({agent_type}): {e}")
                agents_info[agent_type] = {
                    "name": agent_type.upper(),
                    "description": f"{agent_type.upper()} Agent",
                    "capabilities": [],
                    "class_name": agent_class.__name__
                }
        
        return agents_info
    
    @classmethod
    def _get_agent_description(cls, agent_type: str) -> str:
        """에이전트 설명 반환"""
        descriptions = {
            "ec2": "AWS EC2 인스턴스 관리 및 조작을 담당하는 Mini Agent",
            "s3": "AWS S3 버킷 및 객체 관리 및 조작을 담당하는 Mini Agent",
            "vpc": "AWS VPC, 서브넷, 보안 그룹 관리 및 조작을 담당하는 Mini Agent"
        }
        return descriptions.get(agent_type, f"{agent_type.upper()} Agent")
    
    @classmethod
    def _get_agent_capabilities(cls, agent_type: str) -> list:
        """에이전트 기능 목록 반환"""
        capabilities = {
            "ec2": [
                "EC2 인스턴스 생성",
                "인스턴스 목록 조회",
                "인스턴스 상태 확인",
                "인스턴스 시작/중지",
                "인스턴스 삭제",
                "AMI 관리",
                "보안 그룹 관리"
            ],
            "s3": [
                "S3 버킷 생성",
                "버킷 목록 조회",
                "버킷 삭제",
                "객체 업로드",
                "객체 다운로드",
                "객체 목록 조회",
                "객체 삭제",
                "버킷 정책 관리"
            ],
            "vpc": [
                "VPC 생성",
                "VPC 목록 조회",
                "VPC 삭제",
                "서브넷 생성",
                "서브넷 목록 조회",
                "서브넷 삭제",
                "보안 그룹 생성",
                "보안 그룹 목록 조회",
                "보안 그룹 삭제",
                "네트워크 ACL 관리"
            ]
        }
        return capabilities.get(agent_type, [])
    
    @classmethod
    def get_agent_instance(cls, agent_type: str, region: str = "us-east-1") -> Optional[BaseAgent]:
        """기존 에이전트 인스턴스 반환"""
        instance_key = f"{agent_type}_{region}"
        return cls._instances.get(instance_key)
    
    @classmethod
    def clear_instances(cls):
        """모든 에이전트 인스턴스 정리"""
        cls._instances.clear()
        logger.info("모든 에이전트 인스턴스 정리 완료")
    
    @classmethod
    def register_agent(cls, agent_type: str, agent_class: Type[BaseAgent]):
        """새로운 에이전트 타입 등록"""
        cls._agents[agent_type] = agent_class
        logger.info(f"새로운 에이전트 타입 등록: {agent_type}")
    
    @classmethod
    def unregister_agent(cls, agent_type: str):
        """에이전트 타입 등록 해제"""
        if agent_type in cls._agents:
            del cls._agents[agent_type]
            logger.info(f"에이전트 타입 등록 해제: {agent_type}")
    
    @classmethod
    def get_agent_stats(cls) -> Dict[str, Any]:
        """에이전트 통계 정보 반환"""
        return {
            "total_agent_types": len(cls._agents),
            "active_instances": len(cls._instances),
            "available_agents": list(cls._agents.keys()),
            "active_instance_keys": list(cls._instances.keys())
        }

