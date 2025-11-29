# 다양한 사용자 요청 대응 기법 가이드

LLM이 실패하거나 사용할 수 없는 상황에서도 다양한 자연어 요청에 대응하는 방법들입니다.

## 1. Semantic Embedding 기반 유사도 매칭 (추천)

### 개념
- 텍스트를 고차원 벡터(embedding)로 변환
- 벡터 간 유사도를 계산하여 의도 매칭
- 키워드 기반보다 훨씬 유연하고 다양한 표현 이해 가능

### 장점
- **오프라인 동작**: 인터넷 연결 불필요
- **다양한 표현 이해**: "EC2 정보 알려줘" = "EC2 인스턴스 목록 보여줘"
- **의미 기반 매칭**: 동의어, 유사 표현 자동 인식
- **경량**: 작은 모델 사용 가능 (약 100-500MB)

### 구현 방법
```python
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# 1. 모델 로드 (한 번만 로드)
model = SentenceTransformer('jhgan/ko-sroberta-multitask')

# 2. 예시 템플릿 정의
intent_templates = {
    'ec2_list': [
        'EC2 인스턴스 목록 조회',
        'EC2 정보를 알려줘',
        'EC2 리스트 보여줘',
        '현재 실행 중인 EC2 인스턴스',
        'EC2 서버 목록'
    ],
    'ec2_create': [
        'EC2 인스턴스 생성',
        'EC2 서버 만들기',
        '새 EC2 인스턴스 시작',
        'EC2 인스턴스 런칭'
    ],
    's3_list': [
        'S3 버킷 목록',
        'S3 버킷 정보',
        'S3 스토리지 조회'
    ]
}

# 3. 템플릿 임베딩 생성
template_embeddings = {}
for intent, templates in intent_templates.items():
    template_embeddings[intent] = model.encode(templates)

# 4. 사용자 요청 분류
def classify_intent(user_request: str, threshold=0.7):
    user_embedding = model.encode([user_request])
    
    best_match = None
    best_score = 0
    
    for intent, embeddings in template_embeddings.items():
        # 코사인 유사도 계산
        similarities = cosine_similarity(user_embedding, embeddings)
        max_similarity = similarities.max()
        
        if max_similarity > best_score:
            best_score = max_similarity
            best_match = intent
    
    if best_score >= threshold:
        return best_match, best_score
    return None, best_score
```

### 사용할 수 있는 모델
- **한국어**: `jhgan/ko-sroberta-multitask` (추천)
- **다국어**: `paraphrase-multilingual-MiniLM-L12-v2`
- **경량**: `all-MiniLM-L6-v2` (영어)

---

## 2. 로컬 LLM (Ollama)

### 개념
- 로컬에서 실행되는 LLM 모델
- 완전 오프라인, 데이터 프라이버시 보장
- Docker로 쉽게 통합 가능

### 장점
- **완전한 자연어 이해**: LLM의 모든 장점
- **오프라인 동작**: 외부 API 불필요
- **데이터 보안**: 모든 데이터가 로컬에서 처리

### 단점
- **리소스 필요**: GPU 권장, 메모리 많이 사용
- **느림**: 클라우드 LLM보다 느릴 수 있음

### 구현 방법
```python
import httpx

async def classify_with_ollama(user_request: str):
    """Ollama를 사용한 의도 분류"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3:8b",
                "prompt": f"""사용자 요청을 분석하여 의도를 분류하세요:
                
                사용자 요청: {user_request}
                
                가능한 의도:
                - ec2_list: EC2 인스턴스 목록 조회
                - ec2_create: EC2 인스턴스 생성
                - s3_list: S3 버킷 목록 조회
                
                JSON 형식으로 응답: {{"intent": "의도", "confidence": 0.9}}""",
                "stream": False
            },
            timeout=30.0
        )
        return response.json()
```

### Docker 통합
```yaml
# docker-compose.yml
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
```

---

## 3. 의도 분류 모델 (Intent Classification)

### 개념
- 사전 학습된 의도 분류 모델 사용
- 빠른 응답, 경량

### 구현 방법
```python
from transformers import pipeline

# 의도 분류 파이프라인
classifier = pipeline(
    "text-classification",
    model="facebook/bart-large-mnli",
    device=-1  # CPU 사용
)

# 의도 라벨 정의
intent_labels = [
    "EC2 인스턴스 목록 조회",
    "EC2 인스턴스 생성",
    "S3 버킷 목록 조회",
    "일반 질문"
]

def classify_intent(user_request: str):
    # Zero-shot 분류
    result = classifier(user_request, intent_labels)
    return result
```

---

## 4. 하이브리드 접근법 (추천)

### 계층적 폴백 전략

```
1. LLM 시도 (AWS Bedrock, OpenAI 등)
   ↓ 실패
2. 로컬 LLM 시도 (Ollama)
   ↓ 실패
3. Embedding 기반 유사도 매칭
   ↓ 실패
4. 키워드 기반 폴백 (현재 구현)
```

### 구현 예시
```python
class IntentClassifier:
    def __init__(self):
        self.embedding_model = SentenceTransformer('jhgan/ko-sroberta-multitask')
        self.ollama_url = "http://localhost:11434/api/generate"
        self.templates = self._load_intent_templates()
    
    async def classify(self, user_request: str):
        # 1. Embedding 기반 시도
        intent, score = self._classify_with_embedding(user_request)
        if score > 0.75:
            return intent
        
        # 2. Ollama 시도 (있는 경우)
        try:
            intent = await self._classify_with_ollama(user_request)
            if intent:
                return intent
        except:
            pass
        
        # 3. 키워드 기반 폴백
        return self._classify_with_keywords(user_request)
```

---

## 5. 실용적 권장사항

### 현재 상황에 가장 적합한 방법

1. **즉시 구현 가능**: Embedding 기반 유사도 매칭
   - 구현 간단
   - 오프라인 동작
   - 키워드 기반보다 훨씬 우수
   - 추가 설정 불필요

2. **장기적 해결책**: 로컬 LLM (Ollama)
   - 완전한 자연어 이해
   - 데이터 프라이버시
   - 리소스 여유가 있을 때

3. **최적 조합**: 하이브리드 접근
   - LLM → Embedding → Keywords 순서로 폴백
   - 모든 상황에 대응 가능

---

## 구현 우선순위

1. ✅ **Embedding 기반 유사도 매칭** (우선 구현)
   - `sentence-transformers` 라이브러리 추가
   - 의도 템플릿 정의
   - 유사도 기반 매칭 로직

2. 🔄 **로컬 LLM 통합** (선택)
   - Ollama Docker 컨테이너 추가
   - 폴백 체인에 통합

3. 📊 **의도 분류 모델** (고급)
   - 사전 학습 모델 활용
   - 더 정확한 분류 필요 시

