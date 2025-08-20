"""
Enhanced analyze command with comprehensive error logging and diagnostics.

This module provides an enhanced version of the analyze command that includes:
- Comprehensive error logging and diagnostics
- Performance metrics tracking
- External service monitoring
- User-friendly error messages
- Configuration validation

Requirements addressed: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from telegram import Update
from telegram.ext import ContextTypes

from modules.command_diagnostics import (
    enhance_command_with_diagnostics,
    track_database_query,
    track_api_call,
    log_command_milestone,
    log_command_performance_metric,
    validate_command_configuration,
    check_command_dependencies
)
from modules.enhanced_error_diagnostics import enhanced_diagnostics
from modules.structured_logging import StructuredLogger, LogLevel
from modules.error_handler import ErrorHandler, StandardError, ErrorCategory, ErrorSeverity
from modules.const import KYIV_TZ
from modules.logger import general_logger, error_logger


class EnhancedAnalyzeCommand:
    """
    Enhanced analyze command with comprehensive diagnostics and error handling.
    
    This class wraps the existing analyze command functionality with enhanced
    logging, metrics tracking, and diagnostic capabilities.
    """
    
    def __init__(self) -> None:
        self.logger = StructuredLogger("enhanced_analyze")
    
    @enhance_command_with_diagnostics("analyze")
    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Enhanced analyze command with comprehensive diagnostics.
        
        This method provides the same functionality as the original analyze command
        but with enhanced error logging, performance tracking, and diagnostics.
        """
        if not update.effective_chat or not update.effective_user:
            return
        
        # Extract user and chat information
        chat_id = int(update.effective_chat.id)
        user_id = int(update.effective_user.id)
        username = update.effective_user.username or f"ID:{user_id}"
        
        # Validate configuration before proceeding
        config_validation = await validate_command_configuration("analyze")
        if not config_validation["valid"]:
            error_message = (
                "❌ Конфігурація команди аналізу містить помилки.\n"
                "Зверніться до адміністратора для вирішення проблем."
            )
            
            self.logger.log_event(
                LogLevel.ERROR,
                "analyze_config_invalid",
                "Analyze command configuration validation failed",
                user_id=user_id,
                chat_id=chat_id,
                issues=config_validation["issues"]
            )
            
            if update.message:
                await update.message.reply_text(error_message)
            return
        
        # Check command dependencies
        dependency_check = await check_command_dependencies("analyze")
        if not dependency_check["healthy"]:
            error_message = (
                "❌ Деякі сервіси, необхідні для аналізу, недоступні.\n"
                "Спробуйте пізніше або зверніться до адміністратора."
            )
            
            self.logger.log_event(
                LogLevel.ERROR,
                "analyze_dependencies_unhealthy",
                "Analyze command dependencies are unhealthy",
                user_id=user_id,
                chat_id=chat_id,
                dependencies=dependency_check["dependencies"]
            )
            
            if update.message:
                await update.message.reply_text(error_message)
            return
        
        log_command_milestone("analyze", "validation_completed", 
                            user_id=user_id, chat_id=chat_id)
        
        try:
            # Parse command arguments
            args = context.args or []
            command_type, messages, date_str, time_period_key = await self._parse_command_arguments(
                args, chat_id, username
            )
            
            if messages is None:
                # Error occurred during parsing, error message already sent
                return
            
            log_command_milestone("analyze", "arguments_parsed", 
                                command_type=command_type, 
                                message_count=len(messages) if messages else 0,
                                user_id=user_id, chat_id=chat_id)
            
            # Check if we have messages to analyze
            if not messages:
                no_messages_response = (
                    f"📭 Не знайдено повідомлень для аналізу за період: {date_str}.\n"
                    "Спробуйте інший період або переконайтеся, що в чаті є повідомлення."
                )
                
                self.logger.log_event(
                    LogLevel.INFO,
                    "analyze_no_messages",
                    f"No messages found for analysis period: {date_str}",
                    user_id=user_id,
                    chat_id=chat_id,
                    period=date_str,
                    command_type=command_type
                )
                
                if update.message:
                    await update.message.reply_text(no_messages_response)
                return
            
            # Log performance metric for message count
            log_command_performance_metric(
                "analyze", "messages_to_analyze", len(messages), "count",
                user_id=user_id, chat_id=chat_id, period=date_str
            )
            
            # Check cache if enabled
            from modules.config.config_manager import config_manager
            cache_cfg = config_manager.get_analysis_cache_config()
            cache_enabled = cache_cfg["enabled"]
            
            cached_result = None
            if cache_enabled:
                log_command_milestone("analyze", "checking_cache", 
                                    user_id=user_id, chat_id=chat_id)
                
                async with track_database_query("cache_lookup", "analysis_cache"):
                    from modules.database import Database
                    cached_result = await Database.get_analysis_cache(
                        chat_id, time_period_key, cache_cfg["ttl"]
                    )
                
                if cached_result:
                    log_command_milestone("analyze", "cache_hit", 
                                        user_id=user_id, chat_id=chat_id)
                    
                    if update.message:
                        await update.message.reply_text(
                            f"📊 Аналіз повідомлень за {date_str} (з кешу):\n\n{cached_result}"
                        )
                    return
            
            log_command_milestone("analyze", "preparing_analysis", 
                                message_count=len(messages),
                                user_id=user_id, chat_id=chat_id)
            
            # Prepare messages for analysis
            messages_text = []
            for msg in messages:
                timestamp, username_msg, text = msg
                if text:  # Only process messages with text
                    messages_text.append(f"[{timestamp}] {username_msg}: {text}")
            
            if not messages_text:
                no_text_response = (
                    f"📭 Не знайдено текстових повідомлень для аналізу за період: {date_str}.\n"
                    "Можливо, всі повідомлення містять лише медіа-контент."
                )
                
                if update.message:
                    await update.message.reply_text(no_text_response)
                return
            
            # Prepare analysis text
            analysis_text = f"Аналіз повідомлень за {date_str}:\n\n" + "\n".join(messages_text)
            
            log_command_milestone("analyze", "calling_gpt_api", 
                                text_length=len(analysis_text),
                                user_id=user_id, chat_id=chat_id)
            
            # Call GPT for analysis with API call tracking
            async with track_api_call("openrouter", "/chat/completions", "POST") as api_tracker:
                try:
                    from modules.gpt import gpt_response
                    
                    analysis_result = await gpt_response(
                        update, 
                        context, 
                        response_type="analyze", 
                        message_text_override=analysis_text, 
                        return_text=True
                    )
                    
                    api_tracker.set_status_code(200)  # Assume success if no exception
                    
                except Exception as api_error:
                    api_tracker.set_status_code(500)  # API call failed
                    raise api_error
            
            if not analysis_result:
                api_error_response = (
                    "❌ Не вдалося отримати аналіз від сервісу ШІ.\n"
                    "Спробуйте пізніше або зверніться до адміністратора."
                )
                
                self.logger.log_event(
                    LogLevel.ERROR,
                    "analyze_gpt_no_result",
                    "GPT analysis returned empty result",
                    user_id=user_id,
                    chat_id=chat_id,
                    message_count=len(messages_text)
                )
                
                if update.message:
                    await update.message.reply_text(api_error_response)
                return
            
            log_command_milestone("analyze", "analysis_completed", 
                                result_length=len(analysis_result),
                                user_id=user_id, chat_id=chat_id)
            
            # Cache the result if caching is enabled
            if cache_enabled and time_period_key:
                log_command_milestone("analyze", "caching_result", 
                                    user_id=user_id, chat_id=chat_id)
                
                async with track_database_query("cache_store", "analysis_cache"):
                    from modules.database import Database
                    await Database.set_analysis_cache(chat_id, time_period_key, analysis_result)
            
            # Send the analysis result
            response_text = f"📊 Аналіз повідомлень за {date_str}:\n\n{analysis_result}"
            
            if update.message:
                await update.message.reply_text(response_text)
            
            # Log successful completion
            self.logger.log_event(
                LogLevel.INFO,
                "analyze_completed_successfully",
                f"Analysis completed successfully for {len(messages)} messages",
                user_id=user_id,
                chat_id=chat_id,
                period=date_str,
                message_count=len(messages),
                result_length=len(analysis_result),
                cached=cache_enabled and time_period_key is not None
            )
            
            # Log performance metrics
            log_command_performance_metric(
                "analyze", "result_length", len(analysis_result), "characters",
                user_id=user_id, chat_id=chat_id
            )
            
        except Exception as e:
            # Enhanced error handling with detailed context
            error_context = {
                "command": "analyze",
                "user_id": user_id,
                "chat_id": chat_id,
                "username": username,
                "args": context.args,
                "message_count": len(messages) if 'messages' in locals() and messages else 0
            }
            
            # Create a standardized error
            standard_error = StandardError(
                message=f"Analyze command failed: {str(e)}",
                severity=ErrorSeverity.HIGH,
                category=self._categorize_error(e),
                context=error_context,
                original_exception=e
            )
            
            # Handle the error with comprehensive logging
            await ErrorHandler.handle_error(
                error=standard_error,
                update=update,
                context=context,
                context_data=error_context,
                propagate=False
            )
            
            # Send user-friendly error message
            user_error_message = self._get_user_friendly_error_message(e)
            
            if update.message:
                try:
                    await update.message.reply_text(user_error_message)
                except Exception:
                    pass  # Don't fail if we can't send the error message
    
    async def _parse_command_arguments(
        self, 
        args: List[str], 
        chat_id: int, 
        username: str
    ) -> tuple[Optional[str], Optional[List[Tuple[datetime, str, str]]], str, Optional[str]]:
        """
        Parse command arguments with enhanced error handling.
        
        Returns:
            Tuple of (command_type, messages, date_str, time_period_key)
            Returns (None, None, "", None) if parsing fails
        """
        try:
            from modules.utils import DateParser
            from modules.chat_analysis import get_messages_for_chat_today, get_messages_for_chat_last_n_days, get_messages_for_chat_date_period, get_messages_for_chat_single_date
            
            if not args:
                # Default: analyze today's messages
                messages = await get_messages_for_chat_today(chat_id)
                return "today", messages, "сьогодні", "today"
            
            command_type = args[0].lower()
            
            if command_type == "last":
                return await self._parse_last_command(args, chat_id, username)
            elif command_type == "period":
                return await self._parse_period_command(args, chat_id, username)
            elif command_type == "date":
                return await self._parse_date_command(args, chat_id, username)
            else:
                error_message = (
                    "❌ Невідома команда. Доступні варіанти:\n\n"
                    "📊 **Основні команди:**\n"
                    "• /analyze - аналіз сьогоднішніх повідомлень\n"
                    "• /analyze last <число> messages - останні N повідомлень\n"
                    "• /analyze last <число> days - повідомлення за останні N днів\n"
                    "• /analyze date <дата> - повідомлення за конкретну дату\n"
                    "• /analyze period <дата1> <дата2> - повідомлення за період\n\n"
                    "📅 **Формати дат:**\n"
                    "• YYYY-MM-DD (2024-01-15)\n"
                    "• DD-MM-YYYY (15-01-2024)\n"
                    "• DD/MM/YYYY (15/01/2024)\n\n"
                    "💡 **Приклади:**\n"
                    "• /analyze last 50 messages\n"
                    "• /analyze date 15-01-2024\n"
                    "• /analyze period 01-01-2024 31-01-2024"
                )
                
                self.logger.log_event(
                    LogLevel.WARNING,
                    "analyze_invalid_command",
                    f"Invalid command type: {command_type}",
                    command_type=command_type,
                    args=args,
                    username=username,
                    chat_id=chat_id
                )
                
                # This will be handled by the calling function
                raise ValueError(error_message)
        
        except Exception as e:
            self.logger.log_event(
                LogLevel.ERROR,
                "analyze_argument_parsing_error",
                f"Error parsing command arguments: {str(e)}",
                args=args,
                username=username,
                chat_id=chat_id,
                error=str(e)
            )
            return None, None, "", None
    
    async def _parse_last_command(
        self, 
        args: List[str], 
        chat_id: int, 
        username: str
    ) -> tuple[str, List[Tuple[datetime, str, str]], str, str]:
        """Parse 'last N messages/days' command."""
        from modules.chat_analysis import get_last_n_messages_in_chat, get_messages_for_chat_last_n_days
        
        if len(args) < 3:
            error_message = (
                "❌ Неправильний формат команди. Використовуйте:\n"
                "/analyze last <число> messages\n"
                "або\n"
                "/analyze last <число> days\n\n"
                "Приклад: /analyze last 10 messages"
            )
            raise ValueError(error_message)
        
        try:
            number = int(args[1])
            if number <= 0:
                raise ValueError("Number must be positive")
            if number > 10000:  # Reasonable limit
                raise ValueError("Number too large (max 10000)")
        except ValueError as e:
            error_message = (
                "❌ Будь ласка, вкажіть коректне число (1-10000).\n"
                "Приклад: /analyze last 50 messages"
            )
            raise ValueError(error_message)
        
        unit = args[2].lower()
        if unit == "messages":
            messages = await get_last_n_messages_in_chat(chat_id, number)
            date_str = f"останні {number} повідомлень"
            time_period_key = f"last_{number}_messages"
        elif unit == "days":
            messages = await get_messages_for_chat_last_n_days(chat_id, number)
            date_str = f"останні {number} днів"
            time_period_key = f"last_{number}_days"
        else:
            error_message = (
                "❌ Неправильний формат команди. Використовуйте:\n"
                "/analyze last <число> messages\n"
                "або\n"
                "/analyze last <число> days\n\n"
                "Приклади:\n"
                "• /analyze last 20 messages\n"
                "• /analyze last 7 days"
            )
            raise ValueError(error_message)
        
        return "last", messages, date_str, time_period_key
    
    async def _parse_period_command(
        self, 
        args: List[str], 
        chat_id: int, 
        username: str
    ) -> tuple[str, List[Tuple[datetime, str, str]], str, str]:
        """Parse 'period date1 date2' command."""
        from modules.utils import DateParser
        from modules.chat_analysis import get_messages_for_chat_date_period
        
        if len(args) < 3:
            error_message = (
                "❌ Неправильний формат команди. Використовуйте:\n"
                "/analyze period <дата1> <дата2>\n\n"
                "Підтримувані формати дат:\n"
                "• YYYY-MM-DD (наприклад: 2024-01-15)\n"
                "• DD-MM-YYYY (наприклад: 15-01-2024)\n"
                "• DD/MM/YYYY (наприклад: 15/01/2024)\n\n"
                "Приклад: /analyze period 01-01-2024 31-01-2024"
            )
            raise ValueError(error_message)
        
        try:
            start_date, end_date = DateParser.validate_date_range(args[1], args[2])
            messages = await get_messages_for_chat_date_period(chat_id, start_date, end_date)
            date_str = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            time_period_key = f"period_{start_date.isoformat()}_{end_date.isoformat()}"
            
            return "period", messages, date_str, time_period_key
            
        except Exception as e:
            error_message = (
                "❌ Помилка в датах. Перевірте формат:\n\n"
                "Підтримувані формати дат:\n"
                "• YYYY-MM-DD (наприклад: 2024-01-15)\n"
                "• DD-MM-YYYY (наприклад: 15-01-2024)\n"
                "• DD/MM/YYYY (наприклад: 15/01/2024)\n\n"
                "Приклад: /analyze period 01-01-2024 31-01-2024"
            )
            raise ValueError(error_message)
    
    async def _parse_date_command(
        self, 
        args: List[str], 
        chat_id: int, 
        username: str
    ) -> tuple[str, List[Tuple[datetime, str, str]], str, str]:
        """Parse 'date <date>' command."""
        from modules.utils import DateParser
        from modules.chat_analysis import get_messages_for_chat_single_date
        
        if len(args) < 2:
            error_message = (
                "❌ Неправильний формат команди. Використовуйте:\n"
                "/analyze date <дата>\n\n"
                "Підтримувані формати дат:\n"
                "• YYYY-MM-DD (наприклад: 2024-01-15)\n"
                "• DD-MM-YYYY (наприклад: 15-01-2024)\n"
                "• DD/MM/YYYY (наприклад: 15/01/2024)\n\n"
                "Приклад: /analyze date 15-01-2024"
            )
            raise ValueError(error_message)
        
        try:
            # Parse the input date using DateParser
            target_date = DateParser.parse_date(args[1])
            
            # Get messages for the specified date (pass the date object directly)
            messages = await get_messages_for_chat_single_date(chat_id, target_date)
            
            # Format the date for display and caching
            formatted_date = target_date.strftime('%Y-%m-%d')
            date_str = target_date.strftime('%d.%m.%Y')
            time_period_key = f"date_{formatted_date}"
            
            return "date", messages, date_str, time_period_key
            
        except Exception as e:
            error_message = (
                "❌ Помилка в форматі дати. Використовуйте:\n\n"
                "Підтримувані формати дат:\n"
                "• YYYY-MM-DD (наприклад: 2024-01-15)\n"
                "• DD-MM-YYYY (наприклад: 15-01-2024)\n"
                "• DD/MM/YYYY (наприклад: 15/01/2024)\n\n"
                "Приклад: /analyze date 15-01-2024"
            )
            raise ValueError(error_message)
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error based on its type and message."""
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        if "database" in error_str or "connection" in error_str:
            return ErrorCategory.DATABASE
        elif "api" in error_str or "openrouter" in error_str or "timeout" in error_str:
            return ErrorCategory.API
        elif "parse" in error_str or "format" in error_str or "date" in error_str:
            return ErrorCategory.PARSING
        elif error_type in ["ValueError", "TypeError"]:
            return ErrorCategory.INPUT
        elif "network" in error_str:
            return ErrorCategory.NETWORK
        else:
            return ErrorCategory.GENERAL
    
    def _get_user_friendly_error_message(self, error: Exception) -> str:
        """Generate user-friendly error message based on error type."""
        error_str = str(error).lower()
        
        # If the error message is already user-friendly (starts with ❌), use it
        if str(error).startswith("❌"):
            return str(error)
        
        # Database errors
        if "database" in error_str or "connection" in error_str:
            return (
                "❌ Виникла проблема з підключенням до бази даних.\n"
                "Спробуйте пізніше або зверніться до адміністратора."
            )
        
        # API errors
        if "api" in error_str or "openrouter" in error_str or "timeout" in error_str:
            return (
                "❌ Сервіс аналізу тимчасово недоступний.\n"
                "Спробуйте пізніше або зверніться до адміністратора."
            )
        
        # Parsing errors
        if "parse" in error_str or "format" in error_str or "date" in error_str:
            return (
                "❌ Помилка в форматі команди або дати.\n"
                "Перевірте правильність введених даних та спробуйте знову."
            )
        
        # Generic error
        return (
            "❌ Під час аналізу повідомлень сталася помилка.\n"
            "Спробуйте пізніше або зверніться до адміністратора."
        )


# Global instance
enhanced_analyze = EnhancedAnalyzeCommand()


# Export the enhanced command handler
async def enhanced_analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced analyze command handler for external use."""
    await enhanced_analyze.analyze_command(update, context)