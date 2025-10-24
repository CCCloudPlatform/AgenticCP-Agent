#!/usr/bin/env python3
"""
S3와 EC2 Agent 테스트 스크립트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from agents.s3_agent import S3Agent
from agents.ec2_agent import EC2Agent
from config.settings import Settings

def test_s3_agent():
    """S3 Agent 테스트"""
    print("=== S3 Agent 테스트 시작 ===")
    try:
        # Settings 생성
        settings = Settings()
        
        # S3 Agent 생성
        s3_agent = S3Agent(settings=settings)
        print("✅ S3 Agent 생성 성공")
        
        # 간단한 테스트 메시지
        test_message = "S3 버킷 목록을 조회해주세요"
        print(f"테스트 메시지: {test_message}")
        
        # Agent 실행 (비동기)
        import asyncio
        result = asyncio.run(s3_agent.process_request(test_message))
        print(f"✅ S3 Agent 응답: {result}")
        
    except Exception as e:
        print(f"❌ S3 Agent 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

def test_ec2_agent():
    """EC2 Agent 테스트"""
    print("\n=== EC2 Agent 테스트 시작 ===")
    try:
        # Settings 생성
        settings = Settings()
        
        # EC2 Agent 생성
        ec2_agent = EC2Agent(settings=settings)
        print("✅ EC2 Agent 생성 성공")
        
        # 간단한 테스트 메시지
        test_message = "EC2 인스턴스 목록을 조회해주세요"
        print(f"테스트 메시지: {test_message}")
        
        # Agent 실행 (비동기)
        import asyncio
        result = asyncio.run(ec2_agent.process_request(test_message))
        print(f"✅ EC2 Agent 응답: {result}")
        
    except Exception as e:
        print(f"❌ EC2 Agent 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("AWS Agent 테스트 시작...")
    
    # S3 Agent 테스트
    test_s3_agent()
    
    # EC2 Agent 테스트
    test_ec2_agent()
    
    print("\n=== 테스트 완료 ===")
