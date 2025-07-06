"""Core Pydantic schemas for request / response bodies."""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str = Field(..., description="Sender role, e.g. user or assistant")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    messages: List[Message]
    spec_id: str = Field(..., description="ID of the API spec to use for this conversation")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID for continuation")


class ChatResponse(BaseModel):
    conversation_id: str
    messages: List[Message]


class UploadSpecRequest(BaseModel):
    spec: Dict[str, Any]


class UploadSpecResponse(BaseModel):
    status: str
    detail: Optional[str] = None


class SetActiveSpecRequest(BaseModel):
    api_name: str = Field(..., description="Name of the API spec to activate for this conversation")


class SetActiveSpecResponse(BaseModel):
    status: str


class ConversationResponse(BaseModel):
    conversation_id: str
    messages: List[Message]
