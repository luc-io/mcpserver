from typing import List, Optional, Dict
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

class ProjectConfig:
    def __init__(self, name: str, directory: str, pm2_name: str, config_file: str = None):
        self.name = name
        self.directory = directory
        self.pm2_name = pm2_name
        self.config_file = config_file

class AgentManager:
    def __init__(self):
        # Define known projects and their configurations
        self.projects = {
            "selfi-bot": ProjectConfig(
                name="selfi-bot",
                directory="/var/www/selfi-dev/bot",
                pm2_name="selfi-bot",
                config_file="config.js"
            ),
            "selfi-miniapp": ProjectConfig(
                name="selfi-miniapp",
                directory="/var/www/selfi-dev/miniapp",
                pm2_name="selfi-miniapp"
            )
        }
        
        self.allowed_commands = {
            "project": ["deploy", "update", "rollback", "restart", "logs", "status", "config"],
            "shell": ["execute"]
        }
        
        # Define commands with their full paths and allowed arguments
        self.allowed_shell_commands = {
            "ls": {
                "path": "/bin/ls",
                "args": ["-l", "-a", "-la", "-al", "--color=auto"]
            },
            "cd": {
                "path": "cd",
                "args": []
            },
            "cat": {
                "path": "/bin/cat",
                "args": []
            },
            "grep": {
                "path": "/bin/grep",
                "args": ["-i", "-n", "--color=auto"]
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
                "args": ["list", "show", "restart", "reload", "stop", "delete", "logs", "status", "save"]
            }
        }
        
        # Add project directories to safe directories
        self.safe_directories = [
            "/var/www/mcpserver",
            "/var/www/mcpserver/examples",
            "/var/www/mcpserver/src",
            "/var/www/selfi-dev/bot",
            "/var/www/selfi-dev/miniapp"
        ]
        
        # Define log file locations
        self.log_directories = [
            "/var/www/mcpserver/logs",
            "/var/log/nginx",
            "~/.pm2/logs",
            "/var/www/selfi-dev/bot/logs",
            "/var/www/selfi-dev/miniapp/logs"
        ]

    async def _manage_project(self, project_name: str, action: str, parameters: Dict) -> AgentResponse:
        """Handle project-specific commands"""
        if project_name not in self.projects:
            return AgentResponse(
                success=False,
                message=f"Unknown project: {project_name}"
            )
        
        project = self.projects[project_name]
        
        try:
            if action == "config":
                # Read project configuration
                if not project.config_file:
                    return AgentResponse(
                        success=False,
                        message=f"No config file defined for {project_name}"
                    )
                
                config_path = os.path.join(project.directory, project.config_file)
                try:
                    with open(config_path, 'r') as f:
                        config_content = f.read()
                    return AgentResponse(
                        success=True,
                        message=f"Configuration for {project_name}",
                        data={"config": config_content}
                    )
                except Exception as e:
                    return AgentResponse(
                        success=False,
                        message=f"Error reading config: {str(e)}"
                    )
                    
            elif action == "restart":
                cmd = f"{self.allowed_shell_commands['pm2']['path']} restart {project.pm2_name}"
            elif action == "status":
                cmd = f"{self.allowed_shell_commands['pm2']['path']} show {project.pm2_name}"
            elif action == "logs":
                lines = parameters.get("lines", "20")
                cmd = f"{self.allowed_shell_commands['pm2']['path']} logs {project.pm2_name} --nostream --lines {lines}"
            elif action == "update":
                # Git pull and restart
                cmds = [
                    f"cd {project.directory}",
                    f"{self.allowed_shell_commands['git']['path']} pull",
                    f"{self.allowed_shell_commands['npm']['path']} install",
                    f"{self.allowed_shell_commands['pm2']['path']} restart {project.pm2_name}"
                ]
                cmd = " && ".join(cmds)
            else:
                return AgentResponse(
                    success=False,
                    message=f"Unknown action for project: {action}"
                )
            
            # Execute command
            process = subprocess.run(
                cmd,
                shell=True,
                cwd=project.directory,
                capture_output=True,
                text=True,
                timeout=300,
                env=self._get_env()
            )
            
            response_data = {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "return_code": process.returncode,
                "command": cmd,
                "project": project_name
            }
            
            return AgentResponse(
                success=process.returncode == 0,
                message=f"Project {action} {'successful' if process.returncode == 0 else 'failed'}",
                data=response_data
            )
            
        except Exception as e:
            return AgentResponse(
                success=False,
                message=f"Error managing project: {str(e)}"
            )

    def _get_env(self) -> Dict[str, str]:
        """Get environment variables for command execution"""
        env = os.environ.copy()
        env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        env["NODE_ENV"] = "production"
        return env

    def validate_command(self, command: AgentCommand) -> bool:
        """Validate command execution"""
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
            # No argument validation needed for now
            pass
        else:
            for arg in args:
                if arg.startswith("-") and arg not in allowed_args:
                    raise ValueError(f"Invalid argument for {cmd}: {arg}")

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

    async def execute_command(self, command: AgentCommand) -> AgentResponse:
        """Execute a command"""
        try:
            # Handle project-specific commands
            if command.command_type == "project":
                project_name = command.parameters.get("project")
                if not project_name:
                    return AgentResponse(
                        success=False,
                        message="Project name required for project commands"
                    )
                return await self._manage_project(project_name, command.action, command.parameters)
            
            # Handle shell commands
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

    async def _execute_shell_command(self, command: AgentCommand) -> AgentResponse:
        """Execute a shell command"""
        try:
            shell_command = command.parameters.get("command", "")
            if not shell_command:
                return AgentResponse(
                    success=False,
                    message="No shell command provided"
                )
            
            # Validate command
            try:
                self.validate_command(command)
            except ValueError as e:
                return AgentResponse(
                    success=False,
                    message=str(e)
                )
            
            # Execute command
            process = subprocess.run(
                shell_command,
                shell=True,
                cwd="/var/www/mcpserver",
                capture_output=True,
                text=True,
                timeout=300,
                env=self._get_env()
            )
            
            # Prepare response
            response_data = {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "return_code": process.returncode,
                "command": shell_command
            }
            
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