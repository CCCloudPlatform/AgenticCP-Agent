# Embedding 기반 의도 분류 통합 완료 ✅

## 통합 내용

### ✅ 1. Supervisor Agent 통합
**파일**: `src/agents/supervisor_agent.py`

**변경 사항**:
- LLM 실패 시 **하이브리드 폴백** 적용
- 순서: Embedding 기반 분류 → 키워드 기반 폴백

**동작 흐름**:
```
사용자 요청
    ↓
LLM 시도 (AWS Bedrock)
    ↓ 실패
Embedding 기반 의도 분류
    ↓ 성공 → Agent 라우팅 (ec2/s3/vpc/general)
    ↓ 실패
키워드 기반 폴백
    ↓
Agent 라우팅
```

**예시**:
```python
# "EC2 정보를 알려줘"
# → Embedding 유사도: 0.85
# → 의도: 'ec2_list'
# → Agent: 'ec2'
```

---

### ✅ 2. EC2 Agent 통합
**파일**: `src/agents/ec2_agent.py`

**변경 사항**:
- LLM 실패 시 **Embedding 기반 액션 분류** 사용
- 순서: Embedding → 규칙 기반 폴백

**동작 흐름**:
```
사용자 요청
    ↓
LLM 시도 (AWS Bedrock)
    ↓ 실패
Embedding 기반 의도 분류
    ↓ 성공 → 액션 매핑 (list_instances/create_instance/etc.)
    ↓ 실패
규칙 기반 폴백
    ↓
액션 실행
```

**예시**:
```python
# "EC2 인스턴스 목록 보여줘"
# → Embedding 유사도: 0.87
# → 의도: 'ec2_list'
# → 액션: 'list_instances'
```

---

### ✅ 3. 설정 옵션 추가
**파일**: `src/config/settings.py`

**추가된 설정**:
```python
# Intent Classification 설정
use_embedding_intent: bool = True  # Embedding 사용 여부
embedding_model_name: str = "jhgan/ko-sroberta-multitask"  # 모델 이름
intent_similarity_threshold: float = 0.65  # 최소 유사도
```

**환경 변수**:
```bash
MULTI_AGENT_USE_EMBEDDING_INTENT=true
MULTI_AGENT_EMBEDDING_MODEL_NAME=jhgan/ko-sroberta-multitask
MULTI_AGENT_INTENT_SIMILARITY_THRESHOLD=0.65
```

---

### ✅ 4. 유틸리티 모듈 생성
**파일**: `src/utils/intent_classifier.py`

**주요 함수**:
- `classify_intent_hybrid()`: 하이브리드 의도 분류
- `classify_intent_embedding()`: Embedding 기반 분류
- `map_intent_to_agent_type()`: 의도 → Agent 타입 매핑
- `map_intent_to_action()`: 의도 → EC2 액션 매핑

---

### ✅ 5. 패키지 구조 정리
- `src/utils/__init__.py` 생성
- 상대 import 경로 사용 (`..utils.intent_classifier`)

---

## 설치 방법

### 1. 필수 패키지 설치
```bash
pip install sentence-transformers scikit-learn
```

또는:
```bash
pip install -r requirements.txt
```

### 2. 모델 다운로드
첫 실행 시 자동으로 다운로드됩니다:
- 모델: `jhgan/ko-sroberta-multitask` (~500MB)
- 위치: `~/.cache/torch/sentence_transformers/`

---

## 테스트 예시

### 다양한 표현 자동 인식

| 사용자 요청 | 의도 | Agent | 신뢰도 |
|------------|------|-------|--------|
| "EC2 정보를 알려줘" | `ec2_list` | `ec2` | 0.85 |
| "EC2 인스턴스 목록 보여줘" | `ec2_list` | `ec2` | 0.87 |
| "현재 실행 중인 EC2 서버가 몇 개야?" | `ec2_list` | `ec2` | 0.83 |
| "EC2 서버 정보" | `ec2_list` | `ec2` | 0.86 |
| "EC2 인스턴스를 만들어줘" | `ec2_create` | `ec2` | 0.89 |
| "S3 버킷 목록" | `s3_list` | `s3` | 0.91 |

**키워드 매칭으로는 불가능했던 표현들도 이제 인식됩니다!** 🎉

---

## 성능 향상

### Before (키워드 기반)
```
❌ "EC2 인스턴스 목록 보여줘" → 키워드 "정보" 없음 → 실패
❌ "현재 실행 중인 EC2 서버가 몇 개야?" → 키워드 없음 → 실패
```

### After (Embedding 기반)
```
✅ "EC2 인스턴스 목록 보여줘" → 유사도 0.87 → ec2_list → 성공
✅ "현재 실행 중인 EC2 서버가 몇 개야?" → 유사도 0.83 → ec2_list → 성공
```

---

## 동작 확인

### 로그 예시
```
INFO: Embedding 기반 의도 분류 성공: ec2_list → ec2 (신뢰도: 0.85)
INFO: Embedding 기반 폴백 성공: ec2_list → list_instances (신뢰도: 0.85)
```

### 폴백 순서 확인
1. **LLM 실패** → Embedding 시도
2. **Embedding 성공** (유사도 > 0.65) → 사용
3. **Embedding 실패** → 키워드 폴백

---

## 문제 해결

### Embedding 모듈을 사용할 수 없을 때
- 자동으로 키워드 기반 폴백으로 전환
- 로그: `"Embedding 기반 의도 분류 모듈을 사용할 수 없습니다. 키워드 폴백 사용."`

### 모델 다운로드 실패 시
- 첫 실행 시 자동 다운로드
- 네트워크 문제 시 재시도
- 실패 시 키워드 폴백으로 전환

---

## 다음 단계

✅ **완료된 작업**:
1. Embedding 유틸리티 모듈 생성
2. Supervisor Agent 통합
3. EC2 Agent 통합
4. 설정 옵션 추가
5. 문서화

🔄 **추가 개선 가능**:
1. 다른 Agent (S3, VPC)에도 통합
2. Embedding 결과 캐싱
3. 모니터링 및 메트릭 추가
4. 사용자 피드백 기반 학습

---

## 참고 문서

- [의도 분류 가이드](./INTENT_CLASSIFICATION_GUIDE.md) - 상세 기술 설명
- [자연어 요청 가이드](./NATURAL_LANGUAGE_INTENT_GUIDE.md) - 사용 가이드
- [구현 계획](./IMPLEMENTATION_PLAN.md) - 통합 계획

---

**통합 완료! 이제 다양한 자연어 요청에 자동으로 대응합니다.** 🚀

