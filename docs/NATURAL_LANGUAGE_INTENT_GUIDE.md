# 자연어 요청 대응 기법 가이드

## 문제점
현재 키워드 기반 매칭의 한계:
- "EC2 정보를 알려줘" ✅
- "EC2 인스턴스 목록 보여줘" ❌ (키워드 "정보" 없음)
- "현재 실행 중인 EC2 서버가 몇 개야?" ❌ (다른 표현)

## 해결책

### 🎯 1. Semantic Embedding 기반 유사도 매칭 (추천 ⭐)

**개념**: 텍스트를 벡터로 변환하여 의미적 유사도로 매칭

**장점**:
- ✅ 오프라인 동작 (인터넷 불필요)
- ✅ 다양한 표현 자동 이해
- ✅ 동의어, 유사 표현 인식
- ✅ 경량 모델 사용 가능 (~500MB)

**동작 원리**:
```
사용자: "EC2 정보를 알려줘"
        ↓ (벡터 변환)
[0.123, 0.456, ...] (512차원 벡터)
        ↓ (유사도 계산)
템플릿: "EC2 인스턴스 목록 조회" [0.125, 0.458, ...]
유사도: 0.89 (매우 유사!) → ec2_list 의도
```

**구현 위치**: `src/utils/intent_classifier.py`

**사용법**:
```python
from src.utils.intent_classifier import classify_intent_hybrid

intent, method, confidence = classify_intent_hybrid("EC2 정보를 알려줘")
# 결과: ('ec2_list', 'embedding', 0.85)
```

---

### 🔄 2. 로컬 LLM (Ollama) - 선택사항

**개념**: 로컬에서 실행되는 LLM 모델

**장점**:
- ✅ 완전한 자연어 이해
- ✅ 오프라인 동작
- ✅ 데이터 프라이버시

**단점**:
- ❌ 리소스 많이 필요 (GPU 권장)
- ❌ 느릴 수 있음

**사용 시나리오**: Embedding으로도 해결 안 될 때만 사용

---

## 구현된 기능

### ✅ Embedding 기반 의도 분류
- 위치: `src/utils/intent_classifier.py`
- 지원 의도:
  - `ec2_list`: EC2 인스턴스 목록 조회
  - `ec2_create`: EC2 인스턴스 생성
  - `ec2_stop`: EC2 인스턴스 중지
  - `s3_list`: S3 버킷 목록
  - `vpc_list`: VPC 목록
  - 등등...

### ✅ 하이브리드 접근법
1. Embedding 시도 (유사도 > 0.65)
2. 키워드 폴백 (Embedding 실패 시)
3. 기본 동작 (둘 다 실패 시)

---

## 설치 및 사용

### 1. 패키지 설치
```bash
pip install sentence-transformers scikit-learn
```

또는:
```bash
pip install -r requirements.txt
```

### 2. 모델 다운로드
첫 실행 시 자동으로 다운로드됩니다:
- 한국어 모델: `jhgan/ko-sroberta-multitask` (~500MB)
- 다국어 모델: `paraphrase-multilingual-MiniLM-L12-v2` (~420MB)

### 3. 환경 변수 설정 (선택)
```bash
# Embedding 모델 선택
export INTENT_EMBEDDING_MODEL="jhgan/ko-sroberta-multitask"

# Embedding 사용 여부
export USE_EMBEDDING_INTENT=true
```

---

## 사용 예시

### Supervisor Agent 통합
```python
# LLM 실패 시 Embedding 기반 분류 사용
from src.utils.intent_classifier import classify_intent_hybrid, map_intent_to_agent_type

intent, method, confidence = classify_intent_hybrid(user_request)
if intent:
    agent_type = map_intent_to_agent_type(intent)
    # agent_type: 'ec2', 's3', 'vpc', 'general'
```

### EC2 Agent 통합
```python
# LLM 실패 시 Embedding 기반 액션 분류
from src.utils.intent_classifier import classify_intent_hybrid, map_intent_to_action

intent, method, confidence = classify_intent_hybrid(user_request)
if intent:
    action = map_intent_to_action(intent)
    # action: 'list_instances', 'create_instance', etc.
```

---

## 테스트 예시

다양한 표현으로 테스트 가능:

```python
test_cases = [
    "EC2 정보를 알려줘",                    # ✅
    "EC2 인스턴스 목록 보여줘",             # ✅
    "현재 실행 중인 EC2 서버가 몇 개야?",   # ✅
    "EC2 서버 정보",                        # ✅
    "EC2 인스턴스를 만들어줘",              # ✅
    "새로운 EC2 서버 생성",                 # ✅
    "EC2 서버 만들기",                      # ✅
]

for request in test_cases:
    intent, method, confidence = classify_intent_hybrid(request)
    print(f"{request:30} -> {intent:15} ({method:10}, {confidence:.2f})")
```

---

## 성능 비교

| 방법 | 정확도 | 속도 | 리소스 | 오프라인 |
|------|--------|------|--------|----------|
| 키워드 매칭 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ |
| **Embedding** | **⭐⭐⭐⭐** | **⭐⭐⭐⭐** | **⭐⭐⭐⭐** | **✅** |
| 로컬 LLM | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ✅ |
| 클라우드 LLM | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ |

**결론**: Embedding이 **가성비 최고** 🏆

---

## 다음 단계

1. ✅ Embedding 유틸리티 구현 완료
2. 🔄 Supervisor Agent에 통합 (다음 작업)
3. 🔄 EC2 Agent에 통합 (다음 작업)
4. 📊 모니터링 및 튜닝

---

## 참고 문서

- [의도 분류 가이드](./INTENT_CLASSIFICATION_GUIDE.md) - 상세 기술 설명
- [구현 계획](./IMPLEMENTATION_PLAN.md) - 통합 방법

