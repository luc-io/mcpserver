import os
import logging
import sys
from fastapi import FastAPI, HTTPException, Depends, Request
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from digital_ocean import DigitalOceanManager
from auth import get_current_user
from monitor import SystemMonitor
from agent import AgentManager
from telegram_handler import TelegramBot
import asyncio
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Set telegram logging to DEBUG
logging.getLogger('telegram').setLevel(logging.DEBUG)
logging.getLogger('httpx').setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()

# Initialize managers
do_manager = DigitalOceanManager()
sys_monitor = SystemMonitor()
agent_manager = AgentManager()

# Initialize Telegram bot with allowed user IDs
telegram_bot = TelegramBot(
    agent_manager,
    token=os.getenv("TELEGRAM_BOT_TOKEN"),
    allowed_users=[int(id.strip()) for id in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if id.strip()]
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        logging.info("Starting Telegram bot...")
        asyncio.create_task(telegram_bot.start())
        logging.info("Telegram bot started successfully")
    except Exception as e:
        logging.error(f"Failed to start Telegram bot: {str(e)}", exc_info=True)
    
    yield
    
    # Shutdown
    logging.info("Shutting down...")

# Initialize FastAPI app with lifespan
app = FastAPI(title="MCP Server", lifespan=lifespan)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Endpoint to handle agent commands
@app.post("/agent/execute")
async def execute_command(command: dict, current_user = Depends(get_current_user)):
    result = await agent_manager.execute_command(command)
    return result.dict()