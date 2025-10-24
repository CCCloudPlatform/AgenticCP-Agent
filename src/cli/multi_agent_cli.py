"""
Multi-Agent System CLI
Multi-Agent-Test의 메인 애플리케이션을 CLI 도구로 통합
"""

import sys
import asyncio
import logging
from typing import Optional, Dict, Any
import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.syntax import Syntax

from src.config.settings import get_settings, Settings
from src.agents.supervisor_agent import SupervisorAgent
from src.agents.ec2_agent import EC2Agent

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rich 콘솔 설정
console = Console()


class MultiAgentSystem:
    """Multi-Agent System 메인 클래스"""
    
    def __init__(self):
        self.settings = get_settings()
        self.supervisor_agent: Optional[SupervisorAgent] = None
        self.ec2_agent: Optional[EC2Agent] = None
        self.console = Console()
        
    def initialize(self) -> bool:
        """시스템 초기화"""
        try:
            console.print("🚀 Multi-Agent System 초기화 중...", style="bold blue")
            
            # Supervisor Agent 초기화
            self.supervisor_agent = SupervisorAgent(
                openai_api_key=self.settings.multi_agent.openai_api_key
            )
            
            # EC2 Agent 초기화
            self.ec2_agent = EC2Agent(
                openai_api_key=self.settings.multi_agent.openai_api_key,
                aws_access_key=self.settings.multi_agent.aws_access_key_id,
                aws_secret_key=self.settings.multi_agent.aws_secret_access_key,
                region=self.settings.multi_agent.aws_region
            )
            
            console.print("✅ 시스템 초기화 완료!", style="bold green")
            return True
            
        except Exception as e:
            console.print(f"❌ 시스템 초기화 실패: {e}", style="bold red")
            logger.error(f"시스템 초기화 중 오류 발생: {e}")
            return False
    
    def process_request(self, user_request: str, thread_id: str = "default") -> Dict[str, Any]:
        """사용자 요청 처리"""
        if not self.supervisor_agent:
            return {
                "success": False,
                "error": "시스템이 초기화되지 않았습니다.",
                "message": "시스템을 먼저 초기화해주세요."
            }
        
        try:
            console.print(f"\n📝 요청 처리 중: {user_request[:50]}...", style="yellow")
            
            result = self.supervisor_agent.process_request(user_request, thread_id)
            
            if result.get("success"):
                console.print("✅ 요청 처리 완료!", style="green")
            else:
                console.print("❌ 요청 처리 실패", style="red")
            
            return result
            
        except Exception as e:
            logger.error(f"요청 처리 중 오류 발생: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "요청 처리 중 시스템 오류가 발생했습니다."
            }
    
    def display_result(self, result: Dict[str, Any]) -> None:
        """결과 표시"""
        if result.get("success"):
            # 성공 결과 표시
            response = result.get("response", "응답이 없습니다.")
            agent_used = result.get("agent_used", "unknown")
            confidence = result.get("confidence", "N/A")
            routing_info = result.get("routing_info", {})
            
            panel_content = f"""
🤖 사용된 Agent: {agent_used}
🔍 신뢰도: {confidence}
📋 응답:
{response}
            """
            
            # 라우팅 정보가 있으면 추가 표시
            if routing_info and routing_info.get("reasoning"):
                panel_content += f"\n🧠 선택 이유: {routing_info['reasoning']}"
            
            console.print(Panel(
                panel_content,
                title="[bold green]요청 처리 결과 (LangGraph)[/bold green]",
                border_style="green"
            ))
            
        else:
            # 오류 결과 표시
            error = result.get("error", "알 수 없는 오류")
            message = result.get("message", "오류 메시지가 없습니다.")
            
            panel_content = f"""
❌ 오류: {error}

📝 메시지: {message}
            """
            
            console.print(Panel(
                panel_content,
                title="[bold red]오류 발생[/bold red]",
                border_style="red"
            ))
    
    def get_conversation_history(self, thread_id: str = "default") -> None:
        """대화 기록 표시"""
        if not self.supervisor_agent:
            console.print("❌ 시스템이 초기화되지 않았습니다.", style="red")
            return
        
        try:
            history = self.supervisor_agent.get_conversation_history(thread_id)
            
            if not history:
                console.print("📝 대화 기록이 없습니다.", style="yellow")
                return
            
            table = Table(title="대화 기록")
            table.add_column("타입", style="cyan")
            table.add_column("내용", style="white")
            table.add_column("타임스탬프", style="magenta")
            
            for entry in history[-10:]:  # 최근 10개만 표시
                table.add_row(
                    entry.get("type", "Unknown"),
                    entry.get("content", "")[:100] + "..." if len(entry.get("content", "")) > 100 else entry.get("content", ""),
                    entry.get("timestamp", "N/A")
                )
            
            console.print(table)
            
        except Exception as e:
            console.print(f"❌ 대화 기록 조회 중 오류: {e}", style="red")
            logger.error(f"대화 기록 조회 중 오류 발생: {e}")
    
    def show_help(self) -> None:
        """도움말 표시"""
        help_content = """
🎯 Multi-Agent System with LangGraph 사용법

🔧 새로워진 기능 (LangGraph 기반):
• 그래프 기반 워크플로우로 더 정확한 에이전트 라우팅
• 대화 상태 관리 및 스레드별 메모리 유지
• 실시간 신뢰도 점수 및 라우팅 이유 제공
• 스트리밍 지원 및 비동기 처리

📋 지원하는 명령어:
• help - 이 도움말 표시
• history - 대화 기록 조회
• clear - 화면 정리
• quit/exit - 프로그램 종료

🤖 지원하는 Agent:
• EC2 Agent - AWS EC2 인스턴스 관리 (LangChain 기반)
  예시: "EC2 인스턴스 목록 보여줘", "새로운 인스턴스 생성해줘"
  
• General Agent - 일반적인 대화 및 질문
  예시: "안녕하세요", "Python에 대해 설명해줘"

💡 사용 팁:
• 자연어로 요청하세요 - LangGraph가 자동으로 최적의 에이전트를 선택합니다
• EC2 관련 요청은 구체적으로 명시하세요
• 인스턴스 ID는 i-로 시작하는 형식을 사용하세요
• 시스템이 자동으로 제공하는 신뢰도 점수를 확인해보세요
        """
        
        console.print(Panel(
            help_content,
            title="[bold blue]Multi-Agent System 도움말[/bold blue]",
            border_style="blue"
        ))


@click.command()
@click.option('--env-file', default='.env', help='환경 변수 파일 경로')
@click.option('--thread-id', default='default', help='대화 스레드 ID')
@click.option('--interactive/--no-interactive', default=True, help='대화형 모드 활성화')
def main(env_file: str, thread_id: str, interactive: bool):
    """Multi-Agent System 메인 함수"""
    
    # 환경 변수 파일 로드
    if Path(env_file).exists():
        console.print(f"✅ 환경 변수 파일 로드: {env_file}", style="green")
    else:
        console.print(f"⚠️ 환경 변수 파일을 찾을 수 없습니다: {env_file}", style="yellow")
        console.print("env.example 파일을 참조하여 .env 파일을 생성해주세요.", style="yellow")
    
    # 시스템 초기화
    system = MultiAgentSystem()
    if not system.initialize():
        sys.exit(1)
    
    console.print(Panel(
        f"🎉 Multi-Agent System v{system.settings.app_version} 시작!",
        title="[bold green]환영합니다![/bold green]",
        border_style="green"
    ))
    
    system.show_help()
    
    if interactive:
        # 대화형 모드
        console.print("\n💬 대화를 시작하세요! (quit 또는 exit로 종료)", style="bold blue")
        
        while True:
            try:
                user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
                
                if user_input.lower() in ['quit', 'exit', '종료']:
                    console.print("👋 안녕히 가세요!", style="bold green")
                    break
                elif user_input.lower() == 'help':
                    system.show_help()
                    continue
                elif user_input.lower() == 'history':
                    system.get_conversation_history(thread_id)
                    continue
                elif user_input.lower() == 'clear':
                    console.clear()
                    continue
                elif not user_input.strip():
                    continue
                
                # 요청 처리
                result = system.process_request(user_input, thread_id)
                system.display_result(result)
                
            except KeyboardInterrupt:
                console.print("\n👋 프로그램을 종료합니다.", style="bold yellow")
                break
            except Exception as e:
                console.print(f"❌ 예상치 못한 오류: {e}", style="bold red")
                logger.error(f"예상치 못한 오류 발생: {e}")
    
    else:
        # 비대화형 모드 (예시)
        console.print("비대화형 모드에서는 테스트 요청을 처리합니다.", style="yellow")
        
        test_requests = [
            "안녕하세요!",
            "EC2 인스턴스 목록을 보여줘",
            "Python에 대해 설명해줘"
        ]
        
        for request in test_requests:
            console.print(f"\n📝 테스트 요청: {request}")
            result = system.process_request(request, thread_id)
            system.display_result(result)


if __name__ == "__main__":
    main()
