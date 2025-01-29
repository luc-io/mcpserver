import os
from fastapi import FastAPI, HTTPException, Depends, Request
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from digital_ocean import DigitalOceanManager
from auth import get_current_user
from monitor import SystemMonitor
from agent import AgentManager, AgentCommand, AgentResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="MCP Server")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Initialize managers
do_manager = DigitalOceanManager()
sys_monitor = SystemMonitor()
agent_manager = AgentManager()

class DropletCreate(BaseModel):
    name: str
    region: str = "nyc1"
    size: str = "s-1vcpu-512mb-10gb"
    image: str = "ubuntu-20-04-x64"

@app.get("/")
@limiter.limit("60/minute")
async def root(request: Request):
    """Public endpoint with version and available endpoints"""
    return {
        "message": "MCP Server is running",
        "version": "1.2.0",
        "endpoints": [
            "/droplets - List all droplets",
            "/droplets/{id} - Get droplet details",
            "/droplets/{id}/status - Get droplet status",
            "/droplets/{id}/power/on - Power on droplet",
            "/droplets/{id}/power/off - Power off droplet",
            "/droplets/{id}/reboot - Reboot droplet",
            "/system/status - Get system status",
            "/system/process/{pid} - Get process info",
            "/agent/execute - Execute agent command"
        ]
    }

@app.post("/agent/execute")
@limiter.limit("30/minute")
async def execute_agent_command(
    request: Request,
    command: AgentCommand,
    current_user: str = Depends(get_current_user)
):
    """Execute a command through the agent interface"""
    response = await agent_manager.execute_command(command)
    
    if not response.success:
        raise HTTPException(status_code=400, detail=response.message)
    
    # If command is successful, execute it using the appropriate manager
    if command.command_type == "droplet":
        if command.action == "list":
            droplets = do_manager.list_droplets()
            response.data = {
                "droplets": [{
                    "id": d.id,
                    "name": d.name,
                    "status": d.status,
                    "ip_address": d.ip_address
                } for d in droplets]
            }
        elif command.action == "status":
            droplet_id = command.parameters.get("droplet_id")
            if droplet_id:
                status = do_manager.get_droplet_status(droplet_id)
                response.data = {"status": status}
        # Add more droplet actions as needed
    
    elif command.command_type == "system":
        if command.action == "status":
            response.data = sys_monitor.get_system_stats()
    
    # Log the command and response
    agent_manager.log_command(command, response)
    return response

# [Previous endpoints remain the same...]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=os.getenv("MCP_SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_SERVER_PORT", 8000)),
        reload=True
    )