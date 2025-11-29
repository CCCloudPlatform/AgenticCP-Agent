# Embedding 기반 의도 분류 구현 계획

## 개요
키워드 기반 매칭의 한계를 극복하기 위해 Semantic Embedding 기반 유사도 매칭을 도입합니다.

## 구현 단계

### 1단계: 의존성 추가 ✅

```bash
pip install sentence-transformers scikit-learn
```

또는 `requirements.txt`에 추가:
```
sentence-transformers>=2.2.0
scikit-learn>=1.3.0
```

### 2단계: 유틸리티 모듈 생성 ✅

`src/utils/intent_classifier.py` 생성 완료

### 3단계: Supervisor Agent 통합

`src/agents/supervisor_agent.py` 수정:
- LLM 실패 시 Embedding 기반 분류 사용
- 하이브리드 접근법 적용

### 4단계: EC2 Agent 통합

`src/agents/ec2_agent.py` 수정:
- LLM 실패 시 Embedding 기반 액션 분류 사용

### 5단계: 설정 추가

`src/config/settings.py`에 옵션 추가:
- Embedding 모델 선택
- 유사도 임계값 설정
- 사용 여부 토글

## 사용 예시

### 기본 사용
```python
from src.utils.intent_classifier import classify_intent_hybrid

intent, method, confidence = classify_intent_hybrid("EC2 정보를 알려줘")
# 결과: ('ec2_list', 'embedding', 0.85)
```

### Supervisor Agent 통합
```python
# LLM 실패 시
intent, method, confidence = classify_intent_hybrid(user_request)
agent_type = map_intent_to_agent_type(intent)
```

### EC2 Agent 통합
```python
# LLM 실패 시
intent, method, confidence = classify_intent_hybrid(user_request)
action = map_intent_to_action(intent)
```

## 성능 최적화

### 모델 선택
- **경량 모델**: `paraphrase-multilingual-MiniLM-L12-v2` (~420MB)
- **한국어 특화**: `jhgan/ko-sroberta-multitask` (~500MB)
- **최고 성능**: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (~1GB)

### 캐싱
- 모델 로딩: Lazy loading (처음 사용 시)
- 임베딩: 자주 사용되는 템플릿은 캐싱 가능

### 임계값 튜닝
- 기본값: 0.65
- 엄격한 모드: 0.75 (더 정확하지만 놓치는 경우 증가)
- 관대한 모드: 0.55 (더 많이 매칭되지만 오분류 가능)

## 테스트 예시

```python
test_cases = [
    ("EC2 정보를 알려줘", "ec2_list"),
    ("EC2 인스턴스 목록 보여줘", "ec2_list"),
    ("현재 실행 중인 EC2 서버가 몇 개야?", "ec2_list"),
    ("EC2 인스턴스를 만들어줘", "ec2_create"),
    ("EC2 서버 생성", "ec2_create"),
    ("S3 버킷 목록", "s3_list"),
    ("VPC 정보", "vpc_list"),
]

for request, expected in test_cases:
    intent, method, confidence = classify_intent_hybrid(request)
    print(f"{request} -> {intent} ({method}, {confidence:.2f})")
```

## 모니터링

### 로그
- 의도 분류 성공/실패 로그
- 사용된 방법 (embedding/keywords)
- 유사도 점수

### 메트릭
- Embedding 기반 분류 성공률
- 평균 유사도 점수
- 분류 방법별 사용 빈도

## 롤백 계획

만약 문제가 발생하면:
1. 환경 변수로 비활성화: `USE_EMBEDDING_INTENT=false`
2. 키워드 기반 폴백으로 자동 전환
3. 기존 코드 유지 (하위 호환성)

