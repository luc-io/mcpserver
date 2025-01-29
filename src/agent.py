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
    def __init__(self, name: str, directory: str, pm2_name: str):
        self.name = name
        self.directory = directory
        self.pm2_name = pm2_name

class AgentManager:
    def __init__(self):
        # Define known projects and their configurations
        self.projects = {
            "selfi-bot": ProjectConfig(
                name="selfi-bot",
                directory="/var/www/selfi-bot",
                pm2_name="selfi-bot"
            ),
            "selfi-miniapp": ProjectConfig(
                name="selfi-miniapp",
                directory="/var/www/selfi-miniapp",
                pm2_name="selfi-miniapp"
            )
        }
        
        self.allowed_commands = {
            "droplet": ["list", "status", "create", "delete", "reboot", "power_on", "power_off"],
            "system": ["status", "process"],
            "project": ["deploy", "update", "rollback", "restart", "logs", "status"],
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
            "/var/www/mcpserver/src"
        ]
        self.safe_directories.extend([p.directory for p in self.projects.values()])
        
        # Define log file locations
        self.log_directories = [
            "/var/www/mcpserver/logs",
            "/var/log/nginx",
            "~/.pm2/logs"
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
            if action == "restart":
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
            
            # Handle shell commands as before
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
            
            # Validate command before execution
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

    def validate_command(self, command: AgentCommand) -> bool:
        """Previously defined validation logic remains the same"""
        # Your existing validation code here...
        return True

    def _log_execution(self, command: AgentCommand, result: dict):
        """Log command execution"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": command.agent_id,
            "command": command.dict(),
            "result": result
        }
        print(f"Agent Log: {json.dumps(log_entry, indent=2)}")
