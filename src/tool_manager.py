from typing import Dict, Any, Optional, List
import asyncio
import logging
from .agent import AgentManager, AgentCommand
from datetime import datetime

logger = logging.getLogger(__name__)

class ToolManager:
    def __init__(self, agent_manager: AgentManager):
        self.agent = agent_manager

    async def get_project_status(self, project: str) -> Dict[str, Any]:
        """Get status of a specific project"""
        command = AgentCommand(
            command_type="project",
            action="status",
            parameters={"project": project},
            agent_id="llm",
            timestamp=datetime.now().isoformat()
        )
        return await self.agent.execute_command(command)

    async def update_project(self, project: str) -> Dict[str, Any]:
        """Update a project (git pull, install deps, restart)"""
        command = AgentCommand(
            command_type="project",
            action="update",
            parameters={"project": project},
            agent_id="llm",
            timestamp=datetime.now().isoformat()
        )
        return await self.agent.execute_command(command)

    async def restart_project(self, project: str) -> Dict[str, Any]:
        """Restart a project"""
        command = AgentCommand(
            command_type="project",
            action="restart",
            parameters={"project": project},
            agent_id="llm",
            timestamp=datetime.now().isoformat()
        )
        return await self.agent.execute_command(command)

    async def view_logs(self, project: str, lines: int = 20) -> Dict[str, Any]:
        """View project logs"""
        command = AgentCommand(
            command_type="project",
            action="logs",
            parameters={"project": project, "lines": str(lines)},
            agent_id="llm",
            timestamp=datetime.now().isoformat()
        )
        return await self.agent.execute_command(command)

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools with their descriptions and parameters"""
        return [
            {
                "name": "get_project_status",
                "description": "Get the current status of a project",
                "parameters": {
                    "project": {
                        "type": "string",
                        "description": "Project name (selfi-bot or selfi-miniapp)",
                        "required": True
                    }
                }
            },
            {
                "name": "update_project",
                "description": "Update a project (pull latest code, install dependencies, restart)",
                "parameters": {
                    "project": {
                        "type": "string",
                        "description": "Project name (selfi-bot or selfi-miniapp)",
                        "required": True
                    }
                }
            },
            {
                "name": "restart_project",
                "description": "Restart a project",
                "parameters": {
                    "project": {
                        "type": "string",
                        "description": "Project name (selfi-bot or selfi-miniapp)",
                        "required": True
                    }
                }
            },
            {
                "name": "view_logs",
                "description": "View project logs",
                "parameters": {
                    "project": {
                        "type": "string",
                        "description": "Project name (selfi-bot or selfi-miniapp)",
                        "required": True
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines to show",
                        "default": 20
                    }
                }
            }
        ]

    def register_with_llm(self, llm_handler) -> None:
        """Register all tools with the LLM handler"""
        tools = self.get_available_tools()
        for tool in tools:
            llm_handler.register_function(
                name=tool["name"],
                func=getattr(self, tool["name"]),
                description=tool["description"],
                parameters=tool["parameters"]
            )
