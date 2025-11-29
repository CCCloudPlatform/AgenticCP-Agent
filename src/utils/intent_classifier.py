"""
의도 분류 유틸리티
Embedding 기반 유사도 매칭을 통한 자연어 요청 이해
"""

import logging
from typing import Dict, Optional, Tuple, List
import json
import os

logger = logging.getLogger(__name__)

# Lazy loading을 위한 모듈 레벨 변수
_embedding_model = None
_embedding_templates = None


def _load_embedding_model():
    """Embedding 모델 로드 (Lazy loading)"""
    global _embedding_model
    
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            
            # 한국어 지원 모델 (경량 버전)
            # 다국어 모델 대신 한국어 특화 모델 사용
            model_name = os.getenv(
                "INTENT_EMBEDDING_MODEL",
                "jhgan/ko-sroberta-multitask"  # 한국어 모델 (약 500MB)
            )
            
            logger.info(f"Embedding 모델 로딩 중: {model_name}")
            _embedding_model = SentenceTransformer(model_name)
            logger.info("Embedding 모델 로딩 완료")
            
        except ImportError:
            logger.warning(
                "sentence-transformers가 설치되지 않았습니다. "
                "pip install sentence-transformers로 설치하세요."
            )
            _embedding_model = False  # 로딩 실패 표시
        except Exception as e:
            logger.error(f"Embedding 모델 로딩 실패: {e}")
            _embedding_model = False
    
    return _embedding_model


def _load_intent_templates() -> Dict[str, List[str]]:
    """의도 템플릿 로드"""
    global _embedding_templates
    
    if _embedding_templates is None:
        _embedding_templates = {
            # EC2 관련 의도
            'ec2_list': [
                'EC2 인스턴스 목록 조회',
                'EC2 정보를 알려줘',
                'EC2 리스트 보여줘',
                '현재 실행 중인 EC2 인스턴스',
                'EC2 서버 목록',
                'EC2 인스턴스 상태 확인',
                'EC2 인스턴스가 몇 개야',
                'EC2 리스트',
                'EC2 정보',
                'EC2 인스턴스 조회',
                'EC2 서버 정보',
                'EC2 인스턴스 알려줘'
            ],
            'ec2_create': [
                'EC2 인스턴스 생성',
                'EC2 서버 만들기',
                '새 EC2 인스턴스 시작',
                'EC2 인스턴스 런칭',
                'EC2 인스턴스 새로 만들기',
                'EC2 서버 생성',
                'EC2 인스턴스 추가'
            ],
            'ec2_stop': [
                'EC2 인스턴스 중지',
                'EC2 서버 정지',
                'EC2 인스턴스 멈추기',
                'EC2 인스턴스 스톱'
            ],
            'ec2_start': [
                'EC2 인스턴스 시작',
                'EC2 서버 시작',
                'EC2 인스턴스 켜기'
            ],
            'ec2_terminate': [
                'EC2 인스턴스 삭제',
                'EC2 인스턴스 종료',
                'EC2 서버 삭제',
                'EC2 인스턴스 제거'
            ],
            
            # S3 관련 의도
            's3_list': [
                'S3 버킷 목록',
                'S3 버킷 정보',
                'S3 스토리지 조회',
                'S3 버킷 리스트',
                'S3 버킷 알려줘',
                'S3 버킷 보여줘'
            ],
            's3_create': [
                'S3 버킷 생성',
                'S3 버킷 만들기',
                '새 S3 버킷 만들기'
            ],
            
            # VPC 관련 의도
            'vpc_list': [
                'VPC 목록',
                'VPC 정보',
                'VPC 네트워크 조회',
                'VPC 리스트'
            ],
            'vpc_create': [
                'VPC 생성',
                'VPC 만들기',
                '새 VPC 만들기'
            ],
            
            # 일반 의도
            'general': [
                '안녕',
                '도움말',
                '도움',
                'help',
                'hello'
            ]
        }
    
    return _embedding_templates


def classify_intent_embedding(
    user_request: str,
    threshold: float = 0.65,
    top_k: int = 3
) -> Tuple[Optional[str], float, Dict[str, float]]:
    """
    Embedding 기반 의도 분류
    
    Args:
        user_request: 사용자 요청 텍스트
        threshold: 최소 유사도 임계값
        top_k: 상위 k개 결과 반환
    
    Returns:
        (의도, 유사도, 모든 의도별 유사도)
    """
    model = _load_embedding_model()
    
    if model is False or model is None:
        logger.warning("Embedding 모델을 사용할 수 없습니다. None 반환")
        return None, 0.0, {}
    
    templates = _load_intent_templates()
    
    try:
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        
        # 사용자 요청 임베딩
        user_embedding = model.encode([user_request], show_progress_bar=False)
        
        intent_scores = {}
        
        # 각 의도별로 최고 유사도 계산
        for intent, intent_templates in templates.items():
            # 템플릿들 임베딩
            template_embeddings = model.encode(
                intent_templates,
                show_progress_bar=False
            )
            
            # 코사인 유사도 계산
            similarities = cosine_similarity(user_embedding, template_embeddings)
            max_similarity = float(similarities.max())
            
            intent_scores[intent] = max_similarity
        
        # 상위 k개 정렬
        sorted_intents = sorted(
            intent_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 최고 유사도 의도
        best_intent, best_score = sorted_intents[0] if sorted_intents else (None, 0.0)
        
        # 임계값 확인
        if best_score >= threshold:
            logger.info(
                f"의도 분류 성공: '{user_request}' -> {best_intent} "
                f"(유사도: {best_score:.3f})"
            )
            
            # top_k 결과도 반환
            top_results = {
                intent: score
                for intent, score in sorted_intents[:top_k]
                if score >= 0.3  # 최소 유사도 필터
            }
            
            return best_intent, best_score, top_results
        else:
            logger.info(
                f"의도 분류 실패: '{user_request}' -> 최고 유사도 {best_score:.3f} "
                f"(임계값: {threshold})"
            )
            return None, best_score, {
                intent: score
                for intent, score in sorted_intents[:top_k]
            }
            
    except ImportError:
        logger.error("sklearn이 설치되지 않았습니다. pip install scikit-learn로 설치하세요.")
        return None, 0.0, {}
    except Exception as e:
        logger.error(f"의도 분류 중 오류: {e}")
        return None, 0.0, {}


def classify_intent_hybrid(
    user_request: str,
    use_embedding: bool = True,
    use_keywords: bool = True
) -> Tuple[Optional[str], str, float]:
    """
    하이브리드 의도 분류 (Embedding + Keywords)
    
    Args:
        user_request: 사용자 요청 텍스트
        use_embedding: Embedding 기반 분류 사용 여부
        use_keywords: 키워드 기반 폴백 사용 여부
    
    Returns:
        (의도, 방법, 신뢰도)
    """
    # 1. Embedding 기반 시도
    if use_embedding:
        intent, score, all_scores = classify_intent_embedding(user_request)
        if intent and score >= 0.65:
            return intent, "embedding", score
    
    # 2. 키워드 기반 폴백
    if use_keywords:
        intent, score = classify_intent_keywords(user_request)
        if intent:
            return intent, "keywords", score
    
    return None, "none", 0.0


def classify_intent_keywords(user_request: str) -> Tuple[Optional[str], float]:
    """
    키워드 기반 의도 분류 (폴백용)
    
    Args:
        user_request: 사용자 요청 텍스트
    
    Returns:
        (의도, 신뢰도)
    """
    user_request_lower = user_request.lower()
    
    # 키워드 매핑
    keyword_patterns = {
        'ec2_list': ['ec2', '인스턴스', '서버', '정보', '목록', '리스트', '조회', '알려줘', '보여줘'],
        'ec2_create': ['ec2', '생성', '만들', 'create', 'launch', '시작'],
        'ec2_stop': ['ec2', '중지', '정지', 'stop', '멈춤'],
        'ec2_start': ['ec2', '시작', 'start', '켜'],
        'ec2_terminate': ['ec2', '삭제', '종료', 'terminate', 'delete', '제거'],
        's3_list': ['s3', '버킷', 'bucket', '스토리지', 'storage'],
        's3_create': ['s3', '버킷', '생성', '만들', 'create'],
        'vpc_list': ['vpc', '네트워크', 'network', '서브넷', 'subnet'],
        'vpc_create': ['vpc', '생성', '만들', 'create'],
        'general': ['안녕', 'hello', 'hi', '도움', 'help']
    }
    
    intent_scores = {}
    
    for intent, keywords in keyword_patterns.items():
        matches = sum(1 for keyword in keywords if keyword in user_request_lower)
        if matches > 0:
            # 키워드 매칭 개수에 비례한 점수
            intent_scores[intent] = matches / len(keywords)
    
    if intent_scores:
        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        return best_intent[0], best_intent[1]
    
    return None, 0.0


def map_intent_to_agent_type(intent: str) -> Optional[str]:
    """의도를 Agent 타입으로 매핑"""
    mapping = {
        'ec2_list': 'ec2',
        'ec2_create': 'ec2',
        'ec2_stop': 'ec2',
        'ec2_start': 'ec2',
        'ec2_terminate': 'ec2',
        's3_list': 's3',
        's3_create': 's3',
        'vpc_list': 'vpc',
        'vpc_create': 'vpc',
        'general': 'general'
    }
    
    return mapping.get(intent)


def map_intent_to_action(intent: str) -> Optional[str]:
    """의도를 EC2 액션으로 매핑"""
    mapping = {
        'ec2_list': 'list_instances',
        'ec2_create': 'create_instance',
        'ec2_stop': 'stop_instance',
        'ec2_start': 'start_instance',
        'ec2_terminate': 'terminate_instance'
    }
    
    return mapping.get(intent)

