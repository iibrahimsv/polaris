import asyncio
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass

from anthropic import Anthropic
from config import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SessionResult:
    """Result container for agent sessions"""
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0
    session_id: Optional[str] = None


class EnhancedAgentRunner:
    """Production-ready agent runner with error handling and monitoring"""

    def __init__(self):
        self.client = Anthropic(api_key=config.anthropic_api_key)
        self._environment_cache = {}
        self._agent_cache = {}

        # Initialize Composio if enabled
        if config.enable_composio:
            try:
                from composio_anthropic import ComposioToolSet
                self.composio = ComposioToolSet(api_key=config.composio_api_key)
                logger.info("Composio integration enabled")
            except ImportError:
                logger.warning("Composio not installed, disabling integration")
                config.enable_composio = False
                self.composio = None
        else:
            self.composio = None

    def get_or_create_environment(self, env_name: str = "default") -> str:
        """Get cached environment or create new one"""
        if env_name not in self._environment_cache:
            try:
                environment = self.client.beta.environments.create(
                    name=f"enhanced-{env_name}-{datetime.now().strftime('%Y%m%d-%H%M')}",
                    config={
                        "type": config.environment_type,
                        "networking": {"type": config.networking_type},
                    }
                )
                self._environment_cache[env_name] = environment.id
                logger.info(f"Created environment {environment.id}")

            except Exception as e:
                logger.error(f"Failed to create environment: {e}")
                raise

        return self._environment_cache[env_name]

    def create_enhanced_agent(
            self,
            name: str,
            system_prompt: str,
            agent_type: str = "general"
    ) -> str:
        """Create agent with enhanced toolset"""

        cache_key = f"{agent_type}_{hash(system_prompt)}"
        if cache_key in self._agent_cache:
            return self._agent_cache[cache_key]

        try:
            # Base tools
            tools = [{"type": "agent_toolset_20260401"}]

            # Add Composio tools if enabled
            if self.composio:
                try:
                    composio_tools = self.composio.get_tools(actions=config.allowed_tools)
                    tools.extend(composio_tools)
                    logger.info(f"Added {len(composio_tools)} Composio tools")
                except Exception as e:
                    logger.warning(f"Failed to add Composio tools: {e}")

            agent = self.client.beta.agents.create(
                name=name,
                model=config.model,
                system=system_prompt,
                tools=tools
            )

            self._agent_cache[cache_key] = agent.id
            logger.info(f"Created agent {agent.id}")
            return agent.id

        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            raise

    async def run_agent_task(
            self,
            user_message: str,
            agent_name: str = "Enhanced Assistant",
            system_prompt: str = None,
            timeout: int = None
    ) -> SessionResult:
        """Run a single agent task with full error handling"""

        start_time = datetime.now()
        timeout = timeout or config.timeout

        # Default system prompt
        if system_prompt is None:
            system_prompt = """You are an expert AI assistant with access to powerful tools.
            With great power comes great responsibility. It is your duty to make the best judgements when writing code. 
            Ethically, morally, and diligence you are free to explore new ideas and think beyond imagination. Do not limit
            yourself to a single solution, find different ways 
            to solve problems.

When working on tasks:
1. Break down complex problems into smaller steps
2. Use tools when appropriate, but explain your approach first
3. Provide clear, actionable results
4. Handle errors gracefully and suggest alternatives
5. Always validate your outputs

Be precise, helpful, and thorough in your responses."""

        try:
            # Create/get agent and environment
            agent_id = self.create_enhanced_agent(agent_name, system_prompt)
            env_id = self.get_or_create_environment()

            # Create session
            session = self.client.beta.sessions.create(
                agent=agent_id,
                environment_id=env_id,
                timeout=timeout
            )

            logger.info(f"Created session {session.id}")

            # Run session with streaming
            output_parts = []

            with self.client.beta.sessions.events.stream(session.id) as stream:
                self.client.beta.sessions.events.send(
                    session.id,
                    events=[{
                        "type": "user.message",
                        "content": [{"type": "text", "text": user_message}]
                    }]
                )

                for event in stream:
                    if event.type == "agent.message":
                        for block in event.content:
                            if hasattr(block, 'text'):
                                output_parts.append(block.text)
                                print(block.text, end="", flush=True)

                    elif event.type == "agent.tool_use":
                        tool_info = f"\n[Using tool: {event.name}]"
                        output_parts.append(tool_info)
                        print(tool_info)
                        logger.info(f"Tool used: {event.name}")

                    elif event.type == "session.status_idle":
                        if event.stop_reason.type != "requires_action":
                            break

                    elif event.type == "session.status_terminated":
                        logger.warning("Session terminated")
                        break

            execution_time = (datetime.now() - start_time).total_seconds()
            full_output = "".join(output_parts)

            print(f"\n\n✅ Task completed in {execution_time:.2f}s")

            return SessionResult(
                success=True,
                output=full_output,
                execution_time=execution_time,
                session_id=session.id
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Agent task failed: {str(e)}"
            logger.error(error_msg)
            print(f"\n❌ {error_msg}")

            return SessionResult(
                success=False,
                output="",
                error=error_msg,
                execution_time=execution_time
            )


# Convenience function for quick testing
async def quick_run(message: str, **kwargs) -> SessionResult:
    """Quick way to run a single task"""
    runner = EnhancedAgentRunner()
    return await runner.run_agent_task(message, **kwargs)


if __name__ == "__main__":
    # Example usage
    async def main():
        runner = EnhancedAgentRunner()

        result = await runner.run_agent_task(
            """Welcome to the Imagination Lab! Today we're building worlds, breaking boundaries, and creating magic.

        I need you to be my Imagination Architect. Here's the challenge:

        BUILD ME A CREATIVE PLAYGROUND:
        Look at my current situation and design a personalized creative adventure that:
        - Uses my existing skills in unexpected ways
        - Introduces me to something I've never tried before  
        - Creates a tangible result I can share or be proud of
        - Feels like play but teaches me something profound
        - Can evolve and grow over time

        THE TWIST:
        Make it feel like a quest or game with:
        - Clear but exciting objectives
        - Hidden discoveries along the way
        - Multiple paths to explore
        - A rewarding creative outcome

        Ask me 3 questions about what excites me most right now, then architect the perfect creative experience. Let's build something extraordinary together!""",
            agent_name="Imagination Architect & Experience Designer"
        )

        if result.success:
            print(f"\n🎉 Success! Output length: {len(result.output)} chars")
        else:
            print(f"\n💥 Failed: {result.error}")


    asyncio.run(main())
