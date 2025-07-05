"""Redis-backed session store for conversations, active API selection, and API specs.

If Redis is unavailable (e.g. not running locally), this falls back to an in-memory
Python dictionary so the backend can still run for development or tests.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import asyncio

try:
    import redis.asyncio as redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None  # noqa: N816

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Connection helpers
# ----------------------------------------------------------------------------

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis: Optional["redis.Redis"] = None  # type: ignore[name-defined]
_fallback_store: Dict[str, Any] = {}


async def _get_redis() -> Optional["redis.Redis"]:  # type: ignore[name-defined]
    """Return a connected Redis client, or *None* if Redis/driver unavailable."""
    global _redis  # noqa: PLW0603
    if redis is None:
        return None
    if _redis is None:
        try:
            _redis = await redis.from_url(_REDIS_URL, decode_responses=True)
            # simple ping to verify connection
            await _redis.ping()
            logger.info("Connected to Redis at %s", _REDIS_URL)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable (%s). Falling back to in-memory store.", exc)
            _redis = None
    return _redis

# ----------------------------------------------------------------------------
# Conversation history helpers
# ----------------------------------------------------------------------------

_CONV_KEY = "conv:{}"  # conversation messages list (JSON string)
_ACTIVE_API_KEY = "active_api:{}"  # simple string
_SPEC_KEY = "spec:{}"  # API spec JSON string


async def save_conversation(conv_id: str, messages: List["Message"]):  # type: ignore[name-defined]
    data = json.dumps([m.model_dump() for m in messages])
    client = await _get_redis()
    key = _CONV_KEY.format(conv_id)
    if client:
        await client.set(key, data)
    else:
        _fallback_store[key] = data


async def load_conversation(conv_id: str) -> Optional[List["Message"]]:  # type: ignore[name-defined]
    from ..core.schemas import Message  # local import to avoid circular deps

    client = await _get_redis()
    key = _CONV_KEY.format(conv_id)
    raw: Optional[str]
    if client:
        raw = await client.get(key)  # type: ignore[assignment]
    else:
        raw = _fallback_store.get(key)  # type: ignore[assignment]
    if raw is None:
        return None
    try:
        return [Message(**item) for item in json.loads(raw)]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse stored conversation: %s", exc)
        return None


# ----------------------------------------------------------------------------
# Active API helpers
# ----------------------------------------------------------------------------

async def set_active_api(conv_id: str, api_name: str) -> None:
    client = await _get_redis()
    key = _ACTIVE_API_KEY.format(conv_id)
    if client:
        await client.set(key, api_name)
    else:
        _fallback_store[key] = api_name


async def get_active_api(conv_id: str) -> Optional[str]:
    client = await _get_redis()
    key = _ACTIVE_API_KEY.format(conv_id)
    if client:
        return await client.get(key)  # type: ignore[return-value]
    return _fallback_store.get(key)  # type: ignore[return-value]


# ----------------------------------------------------------------------------
# API spec helpers
# ----------------------------------------------------------------------------

async def save_spec(api_name: str, spec: Dict[str, Any]) -> None:
    data = json.dumps(spec)
    client = await _get_redis()
    key = _SPEC_KEY.format(api_name)
    if client:
        await client.set(key, data)
    else:
        _fallback_store[key] = data


async def load_specs() -> List[Dict[str, Any]]:
    """Return all stored specs from Redis or fallback store."""
    client = await _get_redis()
    specs: List[Dict[str, Any]] = []
    if client:
        async for key in client.scan_iter(match=_SPEC_KEY.format("*")):
            raw = await client.get(key)  # type: ignore[assignment]
            if raw:
                try:
                    specs.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
    else:
        for key, raw in _fallback_store.items():
            if key.startswith("spec:"):
                try:
                    specs.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
    return specs
