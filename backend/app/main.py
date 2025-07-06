"""FastAPI entrypoint wiring together the core services."""
from __future__ import annotations

import logging
from .core.config import settings
import uuid
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

from .core.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    SetActiveSpecRequest,
    SetActiveSpecResponse,
    Message,
)
from .services.schema_processor import SchemaProcessor
from .services.llm_client import LLMClient
from .services.api_orchestrator import APIOrchestrator
from .services.response_formatter import ResponseFormatter

from .services import session_store

# Configure global logging
settings_cfg = settings
logging.basicConfig(level=logging.DEBUG if settings_cfg.debug else logging.INFO,
                    format="%(levelname)s: %(message)s")

logger = logging.getLogger(__name__)
app = FastAPI(title="AI API Orchestration System")

# CORS for local dev; tighten for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

schema_processor = SchemaProcessor()
llm_client = LLMClient(schema_processor)
api_orchestrator = APIOrchestrator(schema_processor)

# Simple in-memory conversation store (could be replaced by DB)
_conversations: Dict[str, List[Message]] = {}




@app.post("/api/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    # initialize or fetch conversation history
    conv_id = request.conversation_id or str(uuid.uuid4())
    stored = await session_store.load_conversation(conv_id)
    if stored is not None:
        history: List[Message] = stored
    else:
        history: List[Message] = []
    _conversations[conv_id] = history

    # determine active API spec for this conversation
    # active_api = await session_store.get_active_api(conv_id)
    # if active_api is None:
    #     active_api = schema_processor.first_api_name()

    spec_url = f"https://swaggerparserbackend.onwavemaker.com/swagger/{request.spec_id}"
    async with httpx.AsyncClient() as client:
        response = await client.get(spec_url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        parsed_spec: Dict[str, Any] = response.json()
        parsed_spec = parsed_spec.get("parsed_spec", {})

    print(f"Parsed spec: {parsed_spec}")
    schema_processor.register_spec(parsed_spec)
    active_api = parsed_spec.get("apiName", schema_processor.first_api_name())
    # append user message
    history.append(Message(role="user", content=request.messages[-1].content))

    # prepare messages for LLM
    llm_messages = [m.model_dump() for m in history]

    # call LLM filtered by active_api
    llm_response = await llm_client.chat(llm_messages, api_name=active_api)

    # OpenAI may return function_call without textual content -> content can be None
    assistant_content = llm_response["choices"][0]["message"].get("content")
    if assistant_content:
        history.append(Message(role="assistant", content=assistant_content))

    # If LLM returned function_call, execute it
    func_call = llm_response["choices"][0]["message"].get("function_call")
    if func_call:
        import json
        endpoint_name = func_call["name"]
        raw_args = func_call.get("arguments", {})
        if isinstance(raw_args, str):
            try:
                arguments: Dict[str, Any] = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                arguments = {}
        else:
            arguments = raw_args
        try:
            api_response = await api_orchestrator.execute(endpoint_name, arguments)
            formatted = ResponseFormatter.format_response(api_response.json(), return_type="json_data")
            history.append(Message(role="assistant", content=str(formatted)))
        except Exception as exc:  # noqa: BLE001
            logger.exception("API orchestration error")
            history.append(Message(role="assistant", content=f"Error: {exc}"))

    await session_store.save_conversation(conv_id, history)
    return ChatResponse(conversation_id=conv_id, messages=history)


@app.post("/api/conversation/{conv_id}/active-spec", response_model=SetActiveSpecResponse)
async def set_active_spec(conv_id: str, req: SetActiveSpecRequest):
    await session_store.set_active_api(conv_id, req.api_name)
    return SetActiveSpecResponse(status="ok")


@app.get("/api/conversation/{conv_id}", response_model=ConversationResponse)
async def get_conversation(conv_id: str):
    if conv_id not in _conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationResponse(conversation_id=conv_id, messages=_conversations[conv_id])


@app.on_event("startup")
async def _startup():  # pragma: no cover
    # Load built-in Example API spec
    try:
        from pathlib import Path, PurePath
        import json
        example_path = Path(__file__).parent / "Example_API.json"
        with example_path.open("r", encoding="utf-8") as f:
            example_spec = json.load(f)
        schema_processor.register_spec(example_spec)
        logger.info("Loaded Example_API.json spec")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load Example_API.json: %s", exc)


@app.on_event("shutdown")
async def _shutdown():  # pragma: no cover
    await api_orchestrator.aclose()
