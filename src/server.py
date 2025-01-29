import os
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

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="MCP Server")

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

# Start Telegram bot
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(telegram_bot.start())

# [Rest of your server.py code remains the same...]