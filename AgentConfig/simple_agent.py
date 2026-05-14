"""
Simple Agent - Works with standard Anthropic API (no beta required)
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()


class SimpleAgent:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.conversation_history = []

    async def chat(self, user_message: str, system_prompt: str = None) -> str:
        """Simple chat using standard Anthropic API"""

        if system_prompt is None:
            system_prompt = """You are a helpful AI assistant. You can help with:

- Writing and debugging code
- Explaining complex topics
- Analyzing data and problems  
- Creative writing and brainstorming
- Research and information gathering

Be concise, accurate, and helpful in your responses."""

        try:
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })

            # Keep only last 10 messages to avoid token limits
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

            print(f"🤖 Thinking...")

            # Make API call
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",  # Latest available model
                max_tokens=4000,
                system=system_prompt,
                messages=self.conversation_history
            )

            # Extract response text
            assistant_response = response.content[0].text

            # Add to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_response
            })

            return assistant_response

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        print("🧹 Conversation history cleared")


async def interactive_mode():
    """Interactive chat mode"""
    agent = SimpleAgent()

    print("=" * 60)
    print("🤖 SIMPLE AI AGENT - Standard API")
    print("=" * 60)
    print("This works with any Anthropic API key (no beta required)")
    print()
    print("Commands:")
    print("  'exit' or 'quit' - Exit")
    print("  'clear' - Clear conversation history")
    print("  'help' - Show this help")
    print("-" * 60)

    while True:
        try:
            user_input = input("\n💬 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("👋 Goodbye!")
                break

            elif user_input.lower() == 'clear':
                agent.clear_history()
                continue

            elif user_input.lower() == 'help':
                print("\n📚 Available Commands:")
                print("  exit/quit/q - Exit the program")
                print("  clear       - Clear conversation history")
                print("  help        - Show this help")
                continue

            # Process message
            start_time = datetime.now()
            response = await agent.chat(user_input)
            end_time = datetime.now()

            execution_time = (end_time - start_time).total_seconds()

            print(f"\n🤖 Assistant: {response}")
            print(f"\n⏱️  Response time: {execution_time:.2f}s")

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user. Goodbye!")
            break
        except Exception as e:
            print(f"\n💥 Unexpected error: {e}")


async def single_task(message: str) -> str:
    """Run a single task"""
    agent = SimpleAgent()
    return await agent.chat(message)


# Quick test function
async def test_simple_agent():
    """Test the simple agent"""
    print("🧪 Testing Simple Agent...")

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Please set ANTHROPIC_API_KEY in .env file")
        return

    agent = SimpleAgent()

    # Test message
    test_message = "Create a Python function that calculates the factorial of a number. Include error handling."

    print(f"📝 Test task: {test_message}")

    start_time = datetime.now()
    response = await agent.chat(test_message)
    end_time = datetime.now()

    execution_time = (end_time - start_time).total_seconds()

    if "def " in response and "factorial" in response:
        print(f"✅ Test successful! ({execution_time:.2f}s)")
        print(f"📄 Response length: {len(response)} characters")
        print(f"🔍 Contains function definition: Yes")
        return True
    else:
        print(f"⚠️  Test completed but response might be incomplete")
        print(f"Response preview: {response[:200]}...")
        return False


if __name__ == "__main__":
    print("Choose mode:")
    print("1. Interactive chat")
    print("2. Single test")

    try:
        choice = input("Enter choice (1 or 2): ").strip()

        if choice == "2":
            asyncio.run(test_simple_agent())
        else:
            asyncio.run(interactive_mode())

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
