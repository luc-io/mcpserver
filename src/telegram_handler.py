from typing import Optional, List, Dict
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import os
from datetime import datetime

class TelegramBot:
    def __init__(self, agent_manager, token: str, allowed_users: List[int]):
        self.agent = agent_manager
        self.token = token
        self.allowed_users = allowed_users
        self.app = None
        self.suggestions_cache = {}

    async def start(self):
        """Start the bot"""
        try:
            self.app = Application.builder().token(self.token).build()
            
            # Add handlers
            self.app.add_handler(CommandHandler("start", self.cmd_start))
            self.app.add_handler(CommandHandler("status", self.cmd_status))
            self.app.add_handler(CommandHandler("help", self.cmd_help))
            self.app.add_handler(CallbackQueryHandler(self.handle_callback))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # Start the bot without blocking
            await self.app.initialize()
            await self.app.start()
            
            # Start polling in a separate task
            asyncio.create_task(self.app.updater.start_polling())
            
        except Exception as e:
            print(f"Error starting Telegram bot: {str(e)}")
            raise

    async def stop(self):
        """Stop the bot"""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot"""
        return user_id in self.allowed_users

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not self.is_user_allowed(update.effective_user.id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        await update.message.reply_text(
            "👋 Hi! I'm your Project Management Agent. I can help you manage your projects.\n\n"
            "I can:\n"
            "• Check project status\n"
            "• Deploy updates\n"
            "• Monitor logs\n"
            "• Manage services\n\n"
            "Send me a message describing what you'd like to do!"
        )

    # [Rest of the class remains the same...]