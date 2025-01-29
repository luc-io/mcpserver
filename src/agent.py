from typing import List, Optional
from pydantic import BaseModel
import json
from datetime import datetime

class AgentCommand(BaseModel):
    command_type: str  # e.g., "droplet", "system", "project"
    action: str       # e.g., "create", "status", "list"
    parameters: dict  # command-specific parameters
    agent_id: str    # identifier for the LLM agent
    timestamp: str = datetime.now().isoformat()

class AgentResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
    timestamp: str = datetime.now().isoformat()

class AgentManager:
    def __init__(self):
        self.allowed_commands = {
            "droplet": ["list", "status", "create", "delete", "reboot", "power_on", "power_off"],
            "system": ["status", "process"],
            "project": ["deploy", "update", "rollback"]
        }
    
    def validate_command(self, command: AgentCommand) -> bool:
        if command.command_type not in self.allowed_commands:
            return False
        if command.action not in self.allowed_commands[command.command_type]:
            return False
        return True
    
    def log_command(self, command: AgentCommand, response: AgentResponse):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": command.agent_id,
            "command": command.dict(),
            "response": response.dict()
        }
        # TODO: Implement proper logging
        print(f"Agent Log: {json.dumps(log_entry, indent=2)}")
    
    async def execute_command(self, command: AgentCommand) -> AgentResponse:
        if not self.validate_command(command):
            return AgentResponse(
                success=False,
                message=f"Invalid command: {command.command_type}.{command.action}"
            )
        
        try:
            # Execute the command based on type and action
            # This will be implemented by the server
            return AgentResponse(
                success=True,
                message=f"Executed {command.command_type}.{command.action}",
                data={"command": command.dict()}
            )
        except Exception as e:
            return AgentResponse(
                success=False,
                message=f"Error executing command: {str(e)}"
            )
