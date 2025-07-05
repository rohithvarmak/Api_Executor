"""Unified async LLM client supporting OpenAI and Anthropic with function calling."""
from __future__ import annotations

import asyncio
import logging
from typing import List, Dict, Any

from httpx import TimeoutException, HTTPError

from .schema_processor import SchemaProcessor
from ..core.config import settings

# Conditional imports to avoid mandatory dependencies.
try:
    import openai
except ImportError:  # pragma: no cover
    openai = None  # type: ignore

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore

logger = logging.getLogger(__name__)


class LLMClient:
    """Async wrapper around supported LLM SDKs with function-calling helper.

    Raises RuntimeError with human-readable messages on failure so that
    upstream FastAPI handlers can convert them to 4xx/5xx responses without
    exposing low-level SDK errors to the client.
    """

    def __init__(self, schema_processor: SchemaProcessor):
        self.schema_processor = schema_processor
        provider = settings.llm_provider.lower()
        if provider == "openai":
            if not openai:
                raise RuntimeError("openai package not installed")
            openai.api_key = settings.openai_api_key
        elif provider == "anthropic":
            if not anthropic:
                raise RuntimeError("anthropic package not installed")
        else:
            raise ValueError(f"Unsupported LLM provider '{provider}'")
        self.provider = provider

    # ------------------------------------------------------------------
    async def chat(self, messages: List[Dict[str, str]], api_name: str | None = None, *, retries: int = 2) -> Dict[str, Any]:
        """Call the LLM with optional retries and scoped function list."""
        functions = self.schema_processor.list_functions(api_name)
        attempt = 0
        while attempt <= retries:
            try:
                if self.provider == "openai":
                    return await self._openai_chat(messages, functions)
                return await self._anthropic_chat(messages, functions)
            except (TimeoutException, HTTPError) as exc:
                logger.warning("LLM network error (attempt %d/%d): %s", attempt + 1, retries + 1, exc)
                attempt += 1
                if attempt > retries:
                    raise RuntimeError("LLM request failed after retries") from exc
                await asyncio.sleep(2 ** attempt)
            except Exception as exc:  # noqa: BLE001
                # Non-retryable provider error
                raise RuntimeError(f"LLM provider error: {exc}") from exc

    # ------------------------------------------------------------------
    async def _openai_chat(self, messages, functions):
        model = settings.llm_model_name
        response = await openai.AsyncOpenAI().chat.completions.create(
            model=model,
            messages=messages,
            functions=functions,
            function_call="auto",  # let model decide
            timeout=settings.api_timeout_seconds,
        )
        return response.model_dump(mode="python")

    async def _anthropic_chat(self, messages, functions):
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.llm_model_name,
            messages=messages,
            tools=functions,
            max_tokens=1024,
            temperature=0.0,
        )
        return response.model_dump(mode="python")
