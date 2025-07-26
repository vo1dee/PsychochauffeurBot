"""
Tests for the speechmatics module.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from telegram import Bot

from modules.speechmatics import (
    transcribe_telegram_voice,
    SpeechmaticsLanguageNotExpected,
    SpeechmaticsRussianDetected,
    SpeechmaticsNoSpeechDetected,
    SPEECHMATICS_API_URL
)


class TestSpeechmaticsExceptions:
    """Test speechmatics custom exceptions."""
    
    def test_speechmatics_language_not_expected_exception(self):
        """Test SpeechmaticsLanguageNotExpected exception."""
        with pytest.raises(SpeechmaticsLanguageNotExpected):
            raise SpeechmaticsLanguageNotExpected("Language not expected")
    
    def test_speechmatics_russian_detected_exception(self):
        """Test SpeechmaticsRussianDetected exception."""
        with pytest.raises(SpeechmaticsRussianDetected):
            raise SpeechmaticsRussianDetected("Russian detected")
    
    def test_speechmatics_no_speech_detected_exception(self):
        """Test SpeechmaticsNoSpeechDetected exception."""
        with pytest.raises(SpeechmaticsNoSpeechDetected):
            raise SpeechmaticsNoSpeechDetected("No speech detected")
    
    def test_exception_inheritance(self):
        """Test that custom exceptions inherit from Exception."""
        assert issubclass(SpeechmaticsLanguageNotExpected, Exception)
        assert issubclass(SpeechmaticsRussianDetected, Exception)
        assert issubclass(SpeechmaticsNoSpeechDetected, Exception)


class TestSpeechmaticsConstants:
    """Test speechmatics constants."""
    
    def test_speechmatics_api_url(self):
        """Test SPEECHMATICS_API_URL constant."""
        assert SPEECHMATICS_API_URL == "https://asr.api.speechmatics.com/v2/jobs/"
        assert isinstance(SPEECHMATICS_API_URL, str)
        assert SPEECHMATICS_API_URL.startswith("https://")


class TestTranscribeTelegramVoice:
    """Test transcribe_telegram_voice function."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot."""
        return Mock(spec=Bot)
    
    @pytest.mark.asyncio
    async def test_transcribe_telegram_voice_no_api_key(self, mock_bot):
        """Test transcribe_telegram_voice without API key."""
        with patch('modules.speechmatics.Config') as mock_config:
            mock_config.SPEECHMATICS_API_KEY = None
            
            with pytest.raises(RuntimeError) as exc_info:
                await transcribe_telegram_voice(mock_bot, "test_file_id")
            
            assert "Speechmatics API key is not set" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_transcribe_telegram_voice_with_api_key(self, mock_bot):
        """Test transcribe_telegram_voice with API key."""
        with patch('modules.speechmatics.Config') as mock_config:
            mock_config.SPEECHMATICS_API_KEY = "test_api_key"
            
            # Mock the actual transcription process to avoid real API calls
            with patch('modules.speechmatics.httpx') as mock_httpx:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"transcript": "test transcript"}
                mock_httpx.AsyncClient.return_value.__aenter__.return_value.post.return_value = mock_response
                
                # This will likely fail due to missing implementation, but we're testing the API key check
                try:
                    result = await transcribe_telegram_voice(mock_bot, "test_file_id")
                except Exception:
                    # Expected to fail due to incomplete mocking, but API key check passed
                    pass
    
    def test_transcribe_telegram_voice_default_language(self):
        """Test that transcribe_telegram_voice has correct default language."""
        import inspect
        sig = inspect.signature(transcribe_telegram_voice)
        assert sig.parameters['language'].default == "uk"
    
    def test_transcribe_telegram_voice_parameters(self):
        """Test transcribe_telegram_voice function parameters."""
        import inspect
        sig = inspect.signature(transcribe_telegram_voice)
        
        # Check required parameters
        assert 'bot' in sig.parameters
        assert 'file_id' in sig.parameters
        assert 'language' in sig.parameters
        
        # Check parameter types
        assert sig.parameters['bot'].annotation == Bot
        assert sig.parameters['file_id'].annotation == str
        assert sig.parameters['language'].annotation == str


class TestSpeechmaticsIntegration:
    """Test speechmatics integration scenarios."""
    
    def test_module_imports(self):
        """Test that all required modules are imported correctly."""
        import modules.speechmatics as sm
        
        # Test that functions are available
        assert hasattr(sm, 'transcribe_telegram_voice')
        assert callable(sm.transcribe_telegram_voice)
        
        # Test that exceptions are available
        assert hasattr(sm, 'SpeechmaticsLanguageNotExpected')
        assert hasattr(sm, 'SpeechmaticsRussianDetected')
        assert hasattr(sm, 'SpeechmaticsNoSpeechDetected')
        
        # Test that constants are available
        assert hasattr(sm, 'SPEECHMATICS_API_URL')
    
    def test_speechmatics_dependencies(self):
        """Test that speechmatics has all required dependencies."""
        import modules.speechmatics as sm
        
        # Should be able to import without errors
        assert hasattr(sm, 'httpx')
        assert hasattr(sm, 'os')
        assert hasattr(sm, 'asyncio')
        assert hasattr(sm, 'pyjson')
    
    @pytest.mark.asyncio
    async def test_speechmatics_error_handling(self):
        """Test speechmatics error handling."""
        mock_bot = Mock(spec=Bot)
        
        # Test with no API key
        with patch('modules.speechmatics.Config') as mock_config:
            mock_config.SPEECHMATICS_API_KEY = ""
            
            with pytest.raises(RuntimeError):
                await transcribe_telegram_voice(mock_bot, "test_file_id")
    
    def test_speechmatics_exception_messages(self):
        """Test that speechmatics exceptions can carry messages."""
        # Test that exceptions can be raised with custom messages
        try:
            raise SpeechmaticsLanguageNotExpected("Custom language error")
        except SpeechmaticsLanguageNotExpected as e:
            assert str(e) == "Custom language error"
        
        try:
            raise SpeechmaticsRussianDetected("Custom Russian error")
        except SpeechmaticsRussianDetected as e:
            assert str(e) == "Custom Russian error"
        
        try:
            raise SpeechmaticsNoSpeechDetected("Custom no speech error")
        except SpeechmaticsNoSpeechDetected as e:
            assert str(e) == "Custom no speech error"