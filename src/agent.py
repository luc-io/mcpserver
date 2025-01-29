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
            "git": {
                "path": "/usr/bin/git",
                "args": ["pull", "status", "log", "branch", "checkout", "fetch"]
            },
            "npm": {
                "path": "/usr/bin/npm",
                "args": ["install", "build", "run", "start", "test", "ci"]
            },
            "pm2": {
                "path": "/usr/local/bin/pm2",
                "args": ["delete", "restart", "logs", "list", "status", "stop", "start"]
            },
            "cat": {
                "path": "/bin/cat",
                "args": []
            },
            "tail": {
                "path": "/usr/bin/tail",
                "args": ["-f", "-n"]
            }
        }
        
        # Define approved project directories
        self.safe_directories = [
            "/var/www/mcpserver",
            "/var/www/mcpserver/examples",
            "/var/www/mcpserver/src",
            # Add your project directories here
        ]
        
        # Define log file locations
        self.log_directories = [
            "/var/www/mcpserver/logs",
            "/var/log/nginx",
            "~/.pm2/logs"
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
            
            # Replace command with full path except for cd
            if base_cmd != "cd":
                command.parameters["command"] = shell_command.replace(
                    base_cmd,
                    self.allowed_shell_commands[base_cmd]["path"],
                    1
                )
            
            # Validate arguments
            self._validate_command_args(base_cmd, cmd_parts[1:])
            
            # Validate working directory for all commands
            self._validate_directory(cmd_parts)
            
            # Special validation for log access
            if base_cmd in ["cat", "tail"]:
                self._validate_log_access(cmd_parts)
        
        return True

    def _validate_command_args(self, cmd: str, args: List[str]):
        """Validate command arguments"""
        allowed_args = self.allowed_shell_commands[cmd]["args"]
        
        # Special handling for specific commands
        if cmd == "pm2":
            action = args[0] if args else None
            if action not in allowed_args:
                raise ValueError(f"Invalid pm2 action: {action}")
        elif cmd == "npm":
            action = args[0] if args else None
            if action not in allowed_args:
                raise ValueError(f"Invalid npm action: {action}")
        elif cmd in ["cat", "tail"]:
            # Will be validated in _validate_log_access
            pass
        else:
            for arg in args:
                if arg.startswith("-") and arg not in allowed_args:
                    raise ValueError(f"Invalid argument for {cmd}: {arg}")

    def _validate_log_access(self, cmd_parts: List[str]):
        """Validate access to log files"""
        if len(cmd_parts) < 2:
            raise ValueError("Log file path required")
        
        log_path = cmd_parts[-1]
        abs_path = os.path.abspath(os.path.expanduser(log_path))
        
        if not any(abs_path.startswith(os.path.abspath(os.path.expanduser(log_dir))) 
                  for log_dir in self.log_directories):
            raise ValueError(f"Access to log file not allowed: {log_path}")

    def _validate_directory(self, cmd_parts: List[str]):
        """Validate directory access"""
        for part in cmd_parts:
            if os.path.sep in part:
                abs_path = os.path.abspath(os.path.expanduser(part))
                if not any(abs_path.startswith(os.path.abspath(safe_dir)) 
                          for safe_dir in self.safe_directories):
                    # Check if it's a log file access
                    if not any(abs_path.startswith(os.path.abspath(os.path.expanduser(log_dir))) 
                              for log_dir in self.log_directories):
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
            env["NODE_ENV"] = "production"  # for npm commands
            
            # Execute the command
            process = subprocess.run(
                shell_command,
                shell=True,
                cwd="/var/www/mcpserver",
                capture_output=True,
                text=True,
                timeout=300,  # Extended timeout for npm install/build
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
                message="Command timed out after 300 seconds",
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