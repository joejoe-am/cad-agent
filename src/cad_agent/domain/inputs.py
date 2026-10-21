"""Local attachment and provider-neutral visual input contracts."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PreparedImage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    label: str


class Attachment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    kind: Literal["text", "image", "video", "cad"]
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    images: list[PreparedImage] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class AttachmentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    attachments: list[Attachment] = Field(default_factory=list, max_length=16)


class VisualInput(BaseModel):
    path: Path
    label: str
    media_type: Literal["image/jpeg"] = "image/jpeg"
