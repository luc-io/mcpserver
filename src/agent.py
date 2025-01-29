from typing import List, Optional
from pydantic import BaseModel
import json
import subprocess
from datetime import datetime
import os
import shlex

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
        
        # Define base commands and their allowed arguments
        self.allowed_shell_commands = {
            "ls": ["-l", "-a", "-la", "-al"],
            "cd": [],
            "python3": ["-m", "-V", "-c"],
            "pip": ["install", "list", "freeze"],
            "git": ["pull", "status", "log"]
        }
        
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
            shell_command = command.parameters.get("command", "")
            if not shell_command:
                raise ValueError("Empty shell command")
            
            # Parse command into parts
            try:
                cmd_parts = shlex.split(shell_command)
            except Exception as e:
                raise ValueError(f"Invalid shell command format: {str(e)}")
            
            if not cmd_parts:
                raise ValueError("Empty shell command")
            
            base_cmd = cmd_parts[0]
            if base_cmd not in self.allowed_shell_commands:
                raise ValueError(f"Shell command not allowed: {base_cmd}")
            
            # Validate arguments for specific commands
            if base_cmd == "ls":
                self._validate_ls_command(cmd_parts)
            elif base_cmd == "cd":
                self._validate_cd_command(cmd_parts)
            
            # Validate working directory for all commands
            self._validate_directory(cmd_parts)
        
        return True

    def _validate_ls_command(self, cmd_parts: List[str]):
        """Validate ls command and its arguments"""
        for arg in cmd_parts[1:]:
            if arg.startswith("-"):
                if arg not in self.allowed_shell_commands["ls"]:
                    raise ValueError(f"Invalid ls argument: {arg}")
            else:
                # Validate directory argument
                abs_path = os.path.abspath(arg)
                if not any(abs_path.startswith(safe_dir) for safe_dir in self.safe_directories):
                    raise ValueError(f"Directory not allowed: {arg}")

    def _validate_cd_command(self, cmd_parts: List[str]):
        """Validate cd command"""
        if len(cmd_parts) != 2:
            raise ValueError("cd command requires exactly one argument")
        
        target_dir = cmd_parts[1]
        abs_path = os.path.abspath(target_dir)
        if not any(abs_path.startswith(safe_dir) for safe_dir in self.safe_directories):
            raise ValueError(f"Directory not allowed: {target_dir}")

    def _validate_directory(self, cmd_parts: List[str]):
        """Validate any directory arguments in the command"""
        for part in cmd_parts:
            if os.path.sep in part:
                abs_path = os.path.abspath(part)
                if not any(abs_path.startswith(safe_dir) for safe_dir in self.safe_directories):
                    raise ValueError(f"Path not allowed: {part}")

    async def _execute_shell_command(self, command: AgentCommand) -> AgentResponse:
        try:
            shell_command = command.parameters.get("command", "")
            if not shell_command:
                return AgentResponse(
                    success=False,
                    message="No shell command provided"
                )
            
            # Validate command before execution
            try:
                self.validate_command(command)
            except ValueError as e:
                return AgentResponse(
                    success=False,
                    message=str(e)
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
            
            # Prepare response data
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
        """Log command execution"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": command.agent_id,
            "command": command.dict(),
            "result": result
        }
        # TODO: Implement proper logging to file
        print(f"Agent Log: {json.dumps(log_entry, indent=2)}")

    async def execute_command(self, command: AgentCommand) -> AgentResponse:
        """Execute a command"""
        try:
            if command.command_type == "shell":
                return await self._execute_shell_command(command)
            
            return AgentResponse(
                success=True,
                message=f"Executed {command.command_type}.{command.action}",
                data={"command": command.dict()}
            )
        except Exception as e:
            return AgentResponse(
                success=False,
                message=f"Error executing command: {str(e)}",
                data={"error_type": "execution_error"}
            )