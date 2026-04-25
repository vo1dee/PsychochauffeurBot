"""
Diagnostics command for system health monitoring and troubleshooting.

This module provides a comprehensive diagnostics command that administrators
can use to check system health, service availability, and recent errors.

Requirements addressed: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

from telegram import Update
from telegram.ext import ContextTypes

from modules.enhanced_error_diagnostics import enhanced_diagnostics, get_system_health_report
from modules.command_diagnostics import (
    enhance_command_with_diagnostics,
    validate_command_configuration,
    check_command_dependencies
)
from modules.structured_logging import StructuredLogger, LogLevel
from modules.const import KYIV_TZ
from modules.utils import clock_emoji


class SystemDiagnosticsCommand:
    """
    Comprehensive system diagnostics command for administrators.
    
    Provides detailed information about:
    - System health and resource usage
    - External service availability
    - Recent errors and their patterns
    - Command execution metrics
    - Configuration validation
    """
    
    def __init__(self) -> None:
        self.logger = StructuredLogger("diagnostics_command")
    
    @enhance_command_with_diagnostics("diagnostics")
    async def diagnostics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Main diagnostics command handler.
        
        Usage:
        /diagnostics - Full system health report
        /diagnostics quick - Quick health check
        /diagnostics services - Service health only
        /diagnostics errors - Recent errors only
        /diagnostics config - Configuration validation
        /diagnostics commands - Command execution metrics
        """
        if not update.message or not update.effective_user:
            return
        
        # Check if user is authorized (you may want to implement proper admin checks)
        user_id = update.effective_user.id
        
        # Parse command arguments
        args = context.args or []
        report_type = args[0].lower() if args else "full"
        
        # Show initial status message
        status_msg = await update.message.reply_text("🔍 Генерую діагностичний звіт...")
        
        try:
            if report_type == "quick":
                report = await self._generate_quick_report()
                formatted_report = self._format_quick_report(report)
            elif report_type == "services":
                report = await self._generate_services_report()
                formatted_report = self._format_services_report(report)
            elif report_type == "errors":
                report = await self._generate_errors_report()
                formatted_report = self._format_errors_report(report)
            elif report_type == "config":
                report = await self._generate_config_report()
                formatted_report = self._format_config_report(report)
            elif report_type == "commands":
                report = await self._generate_commands_report()
                formatted_report = self._format_commands_report(report)
            else:
                # Full report
                report = await get_system_health_report()
                formatted_report = self._format_full_report(report)
            
            # Update status message with results
            await status_msg.edit_text(formatted_report, parse_mode='Markdown')
            
            # Log diagnostics command execution
            self.logger.log_event(
                LogLevel.INFO,
                "diagnostics_command_executed",
                f"Diagnostics command executed by user {user_id}",
                user_id=user_id,
                report_type=report_type,
                chat_id=update.effective_chat.id if update.effective_chat else 0
            )
            
        except Exception as e:
            error_msg = f"❌ Помилка при генерації діагностичного звіту: {str(e)}"
            await status_msg.edit_text(error_msg)
            
            self.logger.log_event(
                LogLevel.ERROR,
                "diagnostics_command_error",
                f"Error generating diagnostics report: {str(e)}",
                user_id=user_id,
                report_type=report_type,
                error=str(e)
            )
    
    async def _generate_quick_report(self) -> Dict[str, Any]:
        """Generate a quick health check report."""
        return {
            "timestamp": datetime.now(KYIV_TZ).isoformat(),
            "service_health": enhanced_diagnostics.get_service_health_summary(),
            "command_metrics": enhanced_diagnostics.get_command_metrics_summary(),
            "system_status": "healthy"  # Simplified for quick check
        }
    
    async def _generate_services_report(self) -> Dict[str, Any]:
        """Generate a detailed services health report."""
        services_health = enhanced_diagnostics.get_service_health_summary()
        
        # Add dependency checks for critical commands
        dependency_checks = {}
        for command in ["analyze", "flares"]:
            dependency_checks[command] = await check_command_dependencies(command)
        
        return {
            "timestamp": datetime.now(KYIV_TZ).isoformat(),
            "services": services_health,
            "command_dependencies": dependency_checks
        }
    
    async def _generate_errors_report(self) -> Dict[str, Any]:
        """Generate a detailed errors report."""
        try:
            from modules.error_analytics import get_error_summary, get_recent_errors
            
            error_summary = get_error_summary()
            recent_errors = get_recent_errors(20)
            
            return {
                "timestamp": datetime.now(KYIV_TZ).isoformat(),
                "error_summary": error_summary,
                "recent_errors": recent_errors
            }
        except Exception as e:
            return {
                "timestamp": datetime.now(KYIV_TZ).isoformat(),
                "error": f"Failed to generate errors report: {str(e)}"
            }
    
    async def _generate_config_report(self) -> Dict[str, Any]:
        """Generate a configuration validation report."""
        config_validations = {}
        
        # Validate configuration for critical commands
        for command in ["analyze", "flares"]:
            config_validations[command] = await validate_command_configuration(command)
        
        return {
            "timestamp": datetime.now(KYIV_TZ).isoformat(),
            "configuration_validations": config_validations
        }
    
    async def _generate_commands_report(self) -> Dict[str, Any]:
        """Generate a command execution metrics report."""
        return {
            "timestamp": datetime.now(KYIV_TZ).isoformat(),
            "command_metrics": enhanced_diagnostics.get_command_metrics_summary(),
            "detailed_metrics": dict(enhanced_diagnostics.command_metrics)
        }
    
    def _format_quick_report(self, report: Dict[str, Any]) -> str:
        """Format quick health check report."""
        services = report.get("service_health", {})
        metrics = report.get("command_metrics", {})
        
        # Count healthy vs unhealthy services
        healthy_services = sum(1 for s in services.values() if s.get("status") == "healthy")
        total_services = len(services)
        
        # Get command success rate
        success_rate = metrics.get("success_rate", 0)
        
        status_emoji = "✅" if healthy_services == total_services and success_rate > 90 else "⚠️"
        
        return f"""
{status_emoji} **Швидка перевірка системи**

📊 **Загальний стан:**
• Сервіси: {healthy_services}/{total_services} здорові
• Команди: {success_rate:.1f}% успішних
• Час перевірки: {datetime.now(KYIV_TZ).strftime('%H:%M %d.%m.%Y')}

💡 Для детальної інформації використовуйте:
• `/diagnostics services` - стан сервісів
• `/diagnostics errors` - останні помилки
• `/diagnostics config` - перевірка конфігурації
        """.strip()
    
    def _format_services_report(self, report: Dict[str, Any]) -> str:
        """Format services health report."""
        services = report.get("services", {})
        dependencies = report.get("command_dependencies", {})
        
        lines = ["🔧 **Стан сервісів**", ""]
        
        # Service health
        for service_name, health in services.items():
            status = health.get("status", "unknown")
            emoji = "✅" if status == "healthy" else "❌" if status == "unhealthy" else "⚠️"
            
            response_time = health.get("response_time_ms")
            time_str = f" ({response_time:.0f}ms)" if response_time else ""
            
            availability = health.get("availability_percent", 0)
            
            lines.append(f"{emoji} **{service_name}**: {status}{time_str}")
            lines.append(f"   Доступність: {availability:.1f}%")
            
            if health.get("consecutive_failures", 0) > 0:
                lines.append(f"   Послідовні збої: {health['consecutive_failures']}")
            
            lines.append("")
        
        # Command dependencies
        if dependencies:
            lines.append("🔗 **Залежності команд:**")
            lines.append("")
            
            for command, deps in dependencies.items():
                healthy = deps.get("healthy", False)
                emoji = "✅" if healthy else "❌"
                lines.append(f"{emoji} **{command}**: {'здорові' if healthy else 'проблеми'}")
                
                for dep_name, dep_info in deps.get("dependencies", {}).items():
                    dep_healthy = dep_info.get("healthy", False)
                    dep_emoji = "✅" if dep_healthy else "❌"
                    lines.append(f"   {dep_emoji} {dep_name}")
                
                lines.append("")
        
        return "\n".join(lines)
    
    def _format_errors_report(self, report: Dict[str, Any]) -> str:
        """Format errors report."""
        if "error" in report:
            return f"❌ **Помилка генерації звіту про помилки**\n\n{report['error']}"
        
        summary = report.get("error_summary", {})
        recent_errors = report.get("recent_errors", [])
        
        lines = ["🚨 **Звіт про помилки**", ""]
        
        # Error summary
        total_errors = summary.get("total_errors", 0)
        lines.append(f"📊 **Загальна статистика:**")
        lines.append(f"• Всього помилок: {total_errors}")
        
        # By category
        by_category = summary.get("by_category", {})
        if by_category:
            lines.append(f"• За категоріями:")
            for category, count in by_category.items():
                lines.append(f"  - {category}: {count}")
        
        # By severity
        by_severity = summary.get("by_severity", {})
        if by_severity:
            lines.append(f"• За важливістю:")
            for severity, count in by_severity.items():
                lines.append(f"  - {severity}: {count}")
        
        lines.append("")
        
        # Recent errors
        if recent_errors:
            lines.append("🕐 **Останні помилки:**")
            lines.append("")
            
            for error in recent_errors[:10]:  # Show last 10 errors
                timestamp = error.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        time_str = dt.strftime("%H:%M %d.%m")
                    except (ValueError, TypeError):
                        time_str = timestamp[:16]
                else:
                    time_str = "Unknown"
                
                category = error.get("category", "unknown")
                severity = error.get("severity", "unknown")
                message = error.get("message", "No message")[:100]
                
                lines.append(f"• `{time_str}` [{category}/{severity}]")
                lines.append(f"  {message}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _format_config_report(self, report: Dict[str, Any]) -> str:
        """Format configuration validation report."""
        validations = report.get("configuration_validations", {})
        
        lines = ["⚙️ **Перевірка конфігурації**", ""]
        
        for command, validation in validations.items():
            valid = validation.get("valid", False)
            emoji = "✅" if valid else "❌"
            
            lines.append(f"{emoji} **Команда {command}**: {'OK' if valid else 'Проблеми'}")
            
            issues = validation.get("issues", [])
            if issues:
                lines.append("   Проблеми:")
                for issue in issues:
                    lines.append(f"   • {issue}")
            
            warnings = validation.get("warnings", [])
            if warnings:
                lines.append("   Попередження:")
                for warning in warnings:
                    lines.append(f"   ⚠️ {warning}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_commands_report(self, report: Dict[str, Any]) -> str:
        """Format command execution metrics report."""
        metrics = report.get("command_metrics", {})
        
        lines = ["📈 **Метрики виконання команд**", ""]
        
        total_commands = metrics.get("total_commands", 0)
        successful_commands = metrics.get("successful_commands", 0)
        failed_commands = metrics.get("failed_commands", 0)
        success_rate = metrics.get("success_rate", 0)
        avg_duration = metrics.get("average_duration_seconds", 0)
        
        lines.append(f"📊 **Загальна статистика:**")
        lines.append(f"• Всього команд: {total_commands}")
        lines.append(f"• Успішних: {successful_commands}")
        lines.append(f"• Невдалих: {failed_commands}")
        lines.append(f"• Успішність: {success_rate:.1f}%")
        lines.append(f"• Середній час: {avg_duration:.3f}с")
        lines.append("")
        
        # Command counts
        command_counts = metrics.get("command_counts", {})
        if command_counts:
            lines.append("🔢 **За командами:**")
            for command, count in sorted(command_counts.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"• {command}: {count}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_full_report(self, report: Dict[str, Any]) -> str:
        """Format comprehensive system health report."""
        lines = ["🏥 **Повний діагностичний звіт**", ""]
        
        # System state
        system_state = report.get("system_state", {})
        if system_state:
            lines.append("💻 **Стан системи:**")
            lines.append(f"• CPU: {system_state.get('cpu_usage', 0):.1f}%")
            lines.append(f"• Пам'ять: {system_state.get('memory_usage', 0):.1f} MB")
            lines.append(f"• Диск: {system_state.get('disk_usage', 0):.1f}%")
            lines.append("")
        
        # Service health summary
        service_health = report.get("service_health", {})
        if service_health:
            healthy_services = sum(1 for s in service_health.values() if s.get("status") == "healthy")
            total_services = len(service_health)
            
            lines.append(f"🔧 **Сервіси:** {healthy_services}/{total_services} здорові")
            
            for service_name, health in service_health.items():
                status = health.get("status", "unknown")
                emoji = "✅" if status == "healthy" else "❌"
                lines.append(f"   {emoji} {service_name}")
            
            lines.append("")
        
        # Command metrics summary
        command_metrics = report.get("command_metrics", {})
        if command_metrics:
            success_rate = command_metrics.get("success_rate", 0)
            total_commands = command_metrics.get("total_commands", 0)
            
            lines.append(f"📈 **Команди:** {success_rate:.1f}% успішних ({total_commands} всього)")
            lines.append("")
        
        # Recent errors summary
        recent_errors = report.get("recent_errors", [])
        if recent_errors:
            lines.append(f"🚨 **Останні помилки:** {len(recent_errors)}")
            for error in recent_errors[:5]:  # Show last 5 errors
                timestamp = error.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        time_str = dt.strftime("%H:%M")
                    except (ValueError, TypeError):
                        time_str = "??:??"
                else:
                    time_str = "??:??"
                
                category = error.get("category", "unknown")
                lines.append(f"   • {time_str} [{category}]")
            
            lines.append("")
        
        # Configuration status
        config_status = report.get("configuration_status", {})
        if config_status:
            valid = config_status.get("valid", False)
            emoji = "✅" if valid else "❌"
            lines.append(f"{emoji} **Конфігурація:** {'OK' if valid else 'Проблеми'}")
            
            issues = config_status.get("issues", [])
            if issues:
                for issue in issues[:3]:  # Show first 3 issues
                    lines.append(f"   • {issue}")
            
            lines.append("")
        
        _now = datetime.now(KYIV_TZ)
        lines.append(f"{clock_emoji(_now.hour, _now.minute)} **Час звіту:** {_now.strftime('%H:%M %d.%m.%Y')}")
        
        return "\n".join(lines)


# Global instance
system_diagnostics = SystemDiagnosticsCommand()


# Export the command handler
async def diagnostics_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Diagnostics command handler for external use."""
    await system_diagnostics.diagnostics_command(update, context)