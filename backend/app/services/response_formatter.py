"""Convert raw API responses into frontend-friendly payloads."""
from __future__ import annotations

from typing import Any, Dict, List


class ResponseFormatter:
    """Transforms data according to the endpoint's declared return_type."""

    @staticmethod
    def format_response(api_json: Any, return_type: str) -> Dict[str, Any]:
        if return_type == "table_data":
            rows = ResponseFormatter._extract_rows(api_json)
            return {
                "type": "table",
                "data": rows,
                "columns": ResponseFormatter._infer_columns(rows),
            }
        if return_type == "json_data":
            return api_json["content"]
        if return_type == "success_message":
            return {"type": "message", "text": "Success"}
        # default passthrough
        return {"type": "raw", "data": api_json}

    @staticmethod
    def _extract_rows(api_json: Any) -> List[dict]:
        """Support both plain list responses and paginated dicts with a 'content' list."""
        if isinstance(api_json, list):
            return api_json
        if isinstance(api_json, dict):
            if isinstance(api_json.get("content"), list):
                return api_json["content"]
        # fallback wrap single object into list for uniform handling
        return [api_json]

    @staticmethod
    def _infer_columns(rows: List[dict]) -> List[str]:
        if not rows:
            return []
        return sorted({k for row in rows for k in row.keys()})
