from typing import Optional, List, Dict
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import os
from datetime import datetime
import logging
from .llm_handler import LLMHandler
from .tool_manager import ToolManager

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, agent_manager, token: str, allowed_users: List[int]):
        self.agent = agent_manager
        self.token = token
        self.allowed_users = allowed_users
        self.app = None

        # Initialize LLM and tools
        self.llm = LLMHandler()
        self.tool_manager = ToolManager(agent_manager)
        self.tool_manager.register_with_llm(self.llm)

    async def start(self):
        """Start the bot"""
        try:
            logger.info("Building Telegram application...")
            self.app = Application.builder().token(self.token).build()
            
            # Add handlers
            logger.info("Adding command handlers...")
            self.app.add_handler(CommandHandler("start", self.cmd_start))
            self.app.add_handler(CommandHandler("help", self.cmd_help))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # Initialize the bot
            logger.info("Initializing Telegram bot...")
            await self.app.initialize()
            await self.app.start()
            
            # Start polling in a separate task
            logger.info("Starting polling...")
            asyncio.create_task(self.app.updater.start_polling())
            logger.info("Bot startup complete")
            
        except Exception as e:
            logger.error(f"Error starting Telegram bot: {str(e)}")
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
            "👋 Hi! I'm your AI-powered Project Management Assistant.\n\n"
            "I can help you manage your projects using natural language. Just tell me what you want to do!\n\n"
            "I can:\n"
            "• Check project status\n"
            "• Deploy updates\n"
            "• Monitor logs\n"
            "• Manage services\n"
            "• Answer questions about your projects\n\n"
            "You can also have a natural conversation with me about your projects!"
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        if not self.is_user_allowed(update.effective_user.id):
            return

        help_text = (
            "🤖 Here's what I can help you with:\n\n"
            "📊 Project Management:\n"
            "- Check project status\n"
            "- Update projects\n"
            "- View logs\n"
            "- Restart services\n\n"
            "💬 Natural Interaction:\n"
            "- Ask questions about your projects\n"
            "- Get explanations about errors\n"
            "- Discuss project improvements\n\n"
            "Just chat with me naturally about what you need!"
        )
        await update.message.reply_text(help_text)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language messages using LLM"""
        if not self.is_user_allowed(update.effective_user.id):
            return

        user_id = update.effective_user.id
        message = update.message.text

        try:
            # Send typing action while processing
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
            
            # Process message with LLM
            response = await self.llm.process_message(message)
            
            # Send response
            if len(response) > 4000:
                # Split long messages
                for i in range(0, len(response), 4000):
                    chunk = response[i:i + 4000]
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(response)
                
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            await update.message.reply_text(error_msg)