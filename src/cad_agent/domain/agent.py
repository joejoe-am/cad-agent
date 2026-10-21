"""Serializable decisions and graph state; no COM or framework objects persisted."""

from operator import add
from typing import Annotated, TypedDict

from pydantic import BaseModel, ConfigDict, Field


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=20000)
    tool: str | None = None
    arguments: dict = Field(default_factory=dict)
    facts: dict[str, str] = Field(default_factory=dict, max_length=50)


class AgentState(TypedDict, total=False):
    session_id: str
    turn_id: str
    history: Annotated[list[dict], add]
    decision: dict
    operation_id: str
    steps: int
    blocked: bool
