import digitalocean
from dotenv import load_dotenv
import os
import time

class DigitalOceanManager:
    def __init__(self):
        load_dotenv()
        self.token = os.getenv("DIGITALOCEAN_TOKEN")
        self.manager = digitalocean.Manager(token=self.token)
    
    def list_droplets(self):
        return self.manager.get_all_droplets()
    
    def get_droplet(self, droplet_id):
        return self.manager.get_droplet(droplet_id)
    
    def create_droplet(self, name, region, size, image):
        droplet = digitalocean.Droplet(
            token=self.token,
            name=name,
            region=region,
            size_slug=size,
            image=image
        )
        droplet.create()
        return droplet

    def delete_droplet(self, droplet_id):
        droplet = self.get_droplet(droplet_id)
        return droplet.destroy()
    
    def reboot_droplet(self, droplet_id):
        droplet = self.get_droplet(droplet_id)
        return droplet.reboot()
    
    def power_off_droplet(self, droplet_id):
        droplet = self.get_droplet(droplet_id)
        return droplet.power_off()
    
    def power_on_droplet(self, droplet_id):
        droplet = self.get_droplet(droplet_id)
        return droplet.power_on()
    
    def get_droplet_status(self, droplet_id):
        droplet = self.get_droplet(droplet_id)
        actions = droplet.get_actions()
        recent_action = actions[0] if actions else None
        return {
            "status": droplet.status,
            "last_action": {
                "type": recent_action.type if recent_action else None,
                "status": recent_action.status if recent_action else None,
                "started_at": recent_action.started_at if recent_action else None
            }
        }