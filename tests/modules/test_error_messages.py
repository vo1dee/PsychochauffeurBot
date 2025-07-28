"""
Unit tests for error_messages.py module.
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any

from modules.error_messages import (
    ErrorMessageType,
    StandardErrorMessages,
    ErrorFeedbackManager,
    ErrorResponseBuilder,
    error_feedback_manager,
    error_response_builder,
    get_user_error_message,
    get_error_response,
    get_admin_error_report
)
from modules.error_handler import ErrorSeverity, ErrorCategory
from modules.const import Stickers


class TestErrorMessageType:
    """Test ErrorMessageType enum."""
    
    def test_enum_values(self):
        """Test that enum has expected values."""
        assert ErrorMessageType.USER_FRIENDLY.value == "user_friendly"
        assert ErrorMessageType.TECHNICAL.value == "technical"
        assert ErrorMessageType.ADMIN.value == "admin"
        assert ErrorMessageType.DEBUG.value == "debug"


class TestStandardErrorMessages:
    """Test StandardErrorMessages class."""
    
    def test_user_messages_structure(self):
        """Test that USER_MESSAGES has all expected categories."""
        expected_categories = [
            ErrorCategory.NETWORK,
            ErrorCategory.API,
            ErrorCategory.DATABASE,
            ErrorCategory.PARSING,
            ErrorCategory.INPUT,
            ErrorCategory.PERMISSION,
            ErrorCategory.RESOURCE,
            ErrorCategory.GENERAL
        ]
        
        for category in expected_categories:
            assert category in StandardErrorMessages.USER_MESSAGES
            messages = StandardErrorMessages.USER_MESSAGES[category]
            assert isinstance(messages, list)
            assert len(messages) > 0
            assert all(isinstance(msg, str) for msg in messages)
    
    def test_technical_messages_structure(self):
        """Test that TECHNICAL_MESSAGES has all expected categories."""
        expected_categories = [
            ErrorCategory.NETWORK,
            ErrorCategory.API,
            ErrorCategory.DATABASE,
            ErrorCategory.PARSING,
            ErrorCategory.INPUT,
            ErrorCategory.PERMISSION,
            ErrorCategory.RESOURCE,
            ErrorCategory.GENERAL
        ]
        
        for category in expected_categories:
            assert category in StandardErrorMessages.TECHNICAL_MESSAGES
            message = StandardErrorMessages.TECHNICAL_MESSAGES[category]
            assert isinstance(message, str)
            assert len(message) > 0
    
    def test_admin_messages_structure(self):
        """Test that ADMIN_MESSAGES has all expected categories."""
        expected_categories = [
            ErrorCategory.NETWORK,
            ErrorCategory.API,
            ErrorCategory.DATABASE,
            ErrorCategory.PARSING,
            ErrorCategory.INPUT,
            ErrorCategory.PERMISSION,
            ErrorCategory.RESOURCE,
            ErrorCategory.GENERAL
        ]
        
        for category in expected_categories:
            assert category in StandardErrorMessages.ADMIN_MESSAGES
            message = StandardErrorMessages.ADMIN_MESSAGES[category]
            assert isinstance(message, str)
            assert len(message) > 0


class TestErrorFeedbackManager:
    """Test ErrorFeedbackManager class."""
    
    def test_initialization(self):
        """Test ErrorFeedbackManager initialization."""
        manager = ErrorFeedbackManager()
        assert hasattr(manager, 'error_stickers')
        assert isinstance(manager.error_stickers, list)
        assert len(manager.error_stickers) > 0
        # Check that error_stickers list is not empty and contains valid sticker IDs
        assert len(manager.error_stickers) > 0
        assert all(isinstance(sticker, str) and len(sticker) > 0 for sticker in manager.error_stickers)
    
    def test_get_user_message_default(self):
        """Test get_user_message with default parameters."""
        manager = ErrorFeedbackManager()
        
        with patch('modules.error_messages.random.choice') as mock_choice:
            mock_choice.return_value = "Test message"
            result = manager.get_user_message(ErrorCategory.NETWORK)
            
            assert result == "Test message"
            mock_choice.assert_called_once()
    
    def test_get_user_message_custom_message(self):
        """Test get_user_message with custom message."""
        manager = ErrorFeedbackManager()
        custom_msg = "Custom error message"
        
        result = manager.get_user_message(ErrorCategory.NETWORK, custom_message=custom_msg)
        assert result == custom_msg
    
    def test_get_user_message_high_severity(self):
        """Test get_user_message with high severity."""
        manager = ErrorFeedbackManager()
        
        with patch('modules.error_messages.random.choice') as mock_choice:
            mock_choice.return_value = "Test message"
            result = manager.get_user_message(ErrorCategory.NETWORK, severity=ErrorSeverity.HIGH)
            
            assert result == "🚨 Test message"
    
    def test_get_user_message_critical_severity(self):
        """Test get_user_message with critical severity."""
        manager = ErrorFeedbackManager()
        
        with patch('modules.error_messages.random.choice') as mock_choice:
            mock_choice.return_value = "Test message"
            result = manager.get_user_message(ErrorCategory.NETWORK, severity=ErrorSeverity.CRITICAL)
            
            assert result == "💥 CRITICAL: Test message"
    
    def test_get_user_message_unknown_category(self):
        """Test get_user_message with unknown category falls back to GENERAL."""
        manager = ErrorFeedbackManager()
        
        with patch('modules.error_messages.random.choice') as mock_choice:
            mock_choice.return_value = "General message"
            result = manager.get_user_message("UNKNOWN_CATEGORY")
            
            assert result == "General message"
    
    def test_get_technical_message_basic(self):
        """Test get_technical_message with basic parameters."""
        manager = ErrorFeedbackManager()
        
        result = manager.get_technical_message(ErrorCategory.NETWORK, "test_function")
        assert "Network operation failed" in result
        assert "test_function" in result
    
    def test_get_technical_message_with_details(self):
        """Test get_technical_message with additional details."""
        manager = ErrorFeedbackManager()
        
        result = manager.get_technical_message(
            ErrorCategory.API, 
            "test_function", 
            details="Connection timeout"
        )
        assert "External API call failed" in result
        assert "test_function" in result
        assert "Connection timeout" in result
    
    def test_get_technical_message_unknown_category(self):
        """Test get_technical_message with unknown category."""
        manager = ErrorFeedbackManager()
        
        result = manager.get_technical_message("UNKNOWN_CATEGORY", "test_function")
        assert "General operation failed" in result
    
    def test_get_admin_message_basic(self):
        """Test get_admin_message with basic parameters."""
        manager = ErrorFeedbackManager()
        
        result = manager.get_admin_message(ErrorCategory.DATABASE)
        assert "Database connectivity" in result
    
    def test_get_admin_message_with_context(self):
        """Test get_admin_message with context information."""
        manager = ErrorFeedbackManager()
        context = {"user_id": 123, "action": "save"}
        
        result = manager.get_admin_message(ErrorCategory.DATABASE, context)
        assert "Database connectivity" in result
        assert "user_id: 123" in result
        assert "action: save" in result
    
    def test_get_admin_message_unknown_category(self):
        """Test get_admin_message with unknown category."""
        manager = ErrorFeedbackManager()
        
        result = manager.get_admin_message("UNKNOWN_CATEGORY")
        assert "Unspecified system error" in result
    
    def test_get_error_sticker(self):
        """Test get_error_sticker returns a sticker from the list."""
        manager = ErrorFeedbackManager()
        
        with patch('modules.error_messages.random.choice') as mock_choice:
            mock_choice.return_value = "test_sticker_id"
            result = manager.get_error_sticker(ErrorCategory.NETWORK)
            
            assert result == "test_sticker_id"
            mock_choice.assert_called_once_with(manager.error_stickers)
    
    def test_format_error_for_telegram_basic(self):
        """Test format_error_for_telegram with basic parameters."""
        manager = ErrorFeedbackManager()
        
        with patch('modules.error_messages.random.choice') as mock_choice:
            mock_choice.return_value = "test_sticker"
            result = manager.format_error_for_telegram("Test error message")
            
            assert result["text"] == "Test error message"
            assert result["parse_mode"] == "Markdown"
            assert result["sticker"] == "test_sticker"
    
    def test_format_error_for_telegram_high_severity(self):
        """Test format_error_for_telegram with high severity."""
        manager = ErrorFeedbackManager()
        
        result = manager.format_error_for_telegram(
            "Test error message", 
            severity=ErrorSeverity.HIGH
        )
        
        assert result["text"] == "*Test error message*"
        assert result["parse_mode"] == "Markdown"
    
    def test_format_error_for_telegram_critical_severity(self):
        """Test format_error_for_telegram with critical severity."""
        manager = ErrorFeedbackManager()
        
        result = manager.format_error_for_telegram(
            "Test error message", 
            severity=ErrorSeverity.CRITICAL
        )
        
        assert result["text"] == "*⚠️ Test error message ⚠️*"
        assert result["parse_mode"] == "Markdown"
    
    def test_format_error_for_telegram_no_sticker(self):
        """Test format_error_for_telegram without sticker."""
        manager = ErrorFeedbackManager()
        
        result = manager.format_error_for_telegram(
            "Test error message", 
            include_sticker=False
        )
        
        assert result["text"] == "Test error message"
        assert result["parse_mode"] == "Markdown"
        assert "sticker" not in result


class TestErrorResponseBuilder:
    """Test ErrorResponseBuilder class."""
    
    def test_initialization(self):
        """Test ErrorResponseBuilder initialization."""
        builder = ErrorResponseBuilder()
        assert hasattr(builder, 'feedback_manager')
        assert hasattr(builder, 'response_templates')
        assert isinstance(builder.feedback_manager, ErrorFeedbackManager)
        assert isinstance(builder.response_templates, dict)
    
    def test_build_user_response_basic(self):
        """Test build_user_response with basic parameters."""
        builder = ErrorResponseBuilder()
        
        with patch.object(builder.feedback_manager, 'get_user_message') as mock_get_msg:
            with patch.object(builder.feedback_manager, 'format_error_for_telegram') as mock_format:
                mock_get_msg.return_value = "Test user message"
                mock_format.return_value = {"text": "Test user message", "parse_mode": "Markdown"}
                
                result = builder.build_user_response(ErrorCategory.NETWORK)
                
                assert result == {"text": "Test user message", "parse_mode": "Markdown"}
                mock_get_msg.assert_called_once_with(ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, None)
                mock_format.assert_called_once()
    
    def test_build_user_response_with_custom_message(self):
        """Test build_user_response with custom message."""
        builder = ErrorResponseBuilder()
        custom_msg = "Custom error message"
        
        with patch.object(builder.feedback_manager, 'get_user_message') as mock_get_msg:
            with patch.object(builder.feedback_manager, 'format_error_for_telegram') as mock_format:
                mock_get_msg.return_value = custom_msg
                mock_format.return_value = {"text": custom_msg, "parse_mode": "Markdown"}
                
                result = builder.build_user_response(
                    ErrorCategory.NETWORK, 
                    custom_message=custom_msg
                )
                
                mock_get_msg.assert_called_once_with(ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, custom_msg)
    
    def test_build_user_response_with_help(self):
        """Test build_user_response with help text."""
        builder = ErrorResponseBuilder()
        
        with patch.object(builder.feedback_manager, 'get_user_message') as mock_get_msg:
            with patch.object(builder.feedback_manager, 'format_error_for_telegram') as mock_format:
                with patch.object(builder, '_get_help_text') as mock_help:
                    mock_get_msg.return_value = "Test user message"
                    mock_help.return_value = "Help text"
                    mock_format.return_value = {"text": "Test user message\n\n💡 Help text", "parse_mode": "Markdown"}
                    
                    result = builder.build_user_response(ErrorCategory.INPUT, include_help=True)
                    
                    mock_help.assert_called_once_with(ErrorCategory.INPUT)
    
    def test_build_user_response_without_help(self):
        """Test build_user_response without help text."""
        builder = ErrorResponseBuilder()
        
        with patch.object(builder.feedback_manager, 'get_user_message') as mock_get_msg:
            with patch.object(builder.feedback_manager, 'format_error_for_telegram') as mock_format:
                mock_get_msg.return_value = "Test user message"
                mock_format.return_value = {"text": "Test user message", "parse_mode": "Markdown"}
                
                result = builder.build_user_response(ErrorCategory.NETWORK, include_help=False)
                
                # Should not call _get_help_text
                assert result == {"text": "Test user message", "parse_mode": "Markdown"}
    
    def test_build_admin_response_basic(self):
        """Test build_admin_response with basic parameters."""
        builder = ErrorResponseBuilder()
        
        with patch.object(builder.feedback_manager, 'get_admin_message') as mock_get_admin:
            mock_get_admin.return_value = "Admin error message"
            
            result = builder.build_admin_response(
                ErrorCategory.DATABASE, 
                "test_function"
            )
            
            assert "🔧 **Admin Error Report**" in result
            assert "**Function:** test_function" in result
            assert "**Category:** database" in result
            assert "**Message:** Admin error message" in result
            mock_get_admin.assert_called_once_with(ErrorCategory.DATABASE, None)
    
    def test_build_admin_response_with_context(self):
        """Test build_admin_response with context."""
        builder = ErrorResponseBuilder()
        context = {"user_id": 123, "action": "save"}
        
        with patch.object(builder.feedback_manager, 'get_admin_message') as mock_get_admin:
            mock_get_admin.return_value = "Admin error message"
            
            result = builder.build_admin_response(
                ErrorCategory.DATABASE, 
                "test_function",
                context=context
            )
            
            assert "**Context:** {'user_id': 123, 'action': 'save'}" in result
            mock_get_admin.assert_called_once_with(ErrorCategory.DATABASE, context)
    
    def test_build_admin_response_with_original_error(self):
        """Test build_admin_response with original error."""
        builder = ErrorResponseBuilder()
        original_error = "Connection timeout"
        
        with patch.object(builder.feedback_manager, 'get_admin_message') as mock_get_admin:
            mock_get_admin.return_value = "Admin error message"
            
            result = builder.build_admin_response(
                ErrorCategory.DATABASE, 
                "test_function",
                original_error=original_error
            )
            
            assert "**Original Error:** Connection timeout" in result
    
    def test_get_help_text_input_category(self):
        """Test _get_help_text for INPUT category."""
        builder = ErrorResponseBuilder()
        
        result = builder._get_help_text(ErrorCategory.INPUT)
        assert result == "Check the command format and try again."
    
    def test_get_help_text_permission_category(self):
        """Test _get_help_text for PERMISSION category."""
        builder = ErrorResponseBuilder()
        
        result = builder._get_help_text(ErrorCategory.PERMISSION)
        assert result == "Contact an admin if you need access."
    
    def test_get_help_text_network_category(self):
        """Test _get_help_text for NETWORK category."""
        builder = ErrorResponseBuilder()
        
        result = builder._get_help_text(ErrorCategory.NETWORK)
        assert result == "Check your internet connection."
    
    def test_get_help_text_unknown_category(self):
        """Test _get_help_text for unknown category."""
        builder = ErrorResponseBuilder()
        
        result = builder._get_help_text("UNKNOWN_CATEGORY")
        assert result is None


class TestGlobalInstances:
    """Test global instances."""
    
    def test_error_feedback_manager_global(self):
        """Test that global error_feedback_manager is properly initialized."""
        assert isinstance(error_feedback_manager, ErrorFeedbackManager)
    
    def test_error_response_builder_global(self):
        """Test that global error_response_builder is properly initialized."""
        assert isinstance(error_response_builder, ErrorResponseBuilder)


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_get_user_error_message(self):
        """Test get_user_error_message convenience function."""
        with patch.object(error_feedback_manager, 'get_user_message') as mock_get_msg:
            mock_get_msg.return_value = "Test message"
            
            result = get_user_error_message(ErrorCategory.NETWORK)
            
            assert result == "Test message"
            mock_get_msg.assert_called_once_with(ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, None)
    
    def test_get_user_error_message_with_custom_message(self):
        """Test get_user_error_message with custom message."""
        custom_msg = "Custom error"
        
        with patch.object(error_feedback_manager, 'get_user_message') as mock_get_msg:
            mock_get_msg.return_value = custom_msg
            
            result = get_user_error_message(ErrorCategory.NETWORK, custom_message=custom_msg)
            
            mock_get_msg.assert_called_once_with(ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, custom_msg)
    
    def test_get_error_response(self):
        """Test get_error_response convenience function."""
        with patch.object(error_response_builder, 'build_user_response') as mock_build:
            mock_build.return_value = {"text": "Test response", "parse_mode": "Markdown"}
            
            result = get_error_response(ErrorCategory.NETWORK)
            
            assert result == {"text": "Test response", "parse_mode": "Markdown"}
            mock_build.assert_called_once_with(ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, None, True)
    
    def test_get_error_response_with_parameters(self):
        """Test get_error_response with all parameters."""
        custom_msg = "Custom error"
        
        with patch.object(error_response_builder, 'build_user_response') as mock_build:
            mock_build.return_value = {"text": "Test response", "parse_mode": "Markdown"}
            
            result = get_error_response(
                ErrorCategory.NETWORK, 
                ErrorSeverity.HIGH, 
                custom_msg, 
                False
            )
            
            mock_build.assert_called_once_with(ErrorCategory.NETWORK, ErrorSeverity.HIGH, custom_msg, False)
    
    def test_get_admin_error_report(self):
        """Test get_admin_error_report convenience function."""
        with patch.object(error_response_builder, 'build_admin_response') as mock_build:
            mock_build.return_value = "Admin report"
            
            result = get_admin_error_report(ErrorCategory.DATABASE, "test_function")
            
            assert result == "Admin report"
            mock_build.assert_called_once_with(ErrorCategory.DATABASE, "test_function", None, None)
    
    def test_get_admin_error_report_with_context_and_error(self):
        """Test get_admin_error_report with context and original error."""
        context = {"user_id": 123}
        original_error = "Connection failed"
        
        with patch.object(error_response_builder, 'build_admin_response') as mock_build:
            mock_build.return_value = "Admin report"
            
            result = get_admin_error_report(
                ErrorCategory.DATABASE, 
                "test_function", 
                context, 
                original_error
            )
            
            mock_build.assert_called_once_with(ErrorCategory.DATABASE, "test_function", context, original_error)


class TestErrorMessagesIntegration:
    """Integration tests for error messages."""
    
    def test_full_error_flow(self):
        """Test complete error message flow from category to user response."""
        # Test that we can get a user-friendly message for each category
        categories = [
            ErrorCategory.NETWORK,
            ErrorCategory.API,
            ErrorCategory.DATABASE,
            ErrorCategory.PARSING,
            ErrorCategory.INPUT,
            ErrorCategory.PERMISSION,
            ErrorCategory.RESOURCE,
            ErrorCategory.GENERAL
        ]
        
        for category in categories:
            # Test user message
            user_msg = get_user_error_message(category)
            assert isinstance(user_msg, str)
            assert len(user_msg) > 0
            
            # Test error response
            response = get_error_response(category)
            assert isinstance(response, dict)
            assert "text" in response
            assert "parse_mode" in response
            
            # Test admin report
            admin_report = get_admin_error_report(category, "test_function")
            assert isinstance(admin_report, str)
            assert len(admin_report) > 0
    
    def test_error_message_consistency(self):
        """Test that error messages are consistent across different access methods."""
        category = ErrorCategory.NETWORK
        
        # Test that both methods return valid messages
        msg1 = get_user_error_message(category)
        msg2 = error_feedback_manager.get_user_message(category)
        
        # Both should be valid error messages
        assert isinstance(msg1, str)
        assert isinstance(msg2, str)
        assert len(msg1) > 0
        assert len(msg2) > 0
        
        # Both should contain network-related content
        assert any(word in msg1.lower() for word in ['network', 'connection', 'service'])
        assert any(word in msg2.lower() for word in ['network', 'connection', 'service'])
    
    def test_error_response_structure(self):
        """Test that error responses have the correct structure."""
        response = get_error_response(ErrorCategory.INPUT)
        
        assert isinstance(response, dict)
        assert "text" in response
        assert "parse_mode" in response
        assert response["parse_mode"] == "Markdown"
        assert "sticker" in response  # Should include sticker by default
    
    def test_admin_report_structure(self):
        """Test that admin reports have the correct structure."""
        report = get_admin_error_report(ErrorCategory.DATABASE, "test_function")
        
        assert isinstance(report, str)
        assert "🔧 **Admin Error Report**" in report
        assert "**Function:** test_function" in report
        assert "**Category:** database" in report
        assert "**Message:**" in report 