"""Trusted-script execution helper; this is NOT a security sandbox."""

import os
import subprocess
import sys
from pathlib import Path


def run_trusted_script(script: Path, *, timeout_seconds: float = 60) -> subprocess.CompletedProcess[str]:
    """Run a reviewed Python script; propagate timeout errors to the caller."""
    script = script.resolve(strict=True)
    if not script.is_file() or script.suffix.lower() != ".py":
        raise ValueError("Expected a Python script file.")
    if timeout_seconds <= 0:
        raise ValueError("Timeout must be positive.")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=script.parent,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
        encoding="utf-8",
        errors="replace",
        env={
            key: value
            for key, value in {**os.environ, "PYTHONIOENCODING": "utf-8"}.items()
            if key not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")
        },
    )
