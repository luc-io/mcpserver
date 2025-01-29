import os
from fastapi import FastAPI
from mcp_python_sdk import MCPServer
from dotenv import load_dotenv
from digital_ocean import DigitalOceanManager

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Initialize MCP Server
mcp_server = MCPServer()

# Initialize DigitalOcean Manager
do_manager = DigitalOceanManager()

@app.get("/")
async def root():
    return {"message": "MCP Server is running"}

@app.get("/droplets")
async def list_droplets():
    droplets = do_manager.list_droplets()
    return {"droplets": [{"id": d.id, "name": d.name, "status": d.status} for d in droplets]}

@app.get("/droplets/{droplet_id}")
async def get_droplet(droplet_id: int):
    droplet = do_manager.get_droplet(droplet_id)
    return {
        "id": droplet.id,
        "name": droplet.name,
        "status": droplet.status,
        "ip_address": droplet.ip_address,
        "region": droplet.region['slug'],
        "size": droplet.size_slug
    }

@app.post("/droplets")
async def create_droplet(name: str, region: str = "nyc1", size: str = "s-1vcpu-1gb", image: str = "ubuntu-20-04-x64"):
    droplet = do_manager.create_droplet(name, region, size, image)
    return {
        "id": droplet.id,
        "name": droplet.name,
        "status": "creating"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=os.getenv("MCP_SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_SERVER_PORT", 8000)),
        reload=True
    )