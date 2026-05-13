"""One-time setup: create the Managed Agent. Run once, copy the IDs into .env.

Re-running creates a *new* agent (accumulates orphans). To update behavior
later, use client.beta.agents.update(agent_id, ...) instead — that creates
a new version of the existing agent.
"""

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()

agent = client.beta.agents.create(
    name="Coding Assistant",
    model="claude-opus-4-7",
    system="You are a helpful coding assistant. Write clean, well-documented code.",
    tools=[
        {"type": "agent_toolset_20260401"},
    ],
)

print(f"Agent ID: {agent.id}, version: {agent.version}")
print()
print("Copy these into your .env:")
print(f"AGENT_ID={agent.id}")
print(f"AGENT_VERSION={agent.version}")
