"""Executes outbound HTTP calls based on endpoint definitions and parameters."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Tuple

import httpx

from .schema_processor import SchemaProcessor, APISpec, EndpointSchema
from ..core.config import settings


class APIOrchestrator:
    """Perform HTTP requests using endpoint metadata from SchemaProcessor."""

    def __init__(self, schema_processor: SchemaProcessor):
        self.schema_processor = schema_processor
        self._client = httpx.AsyncClient(timeout=settings.api_timeout_seconds)

    async def execute(self, endpoint_name: str, params: Dict[str, Any]) -> httpx.Response:
        """Find endpoint definition and execute request with params."""
        spec, ep = self.schema_processor.get_endpoint(endpoint_name)
        url = self._build_url(spec, ep, params)
        method = ep.method.upper()
        headers = self._build_headers(spec)

        # For simplicity GET -> params in query, others in json body.
        if method == "GET":
            response = await self._client.request(method, url, headers=headers, params=params)
        else:
            response = await self._client.request(method, url, headers=headers, json=params)

        response.raise_for_status()
        return response

    # ------------------------------------------------------------------
    @staticmethod
    def _build_url(spec: APISpec, ep: EndpointSchema, params: Dict[str, Any]) -> str:
        path = ep.path
        # substitute path params like {id}
        for key, value in params.items():
            path = path.replace(f"{{{key}}}", str(value))
        return spec.baseUrl.rstrip("/") + path

    @staticmethod
    def _build_headers(spec: APISpec) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if spec.authentication and spec.authentication.get("type") == "bearer":
            headers["Authorization"] = f"Bearer {spec.authentication['token']}"
        return headers

    async def aclose(self):  # pragma: no cover
        await self._client.aclose()
