"""
Diagnostic Agent - Find the exact problem preventing agent creation
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()


async def diagnose_agent_issue():
    """Step-by-step diagnosis"""
    print("🔍 DETAILED DIAGNOSIS")
    print("=" * 50)

    # Step 1: Check API Key
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found")
        return False

    print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}")

    # Step 2: Test Anthropic import and basic connection
    try:
        from anthropic import Anthropic
        print("✅ Anthropic library imported")
    except ImportError as e:
        print(f"❌ Cannot import Anthropic: {e}")
        print("Run: pip install anthropic")
        return False

    # Step 3: Test basic Anthropic client
    try:
        client = Anthropic(api_key=api_key)
        print("✅ Anthropic client created")
    except Exception as e:
        print(f"❌ Client creation failed: {e}")
        return False

    # Step 4: Test supported models
    print("\n🤖 Testing model compatibility...")

    supported_models = [
        "claude-3-5-sonnet-20240620",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307"
    ]

    for model in supported_models:
        print(f"Testing {model}...")

        try:
            # Try creating an environment first
            environment = client.beta.environments.create(
                name=f"test-{model.split('-')[2]}",
                config={"type": "cloud", "networking": {"type": "unrestricted"}}
            )
            print(f"  ✅ Environment created: {environment.id}")

            # Try creating agent
            agent = client.beta.agents.create(
                name=f"Test Agent - {model}",
                model=model,
                system="You are a helpful test assistant.",
                tools=[{"type": "agent_toolset_20260401"}]
            )
            print(f"  ✅ Agent created successfully with {model}")
            print(f"  Agent ID: {agent.id}")

            # Clean up
            try:
                # Note: Environment cleanup might not be available in beta
                pass
            except:
                pass

            return True, model, agent.id, environment.id

        except Exception as e:
            print(f"  ❌ Failed with {model}: {e}")
            continue

    print("❌ All models failed")
    return False


async def test_working_model(model, agent_id, env_id):
    """Test a working model with a simple task"""
    print(f"\n🧪 Testing agent {agent_id} with model {model}")
    print("-" * 50)

    try:
        from anthropic import Anthropic
        client = Anthropic()

        # Create session
        session = client.beta.sessions.create(
            agent=agent_id,
            environment_id=env_id
        )
        print(f"✅ Session created: {session.id}")

        # Test simple interaction
        print("📝 Sending test message...")

        response_parts = []
        with client.beta.sessions.events.stream(session.id) as stream:
            client.beta.sessions.events.send(
                session.id,
                events=[{
                    "type": "user.message",
                    "content": [{"type": "text", "text": "Say hello and tell me what model you are."}]
                }]
            )

            for event in stream:
                if event.type == "agent.message":
                    for block in event.content:
                        if hasattr(block, 'text'):
                            response_parts.append(block.text)
                            print(block.text, end="", flush=True)

                elif event.type == "session.status_idle":
                    if event.stop_reason.type != "requires_action":
                        break

        response = "".join(response_parts)
        print(f"\n✅ Test successful! Response length: {len(response)} chars")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


async def main():
    """Main diagnostic function"""
    print("🚨 AGENT CREATION DIAGNOSTIC")
    print("=" * 60)

    result = await diagnose_agent_issue()

    if isinstance(result, tuple) and result[0]:
        success, model, agent_id, env_id = result
        print(f"\n🎉 Found working configuration!")
        print(f"Model: {model}")
        print(f"Agent: {agent_id}")
        print(f"Environment: {env_id}")

        # Test the working agent
        test_success = await test_working_model(model, agent_id, env_id)

        if test_success:
            print(f"\n✅ SOLUTION FOUND!")
            print(f"Update your config.py with:")
            print(f'model: str = "{model}"')

            # Create a fixed config file
            config_content = f'''import os
from dataclasses import dataclass
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AgentConfig:
    """Centralized configuration management"""

    # API Keys
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    composio_api_key: str = os.getenv("COMPOSIO_API_KEY", "")

    # Agent Settings - WORKING MODEL
    model: str = "{model}"  # ✅ TESTED AND WORKING
    max_tokens: int = 4096
    timeout: int = 300

    # Environment Settings
    environment_type: str = "cloud"
    networking_type: str = "unrestricted"  # Use unrestricted for now
    resource_limits: Dict[str, str] = None

    # Tool Configuration
    enable_composio: bool = False  # Disabled for compatibility
    allowed_tools: list = None

    def __post_init__(self):
        if self.resource_limits is None:
            self.resource_limits = {{
                "cpu": "2",
                "memory": "4GB", 
                "disk": "10GB"
            }}

        if self.allowed_tools is None:
            self.allowed_tools = [
                "GITHUB_CREATE_ISSUE", "GMAIL_SEND_EMAIL", 
                "SLACK_SEND_MESSAGE", "GOOGLESHEETS_CREATE_SHEET"
            ]

    def validate(self) -> bool:
        """Validate configuration"""
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        if self.enable_composio and not self.composio_api_key:
            print("Warning: COMPOSIO_API_KEY not found, disabling Composio tools")
            self.enable_composio = False

        return True

# Global config instance
config = AgentConfig()
config.validate()
'''

            with open("config_fixed.py", "w") as f:
                f.write(config_content)

            print(f"\n💾 Created config_fixed.py with working settings")
            print(f"Replace your config.py with this file or copy the model setting")

    else:
        print(f"\n❌ No working configuration found")
        print(f"This might be a:")
        print(f"  - API key issue (check permissions)")
        print(f"  - Regional availability issue")
        print(f"  - Account access issue (Beta not enabled)")
        print(f"\nTry:")
        print(f"  1. Check your Anthropic console")
        print(f"  2. Verify API key has Beta access")
        print(f"  3. Try different API key")


if __name__ == "__main__":
    asyncio.run(main())
