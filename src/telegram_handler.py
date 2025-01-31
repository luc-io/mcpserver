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
        logger.info("Initializing LLM and tools...")
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
            logger.error(f"Error starting Telegram bot: {str(e)}", exc_info=True)
            raise

    async def stop(self):
        """Stop the bot"""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot"""
        logger.debug(f"Checking if user {user_id} is allowed. Allowed users: {self.allowed_users}")
        return user_id in self.allowed_users

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        logger.info(f"Received /start command from user {update.effective_user.id}")
        
        if not self.is_user_allowed(update.effective_user.id):
            logger.warning(f"Unauthorized user {update.effective_user.id} tried to use /start")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, you're not authorized to use this bot."
            )
            return

        logger.info(f"Sending welcome message to user {update.effective_user.id}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
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
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        if not self.is_user_allowed(update.effective_user.id):
            return

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
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
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language messages using LLM"""
        try:
            if not self.is_user_allowed(update.effective_user.id):
                logger.warning(f"Unauthorized user {update.effective_user.id} tried to send message")
                return

            user_id = update.effective_user.id
            message = update.message.text
            logger.info(f"Processing message from user {user_id}: {message}")

            # Send typing action while processing
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
            
            # Process message with LLM
            response = await self.llm.process_message(message)
            logger.debug(f"LLM response: {response}")
            
            # Send response in chunks if needed
            if len(response) > 4000:
                for i in range(0, len(response), 4000):
                    chunk = response[i:i + 4000]
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=chunk
                    )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=response
                )
                
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_msg
            )