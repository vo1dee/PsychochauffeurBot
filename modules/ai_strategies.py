"""
AI Response Strategies using Strategy Pattern

This module implements different strategies for AI responses based on context,
user preferences, and chat settings.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable

from telegram import Update, Chat, User, Message
from telegram.ext import CallbackContext

logger = logging.getLogger(__name__)


class ResponseType(Enum):
    """Types of AI responses."""
    DIRECT = "direct"
    RANDOM = "random"
    CONTEXTUAL = "contextual"
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    HELPFUL = "helpful"
    CASUAL = "casual"
    FORMAL = "formal"


@dataclass
class AIContext:
    """Context for AI response generation."""
    user_id: int
    chat_id: int
    message_text: str
    response_type: ResponseType
    chat_history: List[Dict[str, Any]]
    user_preferences: Dict[str, Any]
    chat_settings: Dict[str, Any]
    additional_context: Optional[Dict[str, Any]] = None
    
    def __post_init__(self) -> None:
        # Initialize empty dict if None
        self.additional_context = self.additional_context or {}


@dataclass
class AIResponse:
    """AI response with metadata."""
    text: str
    response_type: ResponseType
    confidence: float
    tokens_used: int
    processing_time: float
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self) -> None:
        # Initialize empty dict if None
        self.metadata = self.metadata or {}


class AIResponseStrategy(ABC):
    """Abstract strategy for AI responses."""
    
    @abstractmethod
    async def generate_response(self, context: AIContext) -> AIResponse:
        """Generate an AI response based on the context."""
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        pass
    
    @abstractmethod
    def is_applicable(self, context: AIContext) -> bool:
        """Check if this strategy is applicable for the given context."""
        pass


class DirectResponseStrategy(AIResponseStrategy):
    """Strategy for direct, straightforward responses."""
    
    def __init__(self, gpt_service: Any) -> None:
        self.gpt_service = gpt_service
    
    async def generate_response(self, context: AIContext) -> AIResponse:
        """Generate a direct response."""
        prompt = self._build_direct_prompt(context)
        
        start_time = time.time()
        response_text = await self.gpt_service.generate_response(
            prompt=prompt,
            max_tokens=150,
            temperature=0.7
        )
        processing_time = time.time() - start_time
        
        return AIResponse(
            text=response_text,
            response_type=ResponseType.DIRECT,
            confidence=0.8,
            tokens_used=int(len(response_text.split()) * 1.3),  # Rough estimate
            processing_time=processing_time,
            metadata={"prompt_type": "direct"}
        )
    
    def _build_direct_prompt(self, context: AIContext) -> str:
        """Build a direct prompt."""
        return f"Respond directly and concisely to: {context.message_text}"
    
    def get_strategy_name(self) -> str:
        """Get strategy name."""
        return "direct_response"
    
    def is_applicable(self, context: AIContext) -> bool:
        """Check if applicable."""
        return context.response_type == ResponseType.DIRECT


class RandomResponseStrategy(AIResponseStrategy):
    """Strategy for random, conversational responses."""
    
    def __init__(self, gpt_service: Any) -> None:
        self.gpt_service = gpt_service
    
    async def generate_response(self, context: AIContext) -> AIResponse:
        """Generate a random response."""
        prompt = self._build_random_prompt(context)
        
        start_time = time.time()
        response_text = await self.gpt_service.generate_response(
            prompt=prompt,
            max_tokens=100,
            temperature=1.0  # Higher temperature for more randomness
        )
        processing_time = time.time() - start_time
        
        return AIResponse(
            text=response_text,
            response_type=ResponseType.RANDOM,
            confidence=0.6,
            tokens_used=int(len(response_text.split()) * 1.3),
            processing_time=processing_time,
            metadata={"prompt_type": "random"}
        )
    
    def _build_random_prompt(self, context: AIContext) -> str:
        """Build a random prompt."""
        return f"Make a casual, interesting comment about: {context.message_text}"
    
    def get_strategy_name(self) -> str:
        """Get strategy name."""
        return "random_response"
    
    def is_applicable(self, context: AIContext) -> bool:
        """Check if applicable."""
        return context.response_type == ResponseType.RANDOM


class ContextualResponseStrategy(AIResponseStrategy):
    """Strategy for context-aware responses."""
    
    def __init__(self, gpt_service: Any) -> None:
        self.gpt_service = gpt_service
    
    async def generate_response(self, context: AIContext) -> AIResponse:
        """Generate a contextual response."""
        prompt = self._build_contextual_prompt(context)
        
        start_time = time.time()
        response_text = await self.gpt_service.generate_response(
            prompt=prompt,
            max_tokens=200,
            temperature=0.8
        )
        processing_time = time.time() - start_time
        
        return AIResponse(
            text=response_text,
            response_type=ResponseType.CONTEXTUAL,
            confidence=0.9,
            tokens_used=int(len(response_text.split()) * 1.3),
            processing_time=processing_time,
            metadata={"prompt_type": "contextual", "context_length": len(context.chat_history)}
        )
    
    def _build_contextual_prompt(self, context: AIContext) -> str:
        """Build a contextual prompt with chat history."""
        history_text = ""
        if context.chat_history:
            recent_messages = context.chat_history[-5:]  # Last 5 messages
            history_text = "\n".join([f"- {msg.get('text', '')}" for msg in recent_messages])
        
        return f"""Given this recent conversation:
{history_text}

Respond appropriately to: {context.message_text}"""
    
    def get_strategy_name(self) -> str:
        """Get strategy name."""
        return "contextual_response"
    
    def is_applicable(self, context: AIContext) -> bool:
        """Check if applicable."""
        return (context.response_type == ResponseType.CONTEXTUAL and 
                len(context.chat_history) > 0)


class AnalyticalResponseStrategy(AIResponseStrategy):
    """Strategy for analytical, detailed responses."""
    
    def __init__(self, gpt_service: Any) -> None:
        self.gpt_service = gpt_service
    
    async def generate_response(self, context: AIContext) -> AIResponse:
        """Generate an analytical response."""
        prompt = self._build_analytical_prompt(context)
        
        start_time = time.time()
        response_text = await self.gpt_service.generate_response(
            prompt=prompt,
            max_tokens=300,
            temperature=0.5  # Lower temperature for more focused analysis
        )
        processing_time = time.time() - start_time
        
        return AIResponse(
            text=response_text,
            response_type=ResponseType.ANALYTICAL,
            confidence=0.85,
            tokens_used=int(len(response_text.split()) * 1.3),
            processing_time=processing_time,
            metadata={"prompt_type": "analytical"}
        )
    
    def _build_analytical_prompt(self, context: AIContext) -> str:
        """Build an analytical prompt."""
        return f"Analyze and provide detailed insights about: {context.message_text}"
    
    def get_strategy_name(self) -> str:
        """Get strategy name."""
        return "analytical_response"
    
    def is_applicable(self, context: AIContext) -> bool:
        """Check if applicable."""
        return context.response_type == ResponseType.ANALYTICAL


class AIResponseStrategyManager:
    """Manager for AI response strategies."""
    
    def __init__(self) -> None:
        self._strategies: Dict[str, AIResponseStrategy] = {}
        self._default_strategy: Optional[AIResponseStrategy] = None
    
    def register_strategy(self, strategy: AIResponseStrategy) -> None:
        """Register a response strategy."""
        self._strategies[strategy.get_strategy_name()] = strategy
        logger.info(f"Registered AI strategy: {strategy.get_strategy_name()}")
    
    def set_default_strategy(self, strategy: AIResponseStrategy) -> None:
        """Set the default strategy."""
        self._default_strategy = strategy
        logger.info(f"Set default AI strategy: {strategy.get_strategy_name()}")
    
    async def generate_response(self, context: AIContext) -> AIResponse:
        """Generate response using the most appropriate strategy."""
        # Find applicable strategies
        applicable_strategies = [
            strategy for strategy in self._strategies.values()
            if strategy.is_applicable(context)
        ]
        
        # Use the first applicable strategy
        if applicable_strategies:
            strategy = applicable_strategies[0]
            logger.info(f"Using AI strategy: {strategy.get_strategy_name()}")
            return await strategy.generate_response(context)
        
        # Fall back to default strategy
        if self._default_strategy:
            logger.info(f"Using default AI strategy: {self._default_strategy.get_strategy_name()}")
            return await self._default_strategy.generate_response(context)
        
        # No strategy available
        raise ValueError("No applicable AI response strategy found")
    
    def get_strategy(self, name: str) -> Optional[AIResponseStrategy]:
        """Get a strategy by name."""
        return self._strategies.get(name)
    
    def get_all_strategies(self) -> Dict[str, AIResponseStrategy]:
        """Get all registered strategies."""
        return self._strategies.copy()


# AI Service Integration
class AIService:
    """Service for AI interactions using strategy pattern."""
    
    def __init__(self, strategy_manager: AIResponseStrategyManager, service_registry: Any) -> None:
        self.strategy_manager = strategy_manager
        self.service_registry = service_registry
    
    async def generate_response(
        self, 
        update: Update, 
        context: CallbackContext[Any, Any, Any, Any], 
        response_type: ResponseType = ResponseType.DIRECT,
        message_text_override: Optional[str] = None
    ) -> AIResponse:
        """Generate AI response using appropriate strategy."""
        # Build AI context
        ai_context = await self._build_context(update, context, response_type, message_text_override)
        
        # Generate response using strategy manager
        response = await self.strategy_manager.generate_response(ai_context)
        
        # Log the interaction
        logger.info(f"Generated {response.response_type.value} response in {response.processing_time:.2f}s")
        
        return response
    
    async def _build_context(
        self, 
        update: Update, 
        context: CallbackContext[Any, Any, Any, Any], 
        response_type: ResponseType,
        message_text_override: Optional[str] = None
    ) -> AIContext:
        """Build AI context from Telegram update."""
        user_id = update.effective_user.id if update.effective_user else 0
        chat_id = update.effective_chat.id if update.effective_chat else 0
        message_text = message_text_override or (update.message.text if update.message else "")
        
        # Get services
        config_manager = self.service_registry.get_service('config_manager')
        chat_history_manager = self.service_registry.get_service('chat_history_manager')
        
        # Get chat history
        chat_history = chat_history_manager.get_recent_messages(chat_id, limit=10)
        
        # Get user preferences and chat settings
        chat_type = update.effective_chat.type if update.effective_chat else "private"
        chat_config = await config_manager.get_config(str(chat_id), chat_type)
        user_preferences: Dict[str, Any] = {}  # TODO: Implement user preferences
        
        return AIContext(
            user_id=user_id,
            chat_id=chat_id,
            message_text=message_text or "",
            response_type=response_type,
            chat_history=chat_history,
            user_preferences=user_preferences,
            chat_settings=chat_config
        )


# Import time for timing
import time