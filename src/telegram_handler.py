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
        self.app = Application.builder().token(self.token).build()
        
        # Add handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Start the bot
        await self.app.initialize()
        await self.app.start()
        await self.app.run_polling()

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

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        if not self.is_user_allowed(update.effective_user.id):
            return

        help_text = (
            "🤖 Here's what I can help you with:\n\n"
            "📊 Project Status:\n"
            "- Check project status\n"
            "- View logs\n"
            "- Monitor resources\n\n"
            "🔄 Management:\n"
            "- Update projects\n"
            "- Restart services\n"
            "- Deploy changes\n\n"
            "Just tell me what you want to do in natural language!"
        )
        await update.message.reply_text(help_text)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if not self.is_user_allowed(update.effective_user.id):
            return

        # Get status of all projects
        status_msg = "📊 Current Status:\n\n"
        
        for project_name in ["selfi-bot", "selfi-miniapp"]:
            response = await self.agent.execute_command({
                "command_type": "project",
                "action": "status",
                "parameters": {"project": project_name},
                "agent_id": "telegram_bot"
            })
            
            if response.success:
                status_msg += f"*{project_name}*:\n"
                status_msg += f"Status: {'✅ Online' if 'online' in response.data['stdout'].lower() else '❌ Offline'}\n\n"
            else:
                status_msg += f"*{project_name}*: Unable to get status\n\n"

        await update.message.reply_text(status_msg, parse_mode='Markdown')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language messages"""
        if not self.is_user_allowed(update.effective_user.id):
            return

        message = update.message.text.lower()
        
        # Parse intent and generate suggestions
        suggestions = self.parse_intent(message)
        
        if not suggestions:
            await update.message.reply_text(
                "I'm not sure what you want to do. Can you be more specific?\n"
                "You can ask me to:\n"
                "- Check project status\n"
                "- View logs\n"
                "- Restart services\n"
                "- Update projects"
            )
            return

        # Store suggestions for callback handling
        self.suggestions_cache[update.effective_user.id] = suggestions

        # Create inline keyboard with suggestions
        keyboard = []
        for i, suggestion in enumerate(suggestions):
            keyboard.append([InlineKeyboardButton(
                suggestion['description'],
                callback_data=f"suggestion_{i}"
            )])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "I suggest these actions:",
            reply_markup=reply_markup
        )

    def parse_intent(self, message: str) -> List[Dict]:
        """Parse user message and return suggested actions"""
        suggestions = []
        
        # Status checks
        if any(word in message for word in ['status', 'health', 'running']):
            suggestions.append({
                'description': '📊 Check all project statuses',
                'command': {
                    'command_type': 'project',
                    'action': 'status',
                    'parameters': {'project': 'all'},
                }
            })

        # Log viewing
        if any(word in message for word in ['log', 'logs', 'error']):
            for project in ['selfi-bot', 'selfi-miniapp']:
                if project in message or 'all' in message:
                    suggestions.append({
                        'description': f'📋 View {project} logs',
                        'command': {
                            'command_type': 'project',
                            'action': 'logs',
                            'parameters': {
                                'project': project,
                                'lines': '20'
                            },
                        }
                    })

        # Updates and deployment
        if any(word in message for word in ['update', 'deploy', 'latest']):
            for project in ['selfi-bot', 'selfi-miniapp']:
                if project in message or 'all' in message:
                    suggestions.append({
                        'description': f'🔄 Update {project}',
                        'command': {
                            'command_type': 'project',
                            'action': 'update',
                            'parameters': {'project': project},
                        }
                    })

        # Restart services
        if any(word in message for word in ['restart', 'reboot', 'reset']):
            for project in ['selfi-bot', 'selfi-miniapp']:
                if project in message or 'all' in message:
                    suggestions.append({
                        'description': f'🔄 Restart {project}',
                        'command': {
                            'command_type': 'project',
                            'action': 'restart',
                            'parameters': {'project': project},
                        }
                    })

        return suggestions

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        if not self.is_user_allowed(update.effective_user.id):
            return

        query = update.callback_query
        await query.answer()

        # Get stored suggestions
        suggestions = self.suggestions_cache.get(update.effective_user.id, [])
        if not suggestions:
            await query.edit_message_text("Sorry, I lost track of the suggestions. Please try again.")
            return

        # Get selected suggestion
        try:
            suggestion_index = int(query.data.split('_')[1])
            suggestion = suggestions[suggestion_index]
        except (IndexError, ValueError):
            await query.edit_message_text("Invalid selection. Please try again.")
            return

        # Execute the command
        await query.edit_message_text(f"Executing: {suggestion['description']}")
        response = await self.agent.execute_command(suggestion['command'])

        # Format and send response
        if response.success:
            result_msg = f"✅ {suggestion['description']} completed!\n\n"
            if response.data and 'stdout' in response.data:
                # Format the output for Telegram
                output = response.data['stdout'].strip()
                if len(output) > 1000:
                    output = output[:997] + "..."
                if output:
                    result_msg += f"```\n{output}\n```"
        else:
            result_msg = f"❌ {suggestion['description']} failed:\n{response.message}"

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=result_msg,
            parse_mode='Markdown'
        )

        # Clean up suggestions cache
        self.suggestions_cache.pop(update.effective_user.id, None)