"""Initial explicit-unit engineering specification."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BlockSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    units: Literal["mm"] = "mm"
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    thickness: float = Field(gt=0)

    @property
    def expected_volume_m3(self) -> float:
        return (self.length / 1000) * (self.width / 1000) * (self.thickness / 1000)
