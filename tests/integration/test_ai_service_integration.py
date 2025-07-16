"""
Integration tests for AI service integration and response handling.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
import openai
import httpx

from modules.gpt import GPTService, AIResponse, ConversationContext
from modules.error_handler import StandardError


class TestGPTServiceIntegration:
    """Integration tests for GPT service."""
    
    @pytest.fixture
    def gpt_service(self):
        """Create a GPTService instance."""
        return GPTService(api_key="test_api_key")
    
    @pytest.mark.asyncio
    async def test_simple_text_generation(self, gpt_service):
        """Test simple text generation with OpenAI API."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "This is a test response from GPT."
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 25
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 15
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_response(
                prompt="Hello, how are you?",
                max_tokens=100,
                temperature=0.7
            )
            
            assert isinstance(response, AIResponse)
            assert response.content == "This is a test response from GPT."
            assert response.tokens_used == 25
            assert response.success is True
    
    @pytest.mark.asyncio
    async def test_conversation_context_handling(self, gpt_service):
        """Test conversation context management."""
        # Mock conversation history
        context = ConversationContext(
            messages=[
                {"role": "user", "content": "What is Python?"},
                {"role": "assistant", "content": "Python is a programming language."},
                {"role": "user", "content": "Tell me more about it."}
            ],
            max_history=10
        )
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Python is versatile and easy to learn."
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 50
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_response_with_context(
                context=context,
                new_message="Tell me more about it.",
                max_tokens=150
            )
            
            assert response.success is True
            assert response.content == "Python is versatile and easy to learn."
            
            # Verify that context was passed correctly
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]['messages']
            assert len(messages) == 4  # 3 from context + 1 new
            assert messages[-1]['content'] == "Tell me more about it."
    
    @pytest.mark.asyncio
    async def test_system_prompt_integration(self, gpt_service):
        """Test system prompt integration."""
        system_prompt = "You are a helpful coding assistant. Always provide code examples."
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Here's a Python example:\n```python\nprint('Hello, World!')\n```"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 30
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_response(
                prompt="Show me a hello world example",
                system_prompt=system_prompt,
                max_tokens=100
            )
            
            assert response.success is True
            assert "python" in response.content.lower()
            assert "print" in response.content
            
            # Verify system prompt was included
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]['messages']
            assert messages[0]['role'] == 'system'
            assert messages[0]['content'] == system_prompt
    
    @pytest.mark.asyncio
    async def test_different_model_variants(self, gpt_service):
        """Test different GPT model variants."""
        models_to_test = [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "gpt-4o-mini"
        ]
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Model-specific response"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 20
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            for model in models_to_test:
                response = await gpt_service.generate_response(
                    prompt="Test prompt",
                    model=model,
                    max_tokens=50
                )
                
                assert response.success is True
                assert response.model == model
                
                # Verify correct model was used in API call
                call_args = mock_client.chat.completions.create.call_args
                assert call_args[1]['model'] == model
    
    @pytest.mark.asyncio
    async def test_temperature_and_creativity_settings(self, gpt_service):
        """Test different temperature and creativity settings."""
        test_cases = [
            {"temperature": 0.0, "description": "deterministic"},
            {"temperature": 0.5, "description": "balanced"},
            {"temperature": 1.0, "description": "creative"},
            {"temperature": 1.5, "description": "very creative"}
        ]
        
        for case in test_cases:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message = Mock()
            mock_response.choices[0].message.content = f"Response with {case['description']} setting"
            mock_response.usage = Mock()
            mock_response.usage.total_tokens = 25
            
            with patch('openai.AsyncOpenAI') as mock_openai:
                mock_client = Mock()
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client
                
                response = await gpt_service.generate_response(
                    prompt="Write a creative story",
                    temperature=case["temperature"],
                    max_tokens=100
                )
                
                assert response.success is True
                assert case["description"] in response.content
                
                # Verify temperature was set correctly
                call_args = mock_client.chat.completions.create.call_args
                assert call_args[1]['temperature'] == case["temperature"]
    
    @pytest.mark.asyncio
    async def test_token_limit_handling(self, gpt_service):
        """Test handling of token limits."""
        # Test with different max_tokens settings
        token_limits = [10, 50, 100, 500, 1000]
        
        for limit in token_limits:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message = Mock()
            mock_response.choices[0].message.content = "A" * min(limit, 100)  # Simulate response length
            mock_response.usage = Mock()
            mock_response.usage.total_tokens = limit
            mock_response.usage.completion_tokens = min(limit - 10, limit)
            
            with patch('openai.AsyncOpenAI') as mock_openai:
                mock_client = Mock()
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client
                
                response = await gpt_service.generate_response(
                    prompt="Generate text",
                    max_tokens=limit
                )
                
                assert response.success is True
                assert response.tokens_used <= limit
                
                # Verify max_tokens was set correctly
                call_args = mock_client.chat.completions.create.call_args
                assert call_args[1]['max_tokens'] == limit
    
    @pytest.mark.asyncio
    async def test_streaming_response_handling(self, gpt_service):
        """Test streaming response handling."""
        # Mock streaming response
        async def mock_stream():
            chunks = [
                {"choices": [{"delta": {"content": "Hello"}}]},
                {"choices": [{"delta": {"content": " there"}}]},
                {"choices": [{"delta": {"content": "!"}}]},
                {"choices": [{"delta": {}}]}  # End of stream
            ]
            for chunk in chunks:
                yield Mock(**chunk)
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_streaming_response(
                prompt="Say hello",
                max_tokens=50
            )
            
            # Collect streamed content
            full_content = ""
            async for chunk in response:
                if chunk.content:
                    full_content += chunk.content
            
            assert full_content == "Hello there!"
    
    @pytest.mark.asyncio
    async def test_function_calling_integration(self, gpt_service):
        """Test function calling capabilities."""
        # Define a test function
        test_functions = [
            {
                "name": "get_weather",
                "description": "Get weather information for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA"
                        }
                    },
                    "required": ["location"]
                }
            }
        ]
        
        # Mock function call response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.function_call = Mock()
        mock_response.choices[0].message.function_call.name = "get_weather"
        mock_response.choices[0].message.function_call.arguments = '{"location": "New York, NY"}'
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 40
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_response_with_functions(
                prompt="What's the weather like in New York?",
                functions=test_functions,
                max_tokens=100
            )
            
            assert response.success is True
            assert response.function_call is not None
            assert response.function_call["name"] == "get_weather"
            assert "New York" in response.function_call["arguments"]


class TestAIServiceErrorHandling:
    """Test error handling in AI service integration."""
    
    @pytest.fixture
    def gpt_service(self):
        """Create a GPTService instance."""
        return GPTService(api_key="test_api_key")
    
    @pytest.mark.asyncio
    async def test_api_key_error_handling(self, gpt_service):
        """Test handling of API key errors."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=openai.AuthenticationError("Invalid API key")
            )
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_response(
                prompt="Test prompt",
                max_tokens=50
            )
            
            assert response.success is False
            assert "authentication" in response.error.lower() or "api key" in response.error.lower()
    
    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, gpt_service):
        """Test handling of rate limit errors."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=openai.RateLimitError("Rate limit exceeded")
            )
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_response(
                prompt="Test prompt",
                max_tokens=50
            )
            
            assert response.success is False
            assert "rate limit" in response.error.lower()
    
    @pytest.mark.asyncio
    async def test_quota_exceeded_error_handling(self, gpt_service):
        """Test handling of quota exceeded errors."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=openai.APIError("Quota exceeded")
            )
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_response(
                prompt="Test prompt",
                max_tokens=50
            )
            
            assert response.success is False
            assert "quota" in response.error.lower() or "limit" in response.error.lower()
    
    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, gpt_service):
        """Test handling of network timeouts."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=asyncio.TimeoutError("Request timeout")
            )
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_response(
                prompt="Test prompt",
                max_tokens=50,
                timeout=5.0
            )
            
            assert response.success is False
            assert "timeout" in response.error.lower()
    
    @pytest.mark.asyncio
    async def test_content_filter_error_handling(self, gpt_service):
        """Test handling of content filter errors."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=openai.APIError("Content filtered")
            )
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_response(
                prompt="Inappropriate content",
                max_tokens=50
            )
            
            assert response.success is False
            assert "content" in response.error.lower() or "filter" in response.error.lower()
    
    @pytest.mark.asyncio
    async def test_malformed_response_handling(self, gpt_service):
        """Test handling of malformed API responses."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            # Mock malformed response
            mock_response = Mock()
            mock_response.choices = []  # Empty choices
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_response(
                prompt="Test prompt",
                max_tokens=50
            )
            
            assert response.success is False
            assert "response" in response.error.lower() or "format" in response.error.lower()
    
    @pytest.mark.asyncio
    async def test_service_unavailable_handling(self, gpt_service):
        """Test handling of service unavailable errors."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Service unavailable", 
                    request=Mock(), 
                    response=Mock(status_code=503)
                )
            )
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_response(
                prompt="Test prompt",
                max_tokens=50
            )
            
            assert response.success is False
            assert "service" in response.error.lower() or "unavailable" in response.error.lower()


class TestAIServicePerformance:
    """Performance tests for AI service integration."""
    
    @pytest.fixture
    def gpt_service(self):
        """Create a GPTService instance."""
        return GPTService(api_key="test_api_key")
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(self, gpt_service):
        """Test handling of concurrent AI requests."""
        async def mock_api_call(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate API latency
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message = Mock()
            mock_response.choices[0].message.content = f"Response {asyncio.current_task().get_name()}"
            mock_response.usage = Mock()
            mock_response.usage.total_tokens = 20
            return mock_response
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_api_call)
            mock_openai.return_value = mock_client
            
            # Create multiple concurrent requests
            tasks = []
            for i in range(5):
                task = asyncio.create_task(
                    gpt_service.generate_response(
                        prompt=f"Request {i}",
                        max_tokens=50
                    ),
                    name=f"request_{i}"
                )
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks)
            
            assert len(responses) == 5
            assert all(response.success for response in responses)
            assert all("Response" in response.content for response in responses)
    
    @pytest.mark.asyncio
    async def test_response_time_measurement(self, gpt_service):
        """Test response time measurement."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            
            async def delayed_response(*args, **kwargs):
                await asyncio.sleep(0.2)  # Simulate 200ms API response time
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message = Mock()
                mock_response.choices[0].message.content = "Delayed response"
                mock_response.usage = Mock()
                mock_response.usage.total_tokens = 15
                return mock_response
            
            mock_client.chat.completions.create = AsyncMock(side_effect=delayed_response)
            mock_openai.return_value = mock_client
            
            start_time = asyncio.get_event_loop().time()
            response = await gpt_service.generate_response(
                prompt="Test prompt",
                max_tokens=50
            )
            end_time = asyncio.get_event_loop().time()
            
            response_time = end_time - start_time
            
            assert response.success is True
            assert response_time >= 0.2  # Should take at least 200ms
            assert response.response_time is not None
            assert response.response_time >= 0.2
    
    @pytest.mark.asyncio
    async def test_large_context_handling(self, gpt_service):
        """Test handling of large context windows."""
        # Create a large conversation context
        large_context = ConversationContext(
            messages=[
                {"role": "user", "content": f"Message {i}: " + "A" * 100}
                for i in range(50)  # 50 messages with 100 chars each
            ],
            max_history=100
        )
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Response to large context"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 2000  # Large token count
        mock_response.usage.prompt_tokens = 1800
        mock_response.usage.completion_tokens = 200
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            response = await gpt_service.generate_response_with_context(
                context=large_context,
                new_message="Summarize our conversation",
                max_tokens=500
            )
            
            assert response.success is True
            assert response.tokens_used == 2000
            assert response.content == "Response to large context"
    
    @pytest.mark.asyncio
    async def test_memory_usage_optimization(self, gpt_service):
        """Test memory usage optimization for large responses."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Mock a large response
        large_content = "A" * 10000  # 10KB response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = large_content
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 3000
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            # Generate multiple large responses
            responses = []
            for i in range(10):
                response = await gpt_service.generate_response(
                    prompt=f"Generate large content {i}",
                    max_tokens=1000
                )
                responses.append(response)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB for 10 responses)
        assert memory_increase < 50 * 1024 * 1024  # 50MB
        
        # Verify all responses were successful
        assert all(response.success for response in responses)
        assert all(len(response.content) == 10000 for response in responses)


class TestAIServiceCaching:
    """Test caching mechanisms in AI service integration."""
    
    @pytest.fixture
    def gpt_service_with_cache(self):
        """Create a GPTService instance with caching enabled."""
        return GPTService(api_key="test_api_key", enable_cache=True)
    
    @pytest.mark.asyncio
    async def test_response_caching(self, gpt_service_with_cache):
        """Test response caching functionality."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Cached response"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 25
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            # First request
            response1 = await gpt_service_with_cache.generate_response(
                prompt="What is Python?",
                max_tokens=100,
                temperature=0.0  # Deterministic for caching
            )
            
            # Second identical request (should be cached)
            response2 = await gpt_service_with_cache.generate_response(
                prompt="What is Python?",
                max_tokens=100,
                temperature=0.0
            )
            
            assert response1.success is True
            assert response2.success is True
            assert response1.content == response2.content
            
            # API should only be called once due to caching
            assert mock_client.chat.completions.create.call_count == 1
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self, gpt_service_with_cache):
        """Test cache invalidation with different parameters."""
        mock_response1 = Mock()
        mock_response1.choices = [Mock()]
        mock_response1.choices[0].message = Mock()
        mock_response1.choices[0].message.content = "Response with temp 0.0"
        mock_response1.usage = Mock()
        mock_response1.usage.total_tokens = 25
        
        mock_response2 = Mock()
        mock_response2.choices = [Mock()]
        mock_response2.choices[0].message = Mock()
        mock_response2.choices[0].message.content = "Response with temp 0.5"
        mock_response2.usage = Mock()
        mock_response2.usage.total_tokens = 25
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_response1, mock_response2]
            )
            mock_openai.return_value = mock_client
            
            # Same prompt, different temperature (should not use cache)
            response1 = await gpt_service_with_cache.generate_response(
                prompt="Tell me a joke",
                max_tokens=100,
                temperature=0.0
            )
            
            response2 = await gpt_service_with_cache.generate_response(
                prompt="Tell me a joke",
                max_tokens=100,
                temperature=0.5
            )
            
            assert response1.content != response2.content
            assert mock_client.chat.completions.create.call_count == 2