from typing import List, Optional
from pydantic import BaseModel
import json
import subprocess
from datetime import datetime
import os

class AgentCommand(BaseModel):
    command_type: str  # e.g., "droplet", "system", "project", "shell"
    action: str       # e.g., "create", "status", "list", "execute"
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
            "project": ["deploy", "update", "rollback"],
            "shell": ["execute"]  # Added shell execution
        }
        
        # Define safe directories where shell commands can be executed
        self.safe_directories = [
            "/var/www/mcpserver",
            "/var/www/mcpserver/examples",
            "/var/www/mcpserver/src"
        ]
        
        # Define allowed shell commands
        self.allowed_shell_commands = [
            "cd", "python3", "pip", "git", "ls", "cat"
        ]
    
    def validate_command(self, command: AgentCommand) -> bool:
        if command.command_type not in self.allowed_commands:
            return False
        if command.action not in self.allowed_commands[command.command_type]:
            return False
        
        # Additional validation for shell commands
        if command.command_type == "shell":
            return self._validate_shell_command(command.parameters.get("command", ""))
        return True
    
    def _validate_shell_command(self, command: str) -> bool:
        # Split command into parts
        parts = command.split()
        if not parts:
            return False
            
        # Check if base command is allowed
        base_cmd = parts[0]
        if base_cmd not in self.allowed_shell_commands:
            return False
            
        # Special validation for cd command
        if base_cmd == "cd":
            if len(parts) != 2:
                return False
            target_dir = os.path.abspath(parts[1])
            return any(target_dir.startswith(safe_dir) for safe_dir in self.safe_directories)
            
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
            if command.command_type == "shell":
                return await self._execute_shell_command(command)
            
            # Handle other command types...
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
    
    async def _execute_shell_command(self, command: AgentCommand) -> AgentResponse:
        shell_command = command.parameters.get("command", "")
        if not shell_command:
            return AgentResponse(success=False, message="No shell command provided")
            
        try:
            # Execute the command
            process = subprocess.run(
                shell_command,
                shell=True,
                cwd="/var/www/mcpserver",  # Set base directory
                capture_output=True,
                text=True,
                timeout=30  # Set timeout
            )
            
            return AgentResponse(
                success=process.returncode == 0,
                message="Command executed successfully" if process.returncode == 0 else "Command failed",
                data={
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "return_code": process.returncode
                }
            )
        except subprocess.TimeoutExpired:
            return AgentResponse(success=False, message="Command timed out")
        except Exception as e:
            return AgentResponse(success=False, message=f"Error executing shell command: {str(e)}")
