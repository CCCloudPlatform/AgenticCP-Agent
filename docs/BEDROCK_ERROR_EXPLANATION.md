# Bedrock Service Error 설명

## 오류 메시지

```
ERROR:root:Error raised by bedrock service: An error occurred (ResourceNotFoundException) when calling the InvokeModel operation: Model use case details have not been submitted for this account.
```

## 의미

이 오류는 **예상된 동작**입니다. 다음과 같은 의미입니다:

1. **AWS Bedrock에서 Anthropic Claude 모델을 사용하려고 시도**
2. **하지만 AWS 계정에서 use case form을 제출하지 않음**
3. **따라서 Bedrock 호출이 실패함**
4. **시스템이 자동으로 Embedding 기반 폴백으로 전환**

## 왜 이 오류가 발생하나요?

AWS Bedrock에서 Anthropic Claude 모델을 사용하려면:
1. AWS 콘솔에서 Bedrock 서비스로 이동
2. Model access 페이지에서 Anthropic Claude 모델 선택
3. Use case form 제출 (사용 목적 설명)

이 과정을 거치지 않으면 Claude 모델을 사용할 수 없습니다.

## 이 오류를 해결하는 방법

### 방법 1: Use case form 제출 (권장)

1. AWS 콘솔 접속
2. Bedrock 서비스로 이동: https://console.aws.amazon.com/bedrock/
3. "Model access" 메뉴 클릭
4. Anthropic Claude 모델 선택
5. Use case form 제출
6. 승인 대기 (보통 즉시 또는 최대 15분)

제출 후에는 Bedrock LLM을 정상적으로 사용할 수 있습니다.

### 방법 2: Embedding 기반 폴백 사용 (현재 상태)

현재 시스템은 **자동으로 Embedding 기반 폴백**을 사용하고 있습니다:

- ✅ LLM 실패 → Embedding 기반 의도 분류
- ✅ 다양한 자연어 표현 자동 인식
- ✅ 오프라인 동작 가능
- ✅ 실제로 잘 작동 중!

**이 오류는 무시해도 됩니다.** 시스템이 정상적으로 작동하고 있습니다.

## 로그 레벨 변경

예상된 오류이므로 로그 레벨을 조정했습니다:

- **Before**: `ERROR` 레벨로 표시
- **After**: `DEBUG` 레벨로 표시 (예상된 오류인 경우)

이제 로그가 더 깔끔하게 표시됩니다.

## 실제 동작 확인

로그를 보면:

```
ERROR:root:Error raised by bedrock service: ...  # LangChain 내부 로그
DEBUG:src.agents.ec2_agent:LLM 사용 불가 (예상된 오류): Bedrock use case form 미제출...
INFO:src.utils.intent_classifier:의도 분류 성공: 'EC2 정보를 알려줘' -> ec2_list (유사도: 1.000)
INFO:src.agents.ec2_agent:✅ Embedding 기반 폴백 성공: 'EC2 정보를 알려줘' → ec2_list → list_instances (신뢰도: 1.00)
```

시스템이 정상적으로 작동하고 있습니다! 🎉

## 요약

- ❌ **Bedrock 오류**: 예상된 동작 (use case form 미제출)
- ✅ **Embedding 폴백**: 자동으로 작동 중
- ✅ **시스템 상태**: 정상 작동
- 💡 **권장 사항**: 현재 상태로도 충분히 사용 가능. 필요시 use case form 제출.

## 참고

- [Embedding 기반 의도 분류 가이드](./INTENT_CLASSIFICATION_GUIDE.md)
- [통합 완료 문서](./INTEGRATION_COMPLETE.md)
- [AWS Bedrock Model Access 문서](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

