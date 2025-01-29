import os
from fastapi import FastAPI, HTTPException, Depends, Request
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from digital_ocean import DigitalOceanManager
from auth import get_current_user
from monitor import SystemMonitor
from agent import AgentManager, AgentCommand, AgentResponse

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="MCP Server")

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
async def execute_agent_command(
    command: AgentCommand,
    current_user: str = Depends(get_current_user)
):
    """Execute a command through the agent interface"""
    try:
        response = await agent_manager.execute_command(command)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.message)
        
        # Execute command based on type
        if command.command_type == "shell":
            return await agent_manager._execute_shell_command(command)
        
        elif command.command_type == "droplet":
            if command.action == "list":
                droplets = do_manager.list_droplets()
                return AgentResponse(
                    success=True,
                    message="Droplets listed successfully",
                    data={
                        "droplets": [{
                            "id": d.id,
                            "name": d.name,
                            "status": d.status,
                            "ip_address": d.ip_address
                        } for d in droplets]
                    }
                )
            elif command.action == "status":
                droplet_id = command.parameters.get("droplet_id")
                status = do_manager.get_droplet_status(droplet_id)
                return AgentResponse(
                    success=True,
                    message="Status retrieved successfully",
                    data={"status": status}
                )
        
        elif command.command_type == "system":
            if command.action == "status":
                return AgentResponse(
                    success=True,
                    message="System status retrieved successfully",
                    data=sys_monitor.get_system_stats()
                )
        
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/droplets")
async def list_droplets(
    current_user: str = Depends(get_current_user)
):
    droplets = do_manager.list_droplets()
    return {
        "droplets": [{
            "id": d.id,
            "name": d.name,
            "status": d.status,
            "size": d.size_slug,
            "region": d.region['slug'],
            "ip_address": d.ip_address,
            "memory": f"{d.memory}MB",
            "disk": f"{d.disk}GB",
            "created_at": d.created_at
        } for d in droplets]
    }

@app.get("/droplets/{droplet_id}")
async def get_droplet(
    droplet_id: int,
    current_user: str = Depends(get_current_user)
):
    try:
        droplet = do_manager.get_droplet(droplet_id)
        return {
            "id": droplet.id,
            "name": droplet.name,
            "status": droplet.status,
            "size": droplet.size_slug,
            "memory": f"{droplet.memory}MB",
            "disk": f"{droplet.disk}GB",
            "vcpus": droplet.vcpus,
            "ip_address": droplet.ip_address,
            "region": {
                "slug": droplet.region['slug'],
                "name": droplet.region['name']
            },
            "image": {
                "id": droplet.image['id'],
                "name": droplet.image['name']
            },
            "created_at": droplet.created_at,
            "tags": droplet.tags
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=os.getenv("MCP_SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_SERVER_PORT", 8000)),
        reload=True
    )