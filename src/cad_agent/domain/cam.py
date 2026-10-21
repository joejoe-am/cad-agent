"""Artifact contract between generated CAM scripts and independent inspection."""

from pydantic import BaseModel, ConfigDict, Field


class CamArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_file: str = Field(min_length=1)
    preview_file: str = Field(min_length=1)
    toolpaths: list[str] = Field(min_length=1)
    application_process_id: int | None = Field(default=None, gt=0)
