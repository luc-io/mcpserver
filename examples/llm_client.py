import requests
import json
from typing import Dict, Any
import os
from datetime import datetime

class MCPAgentClient:
    def __init__(self, base_url: str, username: str, password: str, agent_id: str):
        self.base_url = base_url
        self.auth = (username, password)
        self.agent_id = agent_id
        self.session = requests.Session()
    
    def execute_command(self, command_type: str, action: str, parameters: Dict[str, Any] = None) -> Dict:
        """Execute a command through the MCP server"""
        url = f"{self.base_url}/agent/execute"
        
        command = {
            "command_type": command_type,
            "action": action,
            "parameters": parameters or {},
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat()
        }
        
        response = self.session.post(
            url,
            json=command,
            auth=self.auth
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error executing command: {response.text}")
    
    def get_system_status(self) -> Dict:
        """Get system status"""
        return self.execute_command("system", "status")
    
    def list_droplets(self) -> Dict:
        """List all droplets"""
        return self.execute_command("droplet", "list")
    
    def get_droplet_status(self, droplet_id: int) -> Dict:
        """Get status of a specific droplet"""
        return self.execute_command("droplet", "status", {"droplet_id": droplet_id})

# Example usage
if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Create client
    client = MCPAgentClient(
        base_url="http://157.245.248.36:8000",
        username=os.getenv("API_USERNAME"),
        password=os.getenv("API_PASSWORD"),
        agent_id="example_agent"
    )
    
    # Example commands
    try:
        # Get system status
        system_status = client.get_system_status()
        print("System Status:", json.dumps(system_status, indent=2))
        
        # List droplets
        droplets = client.list_droplets()
        print("\nDroplets:", json.dumps(droplets, indent=2))
        
        # Get specific droplet status
        if droplets["data"]["droplets"]:
            droplet_id = droplets["data"]["droplets"][0]["id"]
            status = client.get_droplet_status(droplet_id)
            print(f"\nDroplet {droplet_id} Status:", json.dumps(status, indent=2))
    
    except Exception as e:
        print(f"Error: {str(e)}")
