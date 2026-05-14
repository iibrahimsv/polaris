import os
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

    # Agent Settings
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    timeout: int = 300  # 5 minutes

    # Environment Settings
    environment_type: str = "cloud"
    networking_type: str = "unrestricted"
    resource_limits: Dict[str, str] = None

    # Tool Configuration
    enable_composio: bool = False
    allowed_tools: list = None

    def __post_init__(self):
        if self.resource_limits is None:
            self.resource_limits = {
                "cpu": "2",
                "memory": "4GB",
                "disk": "10GB"
            }

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
