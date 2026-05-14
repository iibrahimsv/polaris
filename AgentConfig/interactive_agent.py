import asyncio
import sys
from typing import Optional
from enhanced_agent_runner import EnhancedAgentRunner, SessionResult
from config import config


class InteractiveAgent:
    """Interactive chat interface with the enhanced agent"""

    def __init__(self):
        self.runner = EnhancedAgentRunner()
        self.session_history = []

    def print_welcome(self):
        """Print welcome message"""
        print("=" * 60)
        print("🤖 Enhanced AI Agent - Ready for Action!")
        print("=" * 60)
        print(f"Model: {config.model}")
        print(f"Composio Tools: {'✅ Enabled' if config.enable_composio else '❌ Disabled'}")
        print()
        print("Example tasks:")
        print("  • 'Create a Python web scraper for news headlines'")
        print("  • 'Analyze this CSV file and create visualizations'")
        print("  • 'Send an email summary of today's GitHub issues'")
        print("  • 'Create a Slack bot that monitors server status'")
        print()
        print("Type 'exit', 'quit', or 'q' to exit")
        print("Type 'clear' to clear history")
        print("Type 'help' for more commands")
        print("-" * 60)

    def print_help(self):
        """Print help information"""
        print("\n📚 Available Commands:")
        print("  exit/quit/q    - Exit the program")
        print("  clear          - Clear conversation history")
        print("  help           - Show this help message")
        print("  status         - Show current configuration")
        print("  history        - Show recent tasks")
        print()

    def print_status(self):
        """Print current status"""
        print(f"\n📊 Current Status:")
        print(f"  Model: {config.model}")
        print(f"  Timeout: {config.timeout}s")
        print(f"  Composio: {'Enabled' if config.enable_composio else 'Disabled'}")
        print(f"  Tasks completed: {len(self.session_history)}")
        print()

    def print_history(self):
        """Print recent task history"""
        if not self.session_history:
            print("\n📝 No tasks completed yet.")
            return

        print(f"\n📝 Recent Tasks (last 5):")
        for i, task in enumerate(self.session_history[-5:], 1):
            status = "✅" if task['success'] else "❌"
            print(f"  {i}. {status} {task['message'][:50]}...")
            print(f"     Time: {task['execution_time']:.1f}s")
        print()

    async def run_interactive(self):
        """Main interactive loop"""
        self.print_welcome()

        while True:
            try:
                user_input = input("\n🎯 Task: ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print("\n👋 Goodbye!")
                    break

                elif user_input.lower() == 'clear':
                    self.session_history.clear()
                    print("🧹 History cleared!")
                    continue

                elif user_input.lower() == 'help':
                    self.print_help()
                    continue

                elif user_input.lower() == 'status':
                    self.print_status()
                    continue

                elif user_input.lower() == 'history':
                    self.print_history()
                    continue

                # Process actual task
                print(f"\n🚀 Processing: {user_input}")
                print("-" * 60)

                result = await self.runner.run_agent_task(user_input)

                # Store in history
                self.session_history.append({
                    'message': user_input,
                    'success': result.success,
                    'execution_time': result.execution_time,
                    'timestamp': asyncio.get_event_loop().time()
                })

                if not result.success:
                    print(f"\n💥 Task failed: {result.error}")
                    print("💡 Try rephrasing your request or check your setup.")

            except KeyboardInterrupt:
                print("\n\n👋 Interrupted by user. Goodbye!")
                break
            except Exception as e:
                print(f"\n💥 Unexpected error: {e}")
                print("💡 Please try again or restart the program.")


if __name__ == "__main__":
    agent = InteractiveAgent()
    asyncio.run(agent.run_interactive())
