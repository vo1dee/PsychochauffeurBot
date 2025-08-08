"""
Enhanced flares command with comprehensive error logging and diagnostics.

This module provides an enhanced version of the flares command that includes:
- Comprehensive error logging and diagnostics
- Performance metrics tracking
- External service monitoring
- User-friendly error messages
- Configuration validation

Requirements addressed: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from telegram import Update
from telegram.ext import ContextTypes

from modules.command_diagnostics import (
    enhance_command_with_diagnostics,
    track_api_call,
    log_command_milestone,
    log_command_performance_metric,
    validate_command_configuration,
    check_command_dependencies
)
from modules.enhanced_error_diagnostics import enhanced_diagnostics
from modules.structured_logging import StructuredLogger, LogLevel
from modules.error_handler import ErrorHandler, StandardError, ErrorCategory, ErrorSeverity
from modules.const import KYIV_TZ, Config
from modules.logger import general_logger, error_logger


class EnhancedFlaresCommand:
    """
    Enhanced flares command with comprehensive diagnostics and error handling.
    
    This class wraps the existing flares command functionality with enhanced
    logging, metrics tracking, and diagnostic capabilities.
    """
    
    def __init__(self) -> None:
        self.logger = StructuredLogger("enhanced_flares")
    
    @enhance_command_with_diagnostics("flares")
    async def flares_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Enhanced flares command with comprehensive diagnostics.
        
        This method provides the same functionality as the original flares command
        but with enhanced error logging, performance tracking, and diagnostics.
        """
        if not update.effective_chat or not update.effective_user:
            return
        
        # Extract user and chat information
        chat_id = int(update.effective_chat.id)
        user_id = int(update.effective_user.id)
        username = update.effective_user.username or f"ID:{user_id}"
        
        # Validate configuration before proceeding
        config_validation = await validate_command_configuration("flares")
        if not config_validation["valid"]:
            error_message = (
                "❌ Конфігурація команди flares містить помилки.\n"
                "Зверніться до адміністратора для вирішення проблем."
            )
            
            self.logger.log_event(
                LogLevel.ERROR,
                "flares_config_invalid",
                "Flares command configuration validation failed",
                user_id=user_id,
                chat_id=chat_id,
                issues=config_validation["issues"]
            )
            
            if update.message:
                await update.message.reply_text(error_message)
            return
        
        # Check command dependencies
        dependency_check = await check_command_dependencies("flares")
        if not dependency_check["healthy"]:
            error_message = (
                "❌ Деякі сервіси, необхідні для отримання знімків, недоступні.\n"
                "Спробуйте пізніше або зверніться до адміністратора."
            )
            
            self.logger.log_event(
                LogLevel.ERROR,
                "flares_dependencies_unhealthy",
                "Flares command dependencies are unhealthy",
                user_id=user_id,
                chat_id=chat_id,
                dependencies=dependency_check["dependencies"]
            )
            
            if update.message:
                await update.message.reply_text(error_message)
            return
        
        log_command_milestone("flares", "validation_completed", 
                            user_id=user_id, chat_id=chat_id)
        
        status_msg = None
        try:
            # Initialize screenshot manager with enhanced diagnostics
            from modules.utils import ScreenshotManager
            manager = ScreenshotManager()
            
            # Check tool availability with detailed logging
            if not manager._check_wkhtmltoimage_availability():
                error_message = (
                    "❌ Інструмент для створення знімків недоступний.\n"
                    "Зверніться до адміністратора для встановлення wkhtmltoimage."
                )
                
                self.logger.log_event(
                    LogLevel.ERROR,
                    "flares_tool_unavailable",
                    "wkhtmltoimage tool is not available",
                    user_id=user_id,
                    chat_id=chat_id
                )
                
                if update.message:
                    await update.message.reply_text(error_message)
                return
            
            log_command_milestone("flares", "tool_check_passed", 
                                user_id=user_id, chat_id=chat_id)
            
            # Get status information for better progress indicators
            status_info = manager.get_screenshot_status_info()
            
            # Log detailed status information
            self.logger.log_event(
                LogLevel.INFO,
                "flares_status_check",
                "Screenshot status information gathered",
                user_id=user_id,
                chat_id=chat_id,
                status_info=status_info
            )
            
            # Show initial status message with diagnostic info
            initial_status = "🔍 Перевіряю наявність актуального знімку..."
            if not status_info['tool_available']:
                initial_status += "\n⚠️ Інструмент wkhtmltoimage недоступний"
            elif not status_info['directory_exists']:
                initial_status += "\n📁 Створюю директорію для знімків..."
            elif status_info['has_screenshot'] and status_info['is_fresh']:
                initial_status += "\n✅ Знайдено актуальний знімок"
            elif status_info['has_screenshot']:
                initial_status += f"\n🕐 Знайдено застарілий знімок (вік: {status_info['age_hours']:.1f} год)"
            
            if update.message:
                status_msg = await update.message.reply_text(initial_status)
            
            log_command_milestone("flares", "status_message_sent", 
                                user_id=user_id, chat_id=chat_id)
            
            # Try to get current screenshot with API call tracking
            screenshot_path = None
            
            if not status_info['has_screenshot'] or not status_info['is_fresh']:
                # Need to generate new screenshot - track the API call
                log_command_milestone("flares", "generating_screenshot", 
                                    user_id=user_id, chat_id=chat_id)
                
                # Update status message
                if status_msg:
                    progress_msg = (
                        "🔄 Генерую новий знімок сонячних спалахів...\n"
                        "⏳ Це може зайняти до 15-30 секунд\n"
                        "📊 Завантажую дані з api.meteoagent.com..."
                    )
                    await status_msg.edit_text(progress_msg)
                
                # Track the external API call to MeteoAgent
                async with track_api_call("meteoagent", "api.meteoagent.com", "GET") as api_tracker:
                    try:
                        screenshot_path = await manager.get_current_screenshot()
                        api_tracker.set_status_code(200)  # Assume success if no exception
                    except Exception as api_error:
                        api_tracker.set_status_code(500)  # API call failed
                        raise api_error
            else:
                # Use existing fresh screenshot
                log_command_milestone("flares", "using_cached_screenshot", 
                                    user_id=user_id, chat_id=chat_id)
                
                screenshot_path = await manager.get_current_screenshot()
                
                if status_msg:
                    await status_msg.edit_text("✅ Використовую актуальний знімок...")
            
            # Validate screenshot generation
            if not screenshot_path or not os.path.exists(screenshot_path):
                error_message = (
                    "❌ Не вдалося створити або знайти знімок сонячних спалахів.\n"
                    "Спробуйте пізніше або зверніться до адміністратора."
                )
                
                self.logger.log_event(
                    LogLevel.ERROR,
                    "flares_screenshot_generation_failed",
                    "Screenshot generation failed or file not found",
                    user_id=user_id,
                    chat_id=chat_id,
                    screenshot_path=screenshot_path,
                    file_exists=os.path.exists(screenshot_path) if screenshot_path else False
                )
                
                # Clean up status message
                if status_msg:
                    await status_msg.edit_text(error_message)
                elif update.message:
                    await update.message.reply_text(error_message)
                return
            
            log_command_milestone("flares", "screenshot_ready", 
                                screenshot_path=screenshot_path,
                                file_size=os.path.getsize(screenshot_path),
                                user_id=user_id, chat_id=chat_id)
            
            # Get file information for metrics and caption
            file_stats = os.stat(screenshot_path)
            file_size_mb = file_stats.st_size / (1024 * 1024)
            mod_time = datetime.fromtimestamp(file_stats.st_mtime)
            mod_time = mod_time.astimezone(KYIV_TZ)
            
            # Calculate next update time
            kyiv_now = datetime.now(KYIV_TZ)
            hours_since_update = (kyiv_now - mod_time).total_seconds() / 3600
            hours_until_next = max(0, manager.FRESHNESS_THRESHOLD_HOURS - hours_since_update)
            next_screenshot = kyiv_now + timedelta(hours=hours_until_next)
            
            # Determine freshness status
            freshness_status = "актуальний" if hours_since_update < manager.FRESHNESS_THRESHOLD_HOURS else "застарілий"
            
            # Prepare caption with enhanced information
            caption = (
                f"🌞 Прогноз сонячних спалахів і магнітних бурь\n\n"
                f"📅 Час знімку: {mod_time.strftime('%H:%M %d.%m.%Y')}\n"
                f"📊 Статус: {freshness_status}\n"
                f"🔄 Наступне оновлення: {next_screenshot.strftime('%H:%M %d.%m.%Y')}\n"
                f"📁 Розмір файлу: {file_size_mb:.1f} MB\n\n"
                f"🔗 Джерело: api.meteoagent.com"
            )
            
            # Delete status message before sending photo
            if status_msg:
                await status_msg.delete()
                status_msg = None
            
            log_command_milestone("flares", "sending_screenshot", 
                                user_id=user_id, chat_id=chat_id)
            
            # Send the screenshot with error handling
            try:
                with open(screenshot_path, 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=caption
                    )
                
                log_command_milestone("flares", "screenshot_sent_successfully", 
                                    user_id=user_id, chat_id=chat_id)
                
                # Log performance metrics
                log_command_performance_metric(
                    "flares", "screenshot_file_size", file_size_mb, "MB",
                    user_id=user_id, chat_id=chat_id
                )
                
                log_command_performance_metric(
                    "flares", "screenshot_age_hours", hours_since_update, "hours",
                    user_id=user_id, chat_id=chat_id
                )
                
                # Log successful completion
                self.logger.log_event(
                    LogLevel.INFO,
                    "flares_completed_successfully",
                    "Flares command completed successfully",
                    user_id=user_id,
                    chat_id=chat_id,
                    screenshot_path=screenshot_path,
                    file_size_mb=file_size_mb,
                    freshness_status=freshness_status,
                    hours_since_update=hours_since_update
                )
                
            except Exception as send_error:
                error_message = (
                    "❌ Не вдалося надіслати знімок сонячних спалахів.\n"
                    "Спробуйте пізніше або зверніться до адміністратора."
                )
                
                self.logger.log_event(
                    LogLevel.ERROR,
                    "flares_send_failed",
                    f"Failed to send screenshot: {str(send_error)}",
                    user_id=user_id,
                    chat_id=chat_id,
                    screenshot_path=screenshot_path,
                    error=str(send_error)
                )
                
                if update.message:
                    await update.message.reply_text(error_message)
                
                raise send_error
                
        except Exception as e:
            # Enhanced error handling with detailed context
            error_context = {
                "command": "flares",
                "user_id": user_id,
                "chat_id": chat_id,
                "username": username,
                "screenshot_path": locals().get('screenshot_path'),
                "status_info": locals().get('status_info', {})
            }
            
            # Create a standardized error
            standard_error = StandardError(
                message=f"Flares command failed: {str(e)}",
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
            
            # Clean up status message
            if status_msg:
                try:
                    await status_msg.delete()
                except:
                    pass
            
            # Send user-friendly error message
            user_error_message = self._get_user_friendly_error_message(e)
            
            if update.message:
                try:
                    await update.message.reply_text(user_error_message)
                except Exception:
                    pass  # Don't fail if we can't send the error message
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error based on its type and message."""
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        if "network" in error_str or "connection" in error_str or "timeout" in error_str:
            return ErrorCategory.NETWORK
        elif "api" in error_str or "meteoagent" in error_str:
            return ErrorCategory.API
        elif "file" in error_str or "directory" in error_str or "permission" in error_str:
            return ErrorCategory.RESOURCE
        elif "wkhtmltoimage" in error_str or "tool" in error_str:
            return ErrorCategory.RESOURCE
        else:
            return ErrorCategory.GENERAL
    
    def _get_user_friendly_error_message(self, error: Exception) -> str:
        """Generate user-friendly error message based on error type."""
        error_str = str(error).lower()
        
        # Network/API errors
        if "network" in error_str or "connection" in error_str or "timeout" in error_str:
            return (
                "❌ Проблема з мережевим підключенням до сервісу прогнозів.\n"
                "Перевірте інтернет-з'єднання та спробуйте пізніше."
            )
        
        # API errors
        if "api" in error_str or "meteoagent" in error_str:
            return (
                "❌ Сервіс прогнозів сонячних спалахів тимчасово недоступний.\n"
                "Спробуйте пізніше або зверніться до адміністратора."
            )
        
        # File/resource errors
        if "file" in error_str or "directory" in error_str or "permission" in error_str:
            return (
                "❌ Проблема з файловою системою при створенні знімку.\n"
                "Зверніться до адміністратора для вирішення проблеми."
            )
        
        # Tool errors
        if "wkhtmltoimage" in error_str or "tool" in error_str:
            return (
                "❌ Інструмент для створення знімків недоступний або працює некоректно.\n"
                "Зверніться до адміністратора для встановлення або налаштування wkhtmltoimage."
            )
        
        # Generic error
        return (
            "❌ Під час створення знімку сонячних спалахів сталася помилка.\n"
            "Спробуйте пізніше або зверніться до адміністратора."
        )


# Global instance
enhanced_flares = EnhancedFlaresCommand()


# Export the enhanced command handler
async def enhanced_flares_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced flares command handler for external use."""
    await enhanced_flares.flares_command(update, context)