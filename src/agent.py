from typing import List, Optional
from pydantic import BaseModel
import json
import subprocess
from datetime import datetime
import os

class AgentCommand(BaseModel):
    command_type: str
    action: str
    parameters: dict
    agent_id: str
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
            "shell": ["execute"]
        }
        
        self.allowed_shell_commands = [
            "ls", "cd", "python3", "pip", "git"
        ]
        
        self.safe_directories = [
            "/var/www/mcpserver",
            "/var/www/mcpserver/examples",
            "/var/www/mcpserver/src"
        ]

    def validate_command(self, command: AgentCommand) -> bool:
        # Basic command validation
        if command.command_type not in self.allowed_commands:
            raise ValueError(f"Invalid command type: {command.command_type}")
        
        if command.action not in self.allowed_commands[command.command_type]:
            raise ValueError(f"Invalid action for {command.command_type}: {command.action}")
        
        # Shell command validation
        if command.command_type == "shell":
            shell_cmd = command.parameters.get("command", "").split()[0]
            if shell_cmd not in self.allowed_shell_commands:
                raise ValueError(f"Shell command not allowed: {shell_cmd}")
            
            # Validate working directory
            working_dir = self._extract_working_dir(command.parameters.get("command", ""))
            if working_dir and not any(working_dir.startswith(safe_dir) for safe_dir in self.safe_directories):
                raise ValueError(f"Directory not allowed: {working_dir}")
        
        return True

    def _extract_working_dir(self, command: str) -> Optional[str]:
        if "cd" in command:
            parts = command.split()
            try:
                cd_index = parts.index("cd")
                if len(parts) > cd_index + 1:
                    return os.path.abspath(parts[cd_index + 1])
            except ValueError:
                pass
        return None

    async def execute_command(self, command: AgentCommand) -> AgentResponse:
        try:
            # Validate the command
            self.validate_command(command)
            
            # Execute based on command type
            if command.command_type == "shell":
                return await self._execute_shell_command(command)
            
            return AgentResponse(
                success=True,
                message=f"Executed {command.command_type}.{command.action}",
                data={"command": command.dict()}
            )
            
        except ValueError as e:
            return AgentResponse(
                success=False,
                message=str(e),
                data={"error_type": "validation_error"}
            )
        except Exception as e:
            return AgentResponse(
                success=False,
                message=f"Error executing command: {str(e)}",
                data={"error_type": "execution_error"}
            )

    async def _execute_shell_command(self, command: AgentCommand) -> AgentResponse:
        try:
            shell_command = command.parameters.get("command", "")
            if not shell_command:
                return AgentResponse(
                    success=False,
                    message="No shell command provided"
                )
            
            # Execute the command
            process = subprocess.run(
                shell_command,
                shell=True,
                cwd="/var/www/mcpserver",
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Prepare response
            response_data = {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "return_code": process.returncode,
                "command": shell_command
            }
            
            # Log the execution
            self._log_execution(command, response_data)
            
            return AgentResponse(
                success=process.returncode == 0,
                message="Command executed successfully" if process.returncode == 0 else "Command failed",
                data=response_data
            )
            
        except subprocess.TimeoutExpired:
            return AgentResponse(
                success=False,
                message="Command timed out after 30 seconds",
                data={"error_type": "timeout"}
            )
        except Exception as e:
            return AgentResponse(
                success=False,
                message=f"Error executing shell command: {str(e)}",
                data={"error_type": "execution_error"}
            )

    def _log_execution(self, command: AgentCommand, result: dict):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": command.agent_id,
            "command": command.dict(),
            "result": result
        }
        # TODO: Implement proper logging to file
        print(f"Agent Log: {json.dumps(log_entry, indent=2)}")
