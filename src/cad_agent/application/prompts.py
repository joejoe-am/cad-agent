"""Versioned text context packaged with the application, independent of demos."""

from importlib.resources import files


def read_resource(name: str) -> str:
    return files("cad_agent.resources").joinpath(name).read_text(encoding="utf-8")


def engineering_context(target: str = "solidworks") -> str:
    if target not in ("solidworks", "powermill"):
        raise ValueError(f"Unsupported target: {target}")
    return read_resource(f"{target}-context.md")
