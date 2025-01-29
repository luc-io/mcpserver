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
        
        # Define commands with their full paths and allowed arguments
        self.allowed_shell_commands = {
            "ls": {
                "path": "/bin/ls",
                "args": ["-l", "-a", "-la", "-al", "--color=auto"]
            },
            "cd": {
                "path": "cd",  # built-in shell command
                "args": []
            },
            "python3": {
                "path": "/usr/bin/python3",
                "args": ["-m", "-V", "-c"]
            },
            "pip": {
                "path": "/var/www/mcpserver/venv/bin/pip",
                "args": ["install", "list", "freeze"]
            },
            "git": {
                "path": "/usr/bin/git",
                "args": ["pull", "status", "log"]
            }
        }
        
        self.safe_directories = [
            "/var/www/mcpserver",
            "/var/www/mcpserver/examples",
            "/var/www/mcpserver/src"
        ]

    def validate_command(self, command: AgentCommand) -> bool:
        if command.command_type not in self.allowed_commands:
            raise ValueError(f"Invalid command type: {command.command_type}")
        
        if command.action not in self.allowed_commands[command.command_type]:
            raise ValueError(f"Invalid action for {command.command_type}: {command.action}")
        
        if command.command_type == "shell":
            shell_command = command.parameters.get("command", "")
            if not shell_command:
                raise ValueError("Empty shell command")
            
            try:
                cmd_parts = shlex.split(shell_command)
            except Exception as e:
                raise ValueError(f"Invalid shell command format: {str(e)}")
            
            if not cmd_parts:
                raise ValueError("Empty shell command")
            
            base_cmd = cmd_parts[0]
            if base_cmd not in self.allowed_shell_commands:
                raise ValueError(f"Shell command not allowed: {base_cmd}")
            
            # Replace command with full path
            if base_cmd != "cd":  # cd is handled specially
                command.parameters["command"] = shell_command.replace(
                    base_cmd,
                    self.allowed_shell_commands[base_cmd]["path"],
                    1
                )
            
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
        allowed_args = self.allowed_shell_commands["ls"]["args"]
        for arg in cmd_parts[1:]:
            if arg.startswith("-"):
                if arg not in allowed_args:
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
            
            # Get updated command after validation
            shell_command = command.parameters["command"]
            
            # Set up environment variables
            env = os.environ.copy()
            env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            
            # Execute the command
            process = subprocess.run(
                shell_command,
                shell=True,
                cwd="/var/www/mcpserver",
                capture_output=True,
                text=True,
                timeout=30,
                env=env
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