import os
from fastapi import FastAPI, HTTPException, Depends, Request
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from digital_ocean import DigitalOceanManager
from auth import get_current_user
from monitor import SystemMonitor
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
            "/system/process/{pid} - Get process info"
        ]
    }

@app.get("/droplets")
@limiter.limit("30/minute")
async def list_droplets(
    request: Request,
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
@limiter.limit("30/minute")
async def get_droplet(
    request: Request,
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

@app.post("/droplets")
@limiter.limit("10/minute")
async def create_droplet(
    request: Request,
    droplet: DropletCreate,
    current_user: str = Depends(get_current_user)
):
    new_droplet = do_manager.create_droplet(
        name=droplet.name,
        region=droplet.region,
        size=droplet.size,
        image=droplet.image
    )
    return {
        "id": new_droplet.id,
        "name": new_droplet.name,
        "status": "creating",
        "size": droplet.size
    }

@app.delete("/droplets/{droplet_id}")
@limiter.limit("10/minute")
async def delete_droplet(
    request: Request,
    droplet_id: int,
    current_user: str = Depends(get_current_user)
):
    try:
        do_manager.delete_droplet(droplet_id)
        return {"message": f"Droplet {droplet_id} deletion initiated"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/droplets/{droplet_id}/reboot")
@limiter.limit("10/minute")
async def reboot_droplet(
    request: Request,
    droplet_id: int,
    current_user: str = Depends(get_current_user)
):
    try:
        do_manager.reboot_droplet(droplet_id)
        return {"message": f"Droplet {droplet_id} reboot initiated"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/droplets/{droplet_id}/power/off")
@limiter.limit("10/minute")
async def power_off_droplet(
    request: Request,
    droplet_id: int,
    current_user: str = Depends(get_current_user)
):
    try:
        do_manager.power_off_droplet(droplet_id)
        return {"message": f"Droplet {droplet_id} power off initiated"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/droplets/{droplet_id}/power/on")
@limiter.limit("10/minute")
async def power_on_droplet(
    request: Request,
    droplet_id: int,
    current_user: str = Depends(get_current_user)
):
    try:
        do_manager.power_on_droplet(droplet_id)
        return {"message": f"Droplet {droplet_id} power on initiated"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/droplets/{droplet_id}/status")
@limiter.limit("30/minute")
async def get_droplet_status(
    request: Request,
    droplet_id: int,
    current_user: str = Depends(get_current_user)
):
    try:
        return do_manager.get_droplet_status(droplet_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/system/status")
@limiter.limit("30/minute")
async def get_system_status(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    return sys_monitor.get_system_stats()

@app.get("/system/process/{pid}")
@limiter.limit("30/minute")
async def get_process_info(
    request: Request,
    pid: int,
    current_user: str = Depends(get_current_user)
):
    process_info = sys_monitor.get_process_info(pid)
    if process_info is None:
        raise HTTPException(status_code=404, detail="Process not found")
    return process_info

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=os.getenv("MCP_SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_SERVER_PORT", 8000)),
        reload=True
    )