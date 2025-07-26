"""
Tests for modules/prompts.py

This module tests the GPT prompts configuration.
"""

import pytest
from modules.prompts import GPT_PROMPTS


class TestGPTPrompts:
    """Test GPT prompts configuration."""

    def test_gpt_prompts_exists(self):
        """Test that GPT_PROMPTS dictionary exists."""
        assert GPT_PROMPTS is not None
        assert isinstance(GPT_PROMPTS, dict)

    def test_gpt_prompts_contains_required_keys(self):
        """Test that GPT_PROMPTS contains all required prompt keys."""
        required_keys = [
            "gpt_response",
            "gpt_response_return_text", 
            "gpt_summary",
            "get_word_from_gpt"
        ]
        
        for key in required_keys:
            assert key in GPT_PROMPTS, f"Missing required prompt key: {key}"

    def test_gpt_prompts_values_are_strings(self):
        """Test that all prompt values are non-empty strings."""
        for key, value in GPT_PROMPTS.items():
            assert isinstance(value, str), f"Prompt {key} should be a string"
            assert len(value.strip()) > 0, f"Prompt {key} should not be empty"

    def test_gpt_response_prompt_content(self):
        """Test that gpt_response prompt contains expected content."""
        prompt = GPT_PROMPTS["gpt_response"]
        
        # Check for key content elements
        assert "Ukrainian" in prompt
        assert "Russian" in prompt
        assert "PT CRUISER" in prompt
        assert "crazy driver" in prompt

    def test_gpt_summary_prompt_content(self):
        """Test that gpt_summary prompt contains expected content."""
        prompt = GPT_PROMPTS["gpt_summary"]
        
        # Check for key content elements
        assert "hallucinate" in prompt
        assert "Ukrainian" in prompt
        assert "Russian" in prompt

    def test_get_word_from_gpt_prompt_content(self):
        """Test that get_word_from_gpt prompt contains expected content."""
        prompt = GPT_PROMPTS["get_word_from_gpt"]
        
        # Check for key content elements
        assert "Ukrainian" in prompt
        assert "single" in prompt
        assert "word" in prompt

    def test_gpt_response_return_text_prompt_content(self):
        """Test that gpt_response_return_text prompt contains expected content."""
        prompt = GPT_PROMPTS["gpt_response_return_text"]
        
        # Check for key content elements
        assert "helpful assistant" in prompt
        assert "Ukrainian" in prompt
        assert "single" in prompt