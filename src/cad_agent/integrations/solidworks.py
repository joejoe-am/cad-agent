"""SolidWorks attachment and explicitly confirmed desktop startup."""

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4


class SolidWorksConnectionError(RuntimeError):
    """A running SolidWorks instance could not be accessed."""


def _sandbox_account() -> str | None:
    """Read the actual Windows identity, rather than inherited USERNAME values."""
    if sys.platform != "win32":
        return None
    try:
        import win32api

        account = win32api.GetUserName()
    except Exception:
        return None
    return account if account.lower().startswith("codexsandbox") else None


def _sandbox_message(account: str) -> str:
    return (
        f"This process runs as the isolated Windows account '{account}'. "
        "The SolidWorks COM interface is unavailable in this account; an application open "
        "on your normal desktop may not be visible here. Run cad-agent from PowerShell "
        "under the same Windows account and privilege level as SolidWorks. "
        "Repeatedly reopening SolidWorks will not resolve account isolation."
    )


def read_member(obj: Any, name: str) -> Any:
    """Read a zero-argument COM member without invoking returned COM objects."""
    member = getattr(obj, name)
    return member() if callable(member) and not hasattr(member, "_oleobj_") else member


def connect() -> Any:
    """Call on the main thread; return a late-bound COM application object."""
    if sys.platform != "win32":
        raise SolidWorksConnectionError("SolidWorks COM requires Windows.")
    try:
        import win32com.client
    except ImportError as exc:
        raise SolidWorksConnectionError("Install this project and its pywin32 dependency first.") from exc
    try:
        return win32com.client.GetActiveObject("SldWorks.Application")
    except Exception as exc:
        account = _sandbox_account()
        if account:
            raise SolidWorksConnectionError(_sandbox_message(account)) from exc
        raise SolidWorksConnectionError(
            "Open desktop SolidWorks in the same user session and at the "
            f"same privilege level as Python. COM reported: {exc}"
        ) from exc


def get_status() -> dict[str, str | None]:
    """Read application revision and active document title only."""
    app = connect()
    try:
        document = app.ActiveDoc
        # Late-bound COM may expose zero-argument methods as property values.
        revision = read_member(app, "RevisionNumber")
        title = read_member(document, "GetTitle") if document else None
        return {
            "revision": str(revision),
            "active_document": str(title) if title is not None else None,
        }
    except Exception as exc:
        raise SolidWorksConnectionError(f"Status query failed: {exc}") from exc


def open_part_copy(input_path: Path | str, output_directory: Path | str, *, app: Any = None) -> Any:
    """Open a uniquely named copy for edits; leave the input and existing documents alone.

    Intended for self-contained native parts. This helper is not an execution sandbox
    and does not package or rewrite external references.
    """
    source = Path(input_path).resolve(strict=True)
    output = Path(output_directory).resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != ".sldprt":
        raise ValueError("Editing currently requires a native .SLDPRT file.")
    if not output.is_dir() or output == source.parent:
        raise ValueError("Choose a separate output directory for the editable copy.")
    if "inputs" in output.parts:
        raise ValueError("Editable output must be outside the immutable inputs directory.")
    application = app if app is not None else connect()
    destination = output / f"edited_{uuid4().hex}.SLDPRT"
    shutil.copyfile(source, destination)
    import pythoncom
    from win32com.client import VARIANT

    errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    # swDocPART=1; swOpenDocOptions_Silent=1. The new copy must be writable.
    document = application.OpenDoc6(str(destination), 1, 1, "", errors, warnings)
    if document is None or errors.value:
        raise SolidWorksConnectionError(
            f"Could not open editable part copy: errors={errors.value}, warnings={warnings.value}. "
            f"Source was preserved; copy remains at {destination}."
        )
    if Path(read_member(document, "GetPathName")).resolve() != destination:
        raise SolidWorksConnectionError("SolidWorks returned a different document; editing must stop.")
    if warnings.value:
        raise SolidWorksConnectionError(
            f"Part opened with warnings={warnings.value}; inspect its references before editing. "
            f"The new copy is open at {destination}."
        )
    return document


def start(*, confirmed: bool = False, timeout: float = 120) -> dict:
    """Activate SolidWorks in a bounded worker after explicit user confirmation.

    A timeout stops the worker, not the desktop application or its startup dialogs.
    Existing documents are never opened, closed or modified.
    """
    if not confirmed:
        raise ValueError("Confirm SolidWorks startup first.")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be finite and positive.")
    if sys.platform != "win32":
        raise SolidWorksConnectionError("SolidWorks COM requires Windows.")
    account = _sandbox_account()
    if account:
        raise SolidWorksConnectionError(_sandbox_message(account))
    try:
        result = subprocess.run(
            [sys.executable, "-m", "cad_agent.integrations.solidworks"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SolidWorksConnectionError(
            "SolidWorks startup timed out. It may still be opening; check its desktop dialogs "
            "and use the status command before retrying."
        ) from exc
    if result.returncode:
        raise SolidWorksConnectionError(result.stderr.strip() or "SolidWorks startup failed.")
    return json.loads(result.stdout)


def _start_worker() -> int:
    import time

    import win32com.client

    try:
        try:
            app = win32com.client.GetActiveObject("SldWorks.Application")
        except Exception:
            app = win32com.client.Dispatch("SldWorks.Application")
        app.Visible = True
        while True:
            try:
                revision = str(read_member(app, "RevisionNumber"))
                if revision:
                    print(json.dumps({"revision": revision, "ready": True}))
                    return 0
            except Exception:
                pass
            time.sleep(0.5)
    except Exception as exc:
        print(f"SolidWorks startup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_start_worker())
