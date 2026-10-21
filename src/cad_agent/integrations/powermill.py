"""PowerMill COM connection, checked command execution and status queries."""

import sys
from typing import Any


class PowerMillConnectionError(RuntimeError):
    """PowerMill is absent, not ready, or unavailable to this Windows session."""


class PowerMillCommandError(RuntimeError):
    """A command failed numerically or returned an error in its text response."""


def execute_command(app: Any, command: str) -> str:
    """Execute one command through a typed COM wrapper and validate both outputs."""
    if not command.strip():
        raise ValueError("PowerMill command cannot be empty.")
    result = app.DoCommandEx(command)
    if not isinstance(result, tuple) or len(result) != 2:
        raise PowerMillCommandError("Expected (status, response); connect using the project connector.")
    status, response = result
    text = "" if response is None else str(response).strip()
    if status != 0 or "#ERROR" in text.upper() or "ERROR IN NETWORK" in text.upper():
        raise PowerMillCommandError(f"Command failed ({status}): {command}\n{text}")
    return text


def require_empty_project(app: Any) -> None:
    """Refuse to overwrite saved projects or existing entities; never clear them."""
    if app.Busy:
        raise PowerMillConnectionError("PowerMill is busy.")
    if execute_command(app, "PRINT VALUE PROJECTPATH") not in ("", "None"):
        raise ValueError("Use a new empty unsaved PowerMill project; an existing project is open.")
    for name in (
        "Models",
        "Tools",
        "Toolpaths",
        "NCPrograms",
        "Boundaries",
        "Patterns",
        "Workplanes",
        "FeatureSets",
        "StockModels",
        "MachineTools",
    ):
        if getattr(app.Project, name).Count:
            raise ValueError(
                f"PowerMill project contains {name}; existing projects are never cleared automatically."
            )


def connect(process_id: int | None = None) -> Any:
    """Attach only; do not launch PowerMill or alter the current project.

    Complete startup/licensing in the desktop application first. As with other
    COM calls, a busy application can block; run probes in a bounded child process.
    """
    if sys.platform != "win32":
        raise PowerMillConnectionError("PowerMill COM requires Windows.")
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise PowerMillConnectionError("Install the project with pywin32 first.") from exc
    try:
        if process_id is not None:
            # PowerMill registers each instance in the Windows Running Object Table.
            table = pythoncom.GetRunningObjectTable()
            for moniker in table.EnumRunning():
                try:
                    unknown = table.GetObject(moniker)
                    dispatch = unknown.QueryInterface(pythoncom.IID_IDispatch)
                    info = dispatch.GetTypeInfo()
                    library, _ = info.GetContainingTypeLib()
                    if library.GetDocumentation(-1)[0] != "PowerMILL":
                        continue
                    candidate = win32com.client.gencache.EnsureDispatch(dispatch)
                    if int(candidate.Debug.ProcessID) == process_id:
                        return candidate
                except Exception:
                    continue
            raise PowerMillConnectionError(
                f"PowerMill process {process_id} is not available in the Running Object Table."
            )
        app = win32com.client.GetActiveObject("PowerMILL.Application")
        # Typed wrappers expose DoCommandEx's status and out-parameter consistently.
        return win32com.client.gencache.EnsureDispatch(app)
    except Exception as exc:
        raise PowerMillConnectionError(
            "Open PowerMill and finish its startup/licensing dialogs under the same "
            f"Windows user and privilege level as Python. COM reported: {exc}"
        ) from exc


def get_status() -> dict:
    """Inspect application version and entity counts without sending commands."""
    app = connect()
    try:
        project = app.Project
        return {
            "version_raw": int(app.Version),
            "visible": bool(app.Visible),
            "busy": bool(app.Busy),
            "models": int(project.Models.Count),
            "tools": int(project.Tools.Count),
            "toolpaths": int(project.Toolpaths.Count),
            "nc_programs": int(project.NCPrograms.Count),
        }
    except Exception as exc:
        raise PowerMillConnectionError(f"PowerMill status query failed: {exc}") from exc
