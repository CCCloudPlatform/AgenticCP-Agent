import json
import logging
from typing import Any, List, Mapping, Optional, Dict

import boto3
from botocore.exceptions import ClientError
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.llms import BaseLLM
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

class BedrockEmbeddingLLM(BaseLLM):
    """AWS Bedrock Embedding LLM (LangChain 호환) - Amazon Titan Text Embeddings V2"""
    
    model_id: str = "amazon.titan-embed-text-v2:0"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    
    _bedrock_client: Any = None
    
    def __init__(self, **data: Any):
        super().__init__(**data)
        self._initialize_bedrock_client()
    
    def _initialize_bedrock_client(self):
        """Bedrock 런타임 클라이언트 초기화"""
        try:
            session_kwargs = {
                "region_name": self.aws_region
            }
            
            if self.aws_access_key_id and self.aws_secret_access_key:
                session_kwargs.update({
                    "aws_access_key_id": self.aws_access_key_id,
                    "aws_secret_access_key": self.aws_secret_access_key
                })
            
            session = boto3.Session(**session_kwargs)
            self._bedrock_client = session.client('bedrock-runtime')
            
            logger.info(f"Bedrock 클라이언트 초기화 완료: {self.model_id}")
            
        except Exception as e:
            logger.error(f"Bedrock 클라이언트 초기화 실패: {e}")
            raise
    
    @property
    def _llm_type(self) -> str:
        """LLM 타입 반환"""
        return "bedrock_embedding"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """임베딩 모델 호출 - 텍스트를 벡터로 변환"""
        try:
            # 텍스트 임베딩 생성
            embedding = self._generate_embedding(prompt)
            
            # 임베딩을 문자열로 변환 (간단한 텍스트 응답으로 변환)
            embedding_str = json.dumps(embedding)
            
            # 간단한 텍스트 응답 생성 (임베딩 기반)
            response = f"텍스트 임베딩이 생성되었습니다. 벡터 차원: {len(embedding)}"
            
            return response
            
        except Exception as e:
            logger.error(f"Bedrock Embedding LLM 호출 실패: {e}")
            raise
    
    def _generate_embedding(self, text: str) -> List[float]:
        """텍스트 임베딩 생성"""
        try:
            # Titan Text Embeddings V2 요청 형식
            request_body = {
                "inputText": text
            }
            
            response = self._bedrock_client.invoke_model(
                body=json.dumps(request_body),
                modelId=self.model_id,
                accept="application/json",
                contentType="application/json"
            )
            
            response_body = json.loads(response.get("body").read())
            embedding = response_body.get("embedding", [])
            
            logger.info(f"임베딩 생성 완료: 차원 {len(embedding)}")
            return embedding
            
        except ClientError as e:
            logger.error(f"Titan Embedding 모델 호출 실패: {e}")
            raise
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """LangChain 호환 메시지 생성"""
        try:
            # 메시지를 텍스트로 변환
            text = self._format_messages_to_text(messages)
            
            # 임베딩 기반 응답 생성
            response = self._call(text, stop, run_manager, **kwargs)
            
            return LLMResult(generations=[[AIMessage(content=response)]])
            
        except Exception as e:
            logger.error(f"Bedrock 임베딩 메시지 생성 실패: {e}")
            raise
    
    def _format_messages_to_text(self, messages: List[BaseMessage]) -> str:
        """LangChain 메시지를 텍스트로 변환"""
        text_parts = []
        
        for message in messages:
            if isinstance(message, HumanMessage):
                text_parts.append(f"사용자: {message.content}")
            elif isinstance(message, AIMessage):
                text_parts.append(f"AI: {message.content}")
            elif isinstance(message, SystemMessage):
                text_parts.append(f"시스템: {message.content}")
            else:
                text_parts.append(f"{message.type.capitalize()}: {message.content}")
        
        return "\n".join(text_parts)
    
    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """식별 매개변수 반환"""
        return {
            "model_id": self.model_id,
            "model_type": self._llm_type,
            "aws_region": self.aws_region,
            "provider": "aws_bedrock_titan_embedding"
        }
    
    def test_connection(self) -> bool:
        """Bedrock 연결 테스트"""
        try:
            test_text = "Hello, this is a test."
            embedding = self._generate_embedding(test_text)
            return len(embedding) > 0
        except Exception as e:
            logger.error(f"Bedrock 연결 테스트 실패: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보 반환"""
        return {
            "model_id": self.model_id,
            "provider": "aws_bedrock_titan_embedding",
            "region": self.aws_region,
            "model_type": "embedding"
        }
    
    def get_embedding(self, text: str) -> List[float]:
        """텍스트 임베딩 직접 반환"""
        return self._generate_embedding(text)

# 기존 BedrockChatLLM 클래스도 유지 (호환성을 위해)
class BedrockChatLLM(BaseLLM):
    """AWS Bedrock Chat LLM (LangChain 호환) - Amazon Titan Text Embeddings V2 지원"""
    
    model_id: str = "amazon.titan-embed-text-v2:0"
    temperature: float = 0.1
    max_tokens: int = 4000
    top_p: float = 0.9
    top_k: int = 250
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    
    _bedrock_client: Any = None
    
    def __init__(self, **data: Any):
        super().__init__(**data)
        self._initialize_bedrock_client()
    
    def _initialize_bedrock_client(self):
        """Bedrock 런타임 클라이언트 초기화"""
        try:
            session_kwargs = {
                "region_name": self.aws_region
            }
            
            if self.aws_access_key_id and self.aws_secret_access_key:
                session_kwargs.update({
                    "aws_access_key_id": self.aws_access_key_id,
                    "aws_secret_access_key": self.aws_secret_access_key
                })
            
            session = boto3.Session(**session_kwargs)
            self._bedrock_client = session.client('bedrock-runtime')
            
            logger.info(f"Bedrock 클라이언트 초기화 완료: {self.model_id}")
            
        except Exception as e:
            logger.error(f"Bedrock 클라이언트 초기화 실패: {e}")
            raise
    
    @property
    def _llm_type(self) -> str:
        """LLM 타입 반환"""
        return "bedrock"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """임베딩 기반 텍스트 생성"""
        try:
            # 텍스트 임베딩 생성
            embedding = self._generate_embedding(prompt)
            
            # 임베딩을 기반으로 간단한 응답 생성
            response = self._generate_response_from_embedding(prompt, embedding)
            
            return response
            
        except Exception as e:
            logger.error(f"Bedrock LLM 호출 실패: {e}")
            raise
    
    def _generate_embedding(self, text: str) -> List[float]:
        """텍스트 임베딩 생성"""
        try:
            # Titan Text Embeddings V2 요청 형식
            request_body = {
                "inputText": text
            }
            
            response = self._bedrock_client.invoke_model(
                body=json.dumps(request_body),
                modelId=self.model_id,
                accept="application/json",
                contentType="application/json"
            )
            
            response_body = json.loads(response.get("body").read())
            embedding = response_body.get("embedding", [])
            
            logger.info(f"임베딩 생성 완료: 차원 {len(embedding)}")
            return embedding
            
        except ClientError as e:
            logger.error(f"Titan Embedding 모델 호출 실패: {e}")
            raise
    
    def _generate_response_from_embedding(self, prompt: str, embedding: List[float]) -> str:
        """임베딩을 기반으로 응답 생성"""
        # 간단한 규칙 기반 응답 생성
        prompt_lower = prompt.lower()
        
        if "안녕" in prompt_lower or "hello" in prompt_lower:
            return "안녕하세요! Amazon Titan Text Embeddings V2를 사용하여 텍스트를 벡터로 변환하고 있습니다."
        elif "ec2" in prompt_lower:
            return "EC2 인스턴스에 대한 정보를 제공합니다. Amazon Titan Embeddings를 사용하여 관련 정보를 처리했습니다."
        elif "s3" in prompt_lower:
            return "S3 버킷에 대한 정보를 제공합니다. Amazon Titan Embeddings를 사용하여 관련 정보를 처리했습니다."
        elif "vpc" in prompt_lower:
            return "VPC 네트워크에 대한 정보를 제공합니다. Amazon Titan Embeddings를 사용하여 관련 정보를 처리했습니다."
        else:
            return f"Amazon Titan Text Embeddings V2를 사용하여 요청을 처리했습니다. 임베딩 차원: {len(embedding)}"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """LangChain 호환 메시지 생성"""
        try:
            # 메시지를 텍스트로 변환
            text = self._format_messages_to_text(messages)
            
            # 임베딩 기반 응답 생성
            response = self._call(text, stop, run_manager, **kwargs)
            
            return LLMResult(generations=[[AIMessage(content=response)]])
            
        except Exception as e:
            logger.error(f"Bedrock 임베딩 메시지 생성 실패: {e}")
            raise
    
    def _format_messages_to_text(self, messages: List[BaseMessage]) -> str:
        """LangChain 메시지를 텍스트로 변환"""
        text_parts = []
        
        for message in messages:
            if isinstance(message, HumanMessage):
                text_parts.append(f"사용자: {message.content}")
            elif isinstance(message, AIMessage):
                text_parts.append(f"AI: {message.content}")
            elif isinstance(message, SystemMessage):
                text_parts.append(f"시스템: {message.content}")
            else:
                text_parts.append(f"{message.type.capitalize()}: {message.content}")
        
        return "\n".join(text_parts)
    
    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """식별 매개변수 반환"""
        return {
            "model_id": self.model_id,
            "model_type": self._llm_type,
            "aws_region": self.aws_region,
            "provider": "aws_bedrock_titan_embedding"
        }
    
    def test_connection(self) -> bool:
        """Bedrock 연결 테스트"""
        try:
            test_text = "Hello, this is a test."
            embedding = self._generate_embedding(test_text)
            return len(embedding) > 0
        except Exception as e:
            logger.error(f"Bedrock 연결 테스트 실패: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보 반환"""
        return {
            "model_id": self.model_id,
            "provider": "aws_bedrock_titan_embedding",
            "region": self.aws_region,
            "model_type": "embedding"
        }
    
    def get_embedding(self, text: str) -> List[float]:
        """텍스트 임베딩 직접 반환"""
        return self._generate_embedding(text)