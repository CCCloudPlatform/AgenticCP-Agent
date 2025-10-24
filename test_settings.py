#!/usr/bin/env python3
"""
Settings 환경 변수 테스트 스크립트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from config.settings import Settings

def test_settings():
    """Settings 환경 변수 테스트"""
    print("=== Settings 환경 변수 테스트 ===")
    
    try:
        # Settings 생성
        settings = Settings()
        
        print(f"✅ Settings 생성 성공")
        print(f"📋 Multi-Agent Bedrock Model ID: {settings.multi_agent.bedrock_model_id}")
        print(f"📋 Multi-Agent Bedrock Temperature: {settings.multi_agent.bedrock_temperature}")
        print(f"📋 Multi-Agent AWS Region: {settings.multi_agent.aws_region}")
        
        # 환경 변수 직접 확인
        import os
        print(f"\n🔍 환경 변수 직접 확인:")
        print(f"MULTI_AGENT_BEDROCK_MODEL_ID: {os.getenv('MULTI_AGENT_BEDROCK_MODEL_ID', 'NOT SET')}")
        print(f"MULTI_AGENT_BEDROCK_TEMPERATURE: {os.getenv('MULTI_AGENT_BEDROCK_TEMPERATURE', 'NOT SET')}")
        print(f"MULTI_AGENT_AWS_REGION: {os.getenv('MULTI_AGENT_AWS_REGION', 'NOT SET')}")
        
    except Exception as e:
        print(f"❌ Settings 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_settings()
