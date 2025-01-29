import os
from fastapi import FastAPI, HTTPException
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from digital_ocean import DigitalOceanManager

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="MCP Server")

# Initialize DigitalOcean Manager
do_manager = DigitalOceanManager()

class DropletCreate(BaseModel):
    name: str
    region: str = "nyc1"
    size: str = "s-1vcpu-512mb-10gb"
    image: str = "ubuntu-20-04-x64"

@app.get("/")
async def root():
    return {
        "message": "MCP Server is running",
        "version": "1.1.0",
        "endpoints": [
            "/droplets - List all droplets",
            "/droplets/{id} - Get droplet details",
            "/droplets/{id}/status - Get droplet status",
            "/droplets/{id}/power/on - Power on droplet",
            "/droplets/{id}/power/off - Power off droplet",
            "/droplets/{id}/reboot - Reboot droplet"
        ]
    }

@app.get("/droplets")
async def list_droplets():
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
async def get_droplet(droplet_id: int):
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
async def create_droplet(droplet: DropletCreate):
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
async def delete_droplet(droplet_id: int):
    try:
        do_manager.delete_droplet(droplet_id)
        return {"message": f"Droplet {droplet_id} deletion initiated"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/droplets/{droplet_id}/reboot")
async def reboot_droplet(droplet_id: int):
    try:
        do_manager.reboot_droplet(droplet_id)
        return {"message": f"Droplet {droplet_id} reboot initiated"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/droplets/{droplet_id}/power/off")
async def power_off_droplet(droplet_id: int):
    try:
        do_manager.power_off_droplet(droplet_id)
        return {"message": f"Droplet {droplet_id} power off initiated"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/droplets/{droplet_id}/power/on")
async def power_on_droplet(droplet_id: int):
    try:
        do_manager.power_on_droplet(droplet_id)
        return {"message": f"Droplet {droplet_id} power on initiated"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/droplets/{droplet_id}/status")
async def get_droplet_status(droplet_id: int):
    try:
        return do_manager.get_droplet_status(droplet_id)
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