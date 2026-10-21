"""Workspace discovery and provider configuration, independent of source layout."""

import os
import tomllib
from pathlib import Path

from cad_agent.integrations.providers.adapters import ProviderConfig

PROVIDERS = ("codex", "openai", "anthropic", "openrouter")


def find_workspace(start: Path | None = None) -> Path:
    """Locate providers.toml from the current directory or an explicit environment path."""
    configured = os.environ.get("CAD_AGENT_WORKSPACE")
    if configured:
        root = Path(configured).expanduser().resolve()
        if not (root / "providers.toml").is_file():
            raise ValueError("CAD_AGENT_WORKSPACE must contain providers.toml.")
        return root
    current = (start or Path.cwd()).resolve()
    for root in (current, *current.parents):
        if (root / "providers.toml").is_file():
            return root
    raise ValueError("Workspace not found. Run inside the project or pass --root PATH.")


def config_for(root: Path, provider: str | None = None) -> tuple[str, ProviderConfig]:
    data = tomllib.loads((root / "providers.toml").read_text(encoding="utf-8"))
    name = provider or data.get("default_provider", "codex")
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}")
    return name, ProviderConfig.model_validate(data["providers"][name])
