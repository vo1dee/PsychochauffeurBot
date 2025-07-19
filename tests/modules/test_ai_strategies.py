import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock
from modules.ai_strategies import (
    DirectResponseStrategy, RandomResponseStrategy, ContextualResponseStrategy, AnalyticalResponseStrategy,
    AIResponseStrategyManager, AIService, AIContext, AIResponse, ResponseType
)

@pytest.fixture
def gpt_service():
    svc = Mock()
    svc.generate_response = AsyncMock(return_value="Test response")
    return svc

@pytest.fixture
def ai_context():
    return AIContext(
        user_id=1,
        chat_id=2,
        message_text="Hello world",
        response_type=ResponseType.DIRECT,
        chat_history=[],
        user_preferences={},
        chat_settings={}
    )

@pytest.mark.asyncio
async def test_direct_response_strategy(gpt_service, ai_context):
    strategy = DirectResponseStrategy(gpt_service)
    ai_context.response_type = ResponseType.DIRECT
    response = await strategy.generate_response(ai_context)
    assert isinstance(response, AIResponse)
    assert response.response_type == ResponseType.DIRECT
    assert response.text == "Test response"
    assert strategy.is_applicable(ai_context)
    assert strategy.get_strategy_name() == "direct_response"

@pytest.mark.asyncio
async def test_random_response_strategy(gpt_service, ai_context):
    strategy = RandomResponseStrategy(gpt_service)
    ai_context.response_type = ResponseType.RANDOM
    response = await strategy.generate_response(ai_context)
    assert isinstance(response, AIResponse)
    assert response.response_type == ResponseType.RANDOM
    assert response.text == "Test response"
    assert strategy.is_applicable(ai_context)
    assert strategy.get_strategy_name() == "random_response"

@pytest.mark.asyncio
async def test_contextual_response_strategy(gpt_service, ai_context):
    strategy = ContextualResponseStrategy(gpt_service)
    ai_context.response_type = ResponseType.CONTEXTUAL
    ai_context.chat_history = [{"text": "Hi"}, {"text": "How are you?"}]
    response = await strategy.generate_response(ai_context)
    assert isinstance(response, AIResponse)
    assert response.response_type == ResponseType.CONTEXTUAL
    assert response.text == "Test response"
    assert strategy.is_applicable(ai_context)
    assert strategy.get_strategy_name() == "contextual_response"

@pytest.mark.asyncio
async def test_analytical_response_strategy(gpt_service, ai_context):
    strategy = AnalyticalResponseStrategy(gpt_service)
    ai_context.response_type = ResponseType.ANALYTICAL
    response = await strategy.generate_response(ai_context)
    assert isinstance(response, AIResponse)
    assert response.response_type == ResponseType.ANALYTICAL
    assert response.text == "Test response"
    assert strategy.is_applicable(ai_context)
    assert strategy.get_strategy_name() == "analytical_response"

@pytest.mark.asyncio
async def test_strategy_manager_selects_applicable(gpt_service, ai_context):
    manager = AIResponseStrategyManager()
    direct = DirectResponseStrategy(gpt_service)
    random = RandomResponseStrategy(gpt_service)
    manager.register_strategy(direct)
    manager.register_strategy(random)
    ai_context.response_type = ResponseType.RANDOM
    response = await manager.generate_response(ai_context)
    assert response.response_type == ResponseType.RANDOM
    # Test fallback to default
    manager.set_default_strategy(direct)
    ai_context.response_type = ResponseType.CASUAL  # No applicable
    response = await manager.generate_response(ai_context)
    assert response.response_type == ResponseType.DIRECT

@pytest.mark.asyncio
async def test_strategy_manager_no_strategy_raises(gpt_service, ai_context):
    manager = AIResponseStrategyManager()
    with pytest.raises(ValueError):
        await manager.generate_response(ai_context)

@pytest.mark.asyncio
async def test_ai_service_integration(gpt_service, ai_context):
    # Mock service registry and chat_history_manager/config_manager
    chat_history_manager = Mock()
    chat_history_manager.get_recent_messages = Mock(return_value=[{"text": "Hi"}])
    config_manager = AsyncMock()
    config_manager.get_config = AsyncMock(return_value={})
    service_registry = Mock()
    service_registry.get_service = Mock(side_effect=lambda name: {
        "chat_history_manager": chat_history_manager,
        "config_manager": config_manager
    }[name])
    # Setup strategy manager
    manager = AIResponseStrategyManager()
    direct = DirectResponseStrategy(gpt_service)
    manager.register_strategy(direct)
    manager.set_default_strategy(direct)
    # Setup AIService
    ai_service = AIService(manager, service_registry)
    # Mock Telegram Update and Context
    update = Mock()
    update.effective_user.id = 1
    update.effective_chat.id = 2
    update.effective_chat.type = "supergroup"
    update.message.text = "Hello world"
    context = Mock()
    # Should use direct strategy
    response = await ai_service.generate_response(update, context, ResponseType.DIRECT)
    assert isinstance(response, AIResponse)
    assert response.response_type == ResponseType.DIRECT
    assert response.text == "Test response" 