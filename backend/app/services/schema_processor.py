"""Utility to validate API specifications and convert them into LLM function definitions."""
from __future__ import annotations

from typing import Dict, Any, List
from pydantic import BaseModel, Field, ValidationError


class ParameterSchema(BaseModel):
    type: str
    required: bool = False
    description: str | None = None


class EndpointSchema(BaseModel):
    name: str
    method: str
    path: str
    description: str
    parameters: Dict[str, ParameterSchema]
    returns: str


class APISpec(BaseModel):
    apiName: str = Field(..., alias="apiName")
    baseUrl: str = Field(..., alias="baseUrl")
    authentication: Dict[str, Any] | None = None
    endpoints: List[EndpointSchema]

    class Config:
        allow_population_by_field_name = True


class SchemaProcessor:
    """Convert JSON specs to LLM function definitions and provide validation."""

    def __init__(self) -> None:
        # store specs keyed by api_name
        self._specs: Dict[str, APISpec] = {}

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def register_spec(self, spec_dict: Dict[str, Any]) -> None:
        try:
            spec = APISpec(**spec_dict)
        except ValidationError as exc:
            raise ValueError(f"Invalid API spec: {exc}") from exc
        self._specs[spec.apiName] = spec

    def list_functions(self, api_name: str | None = None) -> List[Dict[str, Any]]:
        """Return all endpoint definitions in OpenAI function schema."""
        functions: List[Dict[str, Any]] = []
        if api_name is None:
            for spec in self._specs.values():
                for ep in spec.endpoints:
                    functions.append(self._endpoint_to_function(ep))
        elif api_name in self._specs:
            for ep in self._specs[api_name].endpoints:
                functions.append(self._endpoint_to_function(ep))
        return functions

    def first_api_name(self) -> str | None:
        """Return name of first registered API spec or None."""
        return next(iter(self._specs.keys()), None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _endpoint_to_function(endpoint: EndpointSchema) -> Dict[str, Any]:
        # OpenAI function calling only supports primitives: string, number, integer, boolean, object, array.
        # Convert unsupported types (e.g., 'file') to 'string' so the model accepts the schema.
        allowed_types = {"string", "number", "integer", "boolean", "object", "array"}
        properties: Dict[str, Any] = {}
        for param_name, param in endpoint.parameters.items():
            p_type = param.type if param.type in allowed_types else "string"
            properties[param_name] = {
                "type": p_type,
                "description": param.description or "",
            }
        return {
            "name": endpoint.name,
            "description": endpoint.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": [name for name, p in endpoint.parameters.items() if p.required],
            },
        }

    # ------------------------------------------------------------------
    # Query helpers used by orchestrator
    # ------------------------------------------------------------------
    def get_endpoint(self, name: str) -> tuple[APISpec, EndpointSchema]:
        for spec in self._specs.values():
            for ep in spec.endpoints:
                if ep.name == name:
                    return spec, ep
        raise KeyError(f"Endpoint '{name}' not found in any registered API spec")
