"""
Basic integration tests for SpeechRecognitionService.

This module contains simplified integration tests that verify the core
functionality of the SpeechRecognitionService works with real dependencies.
"""

import pytest
from unittest.mock import Mock, AsyncMock

from modules.speech_recognition_service import SpeechRecognitionService
from config.config_manager import ConfigManager


@pytest.fixture
async def config_manager():
    """Create a real ConfigManager instance for integration testing."""
    config_manager = ConfigManager()
    await config_manager.initialize()
    return config_manager


@pytest.fixture
async def speech_service(config_manager):
    """Create a SpeechRecognitionService with real ConfigManager."""
    service = SpeechRecognitionService(config_manager=config_manager)
    await service.initialize()
    return service


class TestSpeechRecognitionServiceBasicIntegration:
    """Basic integration tests for SpeechRecognitionService."""
    
    @pytest.mark.asyncio
    async def test_service_initialization_with_real_config(self, config_manager):
        """Test service initialization with real ConfigManager."""
        service = SpeechRecognitionService(config_manager=config_manager)
        
        # Test initialization
        await service.initialize()
        assert service.config_manager is config_manager
        assert isinstance(service.file_id_hash_map, dict)
        
        # Test shutdown
        await service.shutdown()
        assert len(service.file_id_hash_map) == 0
        
    @pytest.mark.asyncio
    async def test_speech_configuration_management(self, speech_service):
        """Test speech configuration management with real config."""
        chat_id = "test_chat_12345"
        chat_type = "group"
        
        # Test initial state (should be disabled)
        is_enabled = await speech_service.is_speech_enabled(chat_id, chat_type)
        assert is_enabled is False
        
        # Enable speech recognition
        await speech_service.toggle_speech_recognition(chat_id, chat_type, True)
        
        # Verify it's enabled
        is_enabled = await speech_service.is_speech_enabled(chat_id, chat_type)
        assert is_enabled is True
        
        # Get config and verify structure
        config = await speech_service.get_speech_config(chat_id, chat_type)
        assert config is not None
        assert config.get("enabled") is True
        assert "overrides" in config
        
        # Disable speech recognition
        await speech_service.toggle_speech_recognition(chat_id, chat_type, False)
        
        # Verify it's disabled
        is_enabled = await speech_service.is_speech_enabled(chat_id, chat_type)
        assert is_enabled is False
        
    @pytest.mark.asyncio
    async def test_callback_data_validation(self, speech_service):
        """Test callback data validation functionality."""
        # Test valid speechrec callback
        file_hash = "valid_hash_123"
        speech_service.file_id_hash_map[file_hash] = "file_id"
        
        is_valid, error = speech_service.validate_callback_data(f"speechrec_{file_hash}")
        assert is_valid is True
        assert error is None
        
        # Test valid language callback
        is_valid, error = speech_service.validate_callback_data(f"lang_en|{file_hash}")
        assert is_valid is True
        assert error is None
        
        # Test expired callback
        is_valid, error = speech_service.validate_callback_data("speechrec_expired_hash")
        assert is_valid is False
        assert error == "Speech recognition button has expired"
        
        # Test invalid format
        is_valid, error = speech_service.validate_callback_data("invalid_format")
        assert is_valid is False
        assert error == "Invalid callback data format"
        
    @pytest.mark.asyncio
    async def test_file_hash_mapping(self, speech_service):
        """Test file hash mapping functionality."""
        # Test adding mappings
        file_id = "test_file_123"
        import hashlib
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        
        speech_service.file_id_hash_map[file_hash] = file_id
        assert speech_service.file_id_hash_map[file_hash] == file_id
        
        # Test validation with mapping
        is_valid, error = speech_service.validate_callback_data(f"speechrec_{file_hash}")
        assert is_valid is True
        assert error is None
        
        # Test cleanup
        await speech_service.shutdown()
        assert len(speech_service.file_id_hash_map) == 0
        
    @pytest.mark.asyncio
    async def test_configuration_persistence(self, config_manager):
        """Test that configuration changes persist across service instances."""
        chat_id = "persistence_test_chat"
        chat_type = "group"
        
        # Create first service instance
        service1 = SpeechRecognitionService(config_manager=config_manager)
        await service1.initialize()
        
        # Initially disabled
        assert await service1.is_speech_enabled(chat_id, chat_type) is False
        
        # Enable speech recognition
        await service1.toggle_speech_recognition(chat_id, chat_type, True)
        assert await service1.is_speech_enabled(chat_id, chat_type) is True
        
        await service1.shutdown()
        
        # Create second service instance with same config manager
        service2 = SpeechRecognitionService(config_manager=config_manager)
        await service2.initialize()
        
        # Verify configuration persisted
        assert await service2.is_speech_enabled(chat_id, chat_type) is True
        
        await service2.shutdown()
        
    @pytest.mark.asyncio
    async def test_multiple_chat_configurations(self, speech_service):
        """Test managing configurations for multiple chats."""
        chat_configs = [
            ("chat_1", "group"),
            ("chat_2", "private"),
            ("chat_3", "supergroup")
        ]
        
        # Enable speech for all chats
        for chat_id, chat_type in chat_configs:
            await speech_service.toggle_speech_recognition(chat_id, chat_type, True)
            assert await speech_service.is_speech_enabled(chat_id, chat_type) is True
        
        # Disable speech for middle chat
        await speech_service.toggle_speech_recognition("chat_2", "private", False)
        
        # Verify states
        assert await speech_service.is_speech_enabled("chat_1", "group") is True
        assert await speech_service.is_speech_enabled("chat_2", "private") is False
        assert await speech_service.is_speech_enabled("chat_3", "supergroup") is True
        
    @pytest.mark.asyncio
    async def test_error_handling_with_real_config(self, speech_service):
        """Test error handling scenarios with real configuration."""
        # Test with non-existent chat
        config = await speech_service.get_speech_config("non_existent_chat", "group")
        assert config is None
        
        is_enabled = await speech_service.is_speech_enabled("non_existent_chat", "group")
        assert is_enabled is False
        
        # Test enabling for non-existent chat (should create config)
        await speech_service.toggle_speech_recognition("non_existent_chat", "group", True)
        is_enabled = await speech_service.is_speech_enabled("non_existent_chat", "group")
        assert is_enabled is True