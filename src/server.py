import os
import logging
import sys
from fastapi import FastAPI, HTTPException, Depends, Request
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from src.digital_ocean import DigitalOceanManager
from src.auth import get_current_user
from src.monitor import SystemMonitor
from src.agent import AgentManager
from src.telegram_handler import TelegramBot
import asyncio
import uvicorn
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

try:
    # Load environment variables
    logger.info("Loading environment variables...")
    load_dotenv()
    
    # Initialize managers
    logger.info("Initializing managers...")
    do_manager = DigitalOceanManager()
    sys_monitor = SystemMonitor()
    agent_manager = AgentManager()
    
    # Initialize Telegram bot with allowed user IDs
    logger.info("Setting up Telegram bot...")
    telegram_bot = TelegramBot(
        agent_manager,
        token=os.getenv("TELEGRAM_BOT_TOKEN"),
        allowed_users=[int(id.strip()) for id in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if id.strip()]
    )
except Exception as e:
    logger.error(f"Error during initialization: {str(e)}", exc_info=True)
    raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Startup
        logger.info("Starting Telegram bot...")
        await telegram_bot.start()
        logger.info("Telegram bot started successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to start services: {str(e)}", exc_info=True)
        raise
    finally:
        # Shutdown
        logger.info("Shutting down services...")
        try:
            await telegram_bot.stop()
            logger.info("Services shut down successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}", exc_info=True)

# Initialize FastAPI app
app = FastAPI(title="MCP Server", lifespan=lifespan)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Endpoint to handle agent commands
@app.post("/agent/execute")
async def execute_command(command: dict, current_user = Depends(get_current_user)):
    try:
        result = await agent_manager.execute_command(command)
        return result.dict()
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

def run_server():
    uvicorn.run(
        "src.server:app",
        host=os.getenv("MCP_SERVER_HOST", "157.245.248.36"),
        port=int(os.getenv("MCP_SERVER_PORT", "8000")),
        log_level="debug",
        reload=True
    )

if __name__ == "__main__":
    run_server()