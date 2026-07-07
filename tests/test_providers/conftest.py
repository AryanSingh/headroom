"""Fixtures for OpenAI provider tests."""

import pytest

from cutctx.providers.openai import OpenAIProvider, OpenAITokenCounter


@pytest.fixture
def openai_tokenizer():
    """Return an OpenAITokenCounter instance for gpt-4o."""
    return OpenAITokenCounter(model="gpt-4o")


@pytest.fixture
def openai_provider():
    """Return an OpenAIProvider instance."""
    return OpenAIProvider()
