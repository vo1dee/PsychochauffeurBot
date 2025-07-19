"""
Standardized error messages and user feedback for consistent error communication.
"""

from typing import Dict, List, Optional, Any
from enum import Enum
import random

from modules.error_handler import ErrorSeverity, ErrorCategory
from modules.const import Stickers


class ErrorMessageType(Enum):
    """Types of error messages for different contexts."""
    USER_FRIENDLY = "user_friendly"
    TECHNICAL = "technical"
    ADMIN = "admin"
    DEBUG = "debug"


class StandardErrorMessages:
    """Standardized error messages for different scenarios."""
    
    # User-friendly messages by category
    USER_MESSAGES = {
        ErrorCategory.NETWORK: [
            "🌐 Network connection issue. Please try again in a moment.",
            "🔌 Having trouble connecting to external services. Please wait a bit and try again.",
            "📡 Connection timeout. The service might be temporarily unavailable."
        ],
        ErrorCategory.API: [
            "🔧 External service is temporarily unavailable. Please try again later.",
            "⚙️ API service error. We're working on it!",
            "🛠️ Third-party service issue. Please retry in a few minutes."
        ],
        ErrorCategory.DATABASE: [
            "💾 Database temporarily unavailable. Please try again shortly.",
            "🗄️ Data storage issue. Your request will be processed soon.",
            "📊 Database connection problem. Please wait a moment."
        ],
        ErrorCategory.PARSING: [
            "📝 Unable to process the data format. Please check your input.",
            "🔍 Data parsing error. Please verify the information provided.",
            "📋 Format not recognized. Please try a different format."
        ],
        ErrorCategory.INPUT: [
            "❌ Invalid input. Please check your command and try again.",
            "📝 Input format error. Please follow the correct format.",
            "⚠️ Invalid parameters. Please check the command usage."
        ],
        ErrorCategory.PERMISSION: [
            "🔒 Permission denied. You don't have access to this feature.",
            "🚫 Access restricted. Contact an administrator if needed.",
            "🔐 Insufficient permissions for this operation."
        ],
        ErrorCategory.RESOURCE: [
            "📁 File or resource not found. Please check the path.",
            "💿 Resource unavailable. Please try again later.",
            "🗂️ Unable to access the requested resource."
        ],
        ErrorCategory.GENERAL: [
            "⚠️ Something went wrong. Please try again.",
            "🤖 Unexpected error occurred. Please retry your request.",
            "❓ An error happened. Please try again in a moment."
        ]
    }
    
    # Technical messages for logging
    TECHNICAL_MESSAGES = {
        ErrorCategory.NETWORK: "Network operation failed",
        ErrorCategory.API: "External API call failed",
        ErrorCategory.DATABASE: "Database operation failed",
        ErrorCategory.PARSING: "Data parsing operation failed",
        ErrorCategory.INPUT: "Input validation failed",
        ErrorCategory.PERMISSION: "Permission check failed",
        ErrorCategory.RESOURCE: "Resource access failed",
        ErrorCategory.GENERAL: "General operation failed"
    }
    
    # Admin messages with more detail
    ADMIN_MESSAGES = {
        ErrorCategory.NETWORK: "Network connectivity issue detected. Check external service status.",
        ErrorCategory.API: "External API integration failure. Verify API keys and endpoints.",
        ErrorCategory.DATABASE: "Database connectivity or query execution failure.",
        ErrorCategory.PARSING: "Data format parsing error. Check input data structure.",
        ErrorCategory.INPUT: "User input validation failure. Review input constraints.",
        ErrorCategory.PERMISSION: "Authorization failure. Check user permissions and roles.",
        ErrorCategory.RESOURCE: "File system or resource access failure. Check paths and permissions.",
        ErrorCategory.GENERAL: "Unspecified system error. Check logs for details."
    }


class ErrorFeedbackManager:
    """Manages error feedback to users with appropriate messaging."""
    
    def __init__(self):
        self.error_stickers = [
            "CAACAgQAAxkBAAExX39nn7xI2ENP9ev7Ib1-0GCV0TcFvwACNxUAAn_QmFB67ToFiTpdgTYE",
            "CAACAgQAAxkBAAExYABnn7xJmVXzAAGOAAH-UqFN8KWOvJsAAjgVAAJ_0JhQeu06BYk6XYE2BA",
            "CAACAgQAAxkBAAExYAFnn7xJwQABuQABjgAB_lKhTfCljryaAAI5FQACF9CYUHrtOgWJOl2BNgQ"
        ]
    
    def get_user_message(
        self, 
        category: ErrorCategory, 
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        custom_message: Optional[str] = None
    ) -> str:
        """
        Get a user-friendly error message.
        
        Args:
            category: Error category
            severity: Error severity
            custom_message: Custom message to use instead of default
            
        Returns:
            User-friendly error message
        """
        if custom_message:
            return custom_message
        
        messages = StandardErrorMessages.USER_MESSAGES.get(category, 
                   StandardErrorMessages.USER_MESSAGES[ErrorCategory.GENERAL])
        
        # Add severity-based prefix for high/critical errors
        message = random.choice(messages)
        
        if severity == ErrorSeverity.HIGH:
            message = f"🚨 {message}"
        elif severity == ErrorSeverity.CRITICAL:
            message = f"💥 CRITICAL: {message}"
        
        return message
    
    def get_technical_message(
        self, 
        category: ErrorCategory, 
        function_name: str,
        details: Optional[str] = None
    ) -> str:
        """
        Get a technical error message for logging.
        
        Args:
            category: Error category
            function_name: Name of the function where error occurred
            details: Additional error details
            
        Returns:
            Technical error message
        """
        base_message = StandardErrorMessages.TECHNICAL_MESSAGES.get(
            category, StandardErrorMessages.TECHNICAL_MESSAGES[ErrorCategory.GENERAL]
        )
        
        message = f"{base_message} in {function_name}"
        
        if details:
            message += f": {details}"
        
        return message
    
    def get_admin_message(
        self, 
        category: ErrorCategory, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get an admin-level error message with more details.
        
        Args:
            category: Error category
            context: Additional context information
            
        Returns:
            Admin error message
        """
        base_message = StandardErrorMessages.ADMIN_MESSAGES.get(
            category, StandardErrorMessages.ADMIN_MESSAGES[ErrorCategory.GENERAL]
        )
        
        if context:
            context_str = ", ".join([f"{k}: {v}" for k, v in context.items()])
            base_message += f" Context: {context_str}"
        
        return base_message
    
    def get_error_sticker(self, category: ErrorCategory) -> str:
        """
        Get an appropriate error sticker for the category.
        
        Args:
            category: Error category
            
        Returns:
            Sticker ID
        """
        # For now, return a random error sticker
        # Could be enhanced to return category-specific stickers
        return random.choice(self.error_stickers)
    
    def format_error_for_telegram(
        self, 
        message: str, 
        include_sticker: bool = True,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ) -> Dict[str, Any]:
        """
        Format an error message for Telegram with appropriate styling.
        
        Args:
            message: Error message
            include_sticker: Whether to include a sticker
            severity: Error severity for styling
            
        Returns:
            Dictionary with formatted message and optional sticker
        """
        # Apply markdown formatting based on severity
        if severity == ErrorSeverity.HIGH:
            formatted_message = f"*{message}*"
        elif severity == ErrorSeverity.CRITICAL:
            formatted_message = f"*⚠️ {message} ⚠️*"
        else:
            formatted_message = message
        
        result = {
            "text": formatted_message,
            "parse_mode": "Markdown"
        }
        
        if include_sticker:
            result["sticker"] = random.choice(self.error_stickers)
        
        return result


class ErrorResponseBuilder:
    """Builder for creating standardized error responses."""
    
    def __init__(self):
        self.feedback_manager = ErrorFeedbackManager()
        self.response_templates = {
            "command_error": "❌ Command failed: {message}",
            "service_error": "🔧 Service unavailable: {message}",
            "validation_error": "📝 Invalid input: {message}",
            "permission_error": "🔒 Access denied: {message}",
            "network_error": "🌐 Connection issue: {message}",
            "general_error": "⚠️ Error: {message}"
        }
    
    def build_user_response(
        self, 
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        custom_message: Optional[str] = None,
        include_help: bool = True
    ) -> Dict[str, Any]:
        """
        Build a complete user error response.
        
        Args:
            category: Error category
            severity: Error severity
            custom_message: Custom error message
            include_help: Whether to include help text
            
        Returns:
            Complete error response dictionary
        """
        message = self.feedback_manager.get_user_message(category, severity, custom_message)
        
        if include_help:
            help_text = self._get_help_text(category)
            if help_text:
                message += f"\n\n💡 {help_text}"
        
        return self.feedback_manager.format_error_for_telegram(message, True, severity)
    
    def build_admin_response(
        self, 
        category: ErrorCategory,
        function_name: str,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[str] = None
    ) -> str:
        """
        Build an admin error response with technical details.
        
        Args:
            category: Error category
            function_name: Function where error occurred
            context: Additional context
            original_error: Original error message
            
        Returns:
            Formatted admin error message
        """
        admin_message = self.feedback_manager.get_admin_message(category, context)
        
        response_parts = [
            f"🔧 **Admin Error Report**",
            f"**Function:** {function_name}",
            f"**Category:** {category.value}",
            f"**Message:** {admin_message}"
        ]
        
        if context:
            response_parts.append(f"**Context:** {context}")
        
        if original_error:
            response_parts.append(f"**Original Error:** {original_error}")
        
        return "\n".join(response_parts)
    
    def _get_help_text(self, category: ErrorCategory) -> Optional[str]:
        """
        Get helpful text for users based on error category.
        
        Args:
            category: Error category
            
        Returns:
            Help text or None
        """
        help_texts = {
            ErrorCategory.INPUT: "Check the command format and try again.",
            ErrorCategory.PERMISSION: "Contact an admin if you need access.",
            ErrorCategory.NETWORK: "Check your internet connection.",
            ErrorCategory.API: "The service might be temporarily down.",
            ErrorCategory.RESOURCE: "Make sure the file or resource exists."
        }
        
        return help_texts.get(category)


# Global instances
error_feedback_manager = ErrorFeedbackManager()
error_response_builder = ErrorResponseBuilder()


# Convenience functions
def get_user_error_message(
    category: ErrorCategory, 
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    custom_message: Optional[str] = None
) -> str:
    """Get a user-friendly error message."""
    return error_feedback_manager.get_user_message(category, severity, custom_message)


def get_error_response(
    category: ErrorCategory,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    custom_message: Optional[str] = None,
    include_help: bool = True
) -> Dict[str, Any]:
    """Get a complete error response for Telegram."""
    return error_response_builder.build_user_response(
        category, severity, custom_message, include_help
    )


def get_admin_error_report(
    category: ErrorCategory,
    function_name: str,
    context: Optional[Dict[str, Any]] = None,
    original_error: Optional[str] = None
) -> str:
    """Get an admin error report."""
    return error_response_builder.build_admin_response(
        category, function_name, context, original_error
    )