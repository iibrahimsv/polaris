"""
Test Agent - Comprehensive testing for the Enhanced Agent Runner
Tests basic functionality, error handling, and provides diagnostics
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our enhanced agents
try:
    from enhanced_agent_runner import EnhancedAgentRunner, SessionResult, quick_run
    from config import config
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Make sure you have all the required files in the same directory:")
    print("  - config.py")
    print("  - enhanced_agent_runner.py")
    print("  - test_agent.py")
    sys.exit(1)


class AgentTester:
    """Comprehensive agent testing suite"""

    def __init__(self):
        self.runner = None
        self.test_results = []

    def print_header(self):
        """Print test header"""
        print("=" * 70)
        print("🧪 ENHANCED AGENT TESTER")
        print("=" * 70)
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Python Version: {sys.version.split()[0]}")
        print()

    def check_environment(self) -> Dict[str, Any]:
        """Check environment setup"""
        print("🔍 ENVIRONMENT CHECK")
        print("-" * 40)

        env_status = {
            "anthropic_key": bool(os.getenv("ANTHROPIC_API_KEY")),
            "composio_key": bool(os.getenv("COMPOSIO_API_KEY")),
            "composio_enabled": config.enable_composio,
            "model": config.model,
            "python_version": sys.version.split()[0]
        }

        # Check Anthropic API Key
        if env_status["anthropic_key"]:
            key_preview = os.getenv("ANTHROPIC_API_KEY", "")[:10] + "..."
            print(f"✅ Anthropic API Key: {key_preview}")
        else:
            print("❌ Anthropic API Key: Missing")
            print("   Add ANTHROPIC_API_KEY to your .env file")

        # Check Composio setup
        if env_status["composio_enabled"]:
            if env_status["composio_key"]:
                print("✅ Composio: Enabled with API key")
            else:
                print("⚠️  Composio: Enabled but no API key")
        else:
            print("ℹ️  Composio: Disabled")

        # Check Python version
        py_version = sys.version_info
        if py_version >= (3, 10):
            print(f"✅ Python Version: {env_status['python_version']} (Compatible)")
        else:
            print(f"⚠️  Python Version: {env_status['python_version']} (Composio requires 3.10+)")

        # Check model
        print(f"🤖 Model: {env_status['model']}")

        print()
        return env_status

    def check_imports(self) -> bool:
        """Test all required imports"""
        print("📦 IMPORT CHECK")
        print("-" * 40)

        import_tests = [
            ("anthropic", "Anthropic"),
            ("dotenv", "python-dotenv"),
            ("asyncio", "Built-in async support"),
            ("logging", "Built-in logging"),
            ("json", "Built-in JSON"),
            ("datetime", "Built-in datetime")
        ]

        all_good = True

        for module, description in import_tests:
            try:
                __import__(module)
                print(f"✅ {module}: {description}")
            except ImportError:
                print(f"❌ {module}: {description} - MISSING")
                all_good = False

        # Test Composio import
        try:
            import composio_anthropic
            print("✅ composio_anthropic: External tools available")
        except ImportError:
            print("ℹ️  composio_anthropic: Not installed (external tools disabled)")

        print()
        return all_good

    async def test_agent_creation(self) -> bool:
        """Test agent creation"""
        print("🤖 AGENT CREATION TEST")
        print("-" * 40)

        try:
            self.runner = EnhancedAgentRunner()
            print("✅ EnhancedAgentRunner initialized successfully")

            # Test environment creation
            env_id = self.runner.get_or_create_environment("test_env")
            print(f"✅ Environment created: {env_id[:20]}...")

            # Test agent creation
            agent_id = self.runner.create_enhanced_agent(
                "Test Agent",
                "You are a helpful test assistant.",
                "test"
            )
            print(f"✅ Agent created: {agent_id[:20]}...")

            return True

        except Exception as e:
            print(f"❌ Agent creation failed: {str(e)}")
            return False

    async def test_simple_task(self) -> SessionResult:
        """Test a simple task"""
        print("💬 SIMPLE TASK TEST")
        print("-" * 40)

        if not self.runner:
            print("❌ No runner available - skipping task test")
            return SessionResult(success=False, output="", error="No runner")

        test_message = "Say hello and tell me what you can do. Keep it brief."

        print(f"📝 Task: {test_message}")
        print("🚀 Executing...")
        print()

        result = await self.runner.run_agent_task(
            test_message,
            agent_name="Test Assistant",
            timeout=60  # 1 minute timeout for testing
        )

        print()
        print(f"⏱️  Execution time: {result.execution_time:.2f}s")

        if result.success:
            print("✅ Task completed successfully")
            print(f"📄 Response length: {len(result.output)} characters")
        else:
            print(f"❌ Task failed: {result.error}")

        return result

    async def test_code_generation(self) -> SessionResult:
        """Test code generation capability"""
        print("\n💻 CODE GENERATION TEST")
        print("-" * 40)

        if not self.runner:
            print("❌ No runner available - skipping code test")
            return SessionResult(success=False, output="", error="No runner")

        code_task = "Create a simple Python function that calculates the factorial of a number. Include error handling."

        print(f"📝 Task: {code_task}")
        print("🚀 Executing...")
        print()

        result = await self.runner.run_agent_task(
            code_task,
            agent_name="Code Generator",
            timeout=120  # 2 minute timeout for code generation
        )

        print()
        print(f"⏱️  Execution time: {result.execution_time:.2f}s")

        if result.success:
            print("✅ Code generation completed")

            # Check if code contains expected elements
            code_indicators = ["def ", "factorial", "return", "try", "except"]
            found_indicators = [ind for ind in code_indicators if ind in result.output]

            print(f"🔍 Code quality check: {len(found_indicators)}/{len(code_indicators)} indicators found")
            if len(found_indicators) >= 3:
                print("✅ Code appears well-structured")
            else:
                print("⚠️  Code might be incomplete")

        else:
            print(f"❌ Code generation failed: {result.error}")

        return result

    def print_summary(self, env_status: Dict[str, Any], task_results: list):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("📊 TEST SUMMARY")
        print("=" * 70)

        # Environment summary
        print("🔧 Environment:")
        if env_status["anthropic_key"]:
            print("  ✅ Anthropic API configured")
        else:
            print("  ❌ Anthropic API missing")

        if env_status["composio_enabled"]:
            print("  ✅ Composio enabled")
        else:
            print("  ℹ️  Composio disabled")

        # Task results summary
        print(f"\n🧪 Tests Run: {len(task_results)}")
        successful_tasks = [r for r in task_results if r.success]
        print(f"✅ Successful: {len(successful_tasks)}")
        print(f"❌ Failed: {len(task_results) - len(successful_tasks)}")

        if successful_tasks:
            avg_time = sum(r.execution_time for r in successful_tasks) / len(successful_tasks)
            print(f"⏱️  Average execution time: {avg_time:.2f}s")

        # Overall status
        print(f"\n🎯 Overall Status:")
        if env_status["anthropic_key"] and successful_tasks:
            print("✅ AGENT READY - You can start using the enhanced agent!")
            print("\n💡 Next steps:")
            print("   - Run: python interactive_agent.py")
            print("   - Or use: python enhanced_agent_runner.py")
        else:
            print("❌ SETUP INCOMPLETE")
            if not env_status["anthropic_key"]:
                print("   - Add ANTHROPIC_API_KEY to .env file")
            if not successful_tasks:
                print("   - Check the error messages above")

        print()


async def main():
    """Main test function"""
    tester = AgentTester()

    # Print header
    tester.print_header()

    # Check environment
    env_status = tester.check_environment()

    # Check imports
    imports_ok = tester.check_imports()

    if not env_status["anthropic_key"]:
        print("⚠️  Cannot proceed without Anthropic API key")
        print("Add your API key to .env file and try again")
        return

    task_results = []

    # Test agent creation
    agent_created = await tester.test_agent_creation()

    if agent_created:
        # Test simple task
        result1 = await tester.test_simple_task()
        task_results.append(result1)

        # Test code generation
        result2 = await tester.test_code_generation()
        task_results.append(result2)

    # Print summary
    tester.print_summary(env_status, task_results)


# Standalone test functions for quick checks
async def quick_test():
    """Quick test using the quick_run function"""
    print("🚀 QUICK TEST")
    print("-" * 40)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Please set ANTHROPIC_API_KEY in .env file")
        return

    print("Testing basic agent functionality...")

    result = await quick_run(
        "Hello! Please introduce yourself and tell me what you can help with.",
        agent_name="Quick Test Agent"
    )

    if result.success:
        print(f"✅ Quick test successful! ({result.execution_time:.2f}s)")
        print(f"Response preview: {result.output[:100]}...")
    else:
        print(f"❌ Quick test failed: {result.error}")


if __name__ == "__main__":
    print("Choose test mode:")
    print("1. Full comprehensive test (recommended)")
    print("2. Quick test only")

    try:
        choice = input("Enter choice (1 or 2): ").strip()

        if choice == "2":
            asyncio.run(quick_test())
        else:
            asyncio.run(main())

    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
