"""Small JS/Python bridge; long-running graph work stays off the UI thread."""

import base64
import json
import mimetypes
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cad_agent.application.sessions import SessionEngine
from cad_agent.config import config_for


class DesktopAPI:
    def __init__(self, root: Path, *, engine=None):
        self._engine = engine or SessionEngine(root)
        self._window = None
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cad-agent")
        self._guard = threading.Lock()
        self._busy = None

    def bootstrap(self):
        return {
            "sessions": self._engine.store.list(),
            "providers": self._engine.providers(),
            "workspace": str(self._engine.root),
            "busy_session": self._busy,
            "configuration": str(self._engine.root / "providers.toml"),
            "default_provider": config_for(self._engine.root)[0],
        }

    def get_session(self, session_id):
        session = self._engine.snapshot(session_id)
        session["busy"] = self._busy == session_id
        session["busy_session"] = self._busy
        session["tools"] = self._engine.registry(session_id).schemas()
        session["artifacts"] = self._artifacts(session)
        return session

    def create_session(self, provider=None, title="New conversation"):
        return self._engine.create(title, provider)

    def delete_session(self, session_id):
        with self._guard:
            if self._busy:
                raise ValueError("Wait for the running operation before deleting a conversation.")
            self._engine.delete(session_id)
        return True

    def rename_session(self, session_id, title):
        if not title.strip():
            raise ValueError("Session title cannot be empty.")
        self._engine.store.update(session_id, title=title.strip()[:120])

    def send_message(self, session_id, text, files=None):
        return self._launch(session_id, lambda: self._engine.submit(session_id, text, files))

    def resume(self, session_id, approved=None, operation_id=None):
        return self._launch(session_id, lambda: self._engine.resume(session_id, approved, operation_id))

    def set_facts(self, session_id, facts):
        self._idle(session_id)
        if not isinstance(facts, dict) or len(facts) > 50:
            raise ValueError("Expected at most 50 project facts.")
        if any(
            not isinstance(k, str) or not isinstance(v, str) or len(k) > 100 or len(v) > 2000
            for k, v in facts.items()
        ):
            raise ValueError("Project facts must have short text names and values.")
        data = self._engine.store.get(session_id)["data"]
        data["facts"] = facts
        self._engine.store.update(session_id, data=data)

    def export_session(self, session_id):
        folder = self._engine.store.directory / "exports"
        folder.mkdir(exist_ok=True)
        session = self._engine.snapshot(session_id)
        output = folder / (session["id"] + ".json")
        output.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(output)

    def pick_files(self):
        import webview

        if self._window is None:
            raise RuntimeError("Desktop window not ready.")
        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=True, file_types=("All files (*.*)",)
        )
        return list(result or [])

    def cancel_turn(self, session_id):
        if self._busy:
            raise ValueError("An operation is running; wait for it before cancelling.")
        return self._engine.cancel(session_id)

    def import_job(self, session_id):
        import webview

        self._idle(session_id)
        if self._window is None:
            raise RuntimeError("Desktop window not ready.")
        folders = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if folders:
            self._engine.import_job(session_id, folders[0])
        return bool(folders)

    def read_artifact(self, session_id, value):
        path = self._artifact_path(session_id, value)
        if not path.is_file() or path.stat().st_size > 10 * 1024**2:
            raise ValueError("Preview supports files up to 10 MiB.")
        if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
            mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            return {
                "kind": "image",
                "name": path.name,
                "content": f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii"),
            }
        if path.suffix.lower() in (".txt", ".md", ".py", ".json", ".log", ".csv", ".jsonl"):
            return {"kind": "text", "name": path.name, "content": path.read_text(encoding="utf-8-sig")}
        raise ValueError("Use Open in application for native models.")

    def open_model(self, session_id, value):
        path = self._artifact_path(session_id, value)
        if path.suffix.lower() not in (".sldprt", ".step", ".stp", ".pmlprj"):
            raise ValueError("Only native CAD/CAM models can be opened from this button.")
        if os.name != "nt":
            raise ValueError("Native CAD application launch is supported on Windows.")
        os.startfile(str(path))
        return True

    def _idle(self, session_id):
        if self._busy or self._engine.snapshot(session_id)["can_resume"]:
            raise ValueError("Finish or decline the pending operation first.")

    def _artifact_path(self, session_id, value):
        session = self._engine.store.get(session_id)
        path = Path(value).resolve(strict=True)
        roots = [Path(p).resolve() for p in session["data"].get("jobs", [])]
        if session["data"].get("references"):
            roots.append(Path(session["data"]["references"]).resolve())
        roots.append((self._engine.store.directory / "handoffs" / session_id).resolve())
        if not any(path.is_relative_to(root) for root in roots):
            raise ValueError("File is outside this session's artifacts.")
        return path

    @staticmethod
    def _artifacts(session):
        result = []
        supported = {
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".webp",
            ".sldprt",
            ".step",
            ".stp",
            ".pmlprj",
            ".py",
            ".json",
            ".md",
            ".txt",
        }
        for job in session["jobs"]:
            directory = Path(job["path"])
            for path in directory.glob("attempt-*/*"):
                if path.is_file() and path.suffix.lower() in supported:
                    result.append(
                        {
                            "path": str(path),
                            "name": path.name,
                            "attempt": path.parent.name,
                            "kind": "model"
                            if path.suffix.lower() in (".sldprt", ".step", ".stp", ".pmlprj")
                            else "image"
                            if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp")
                            else "text",
                        }
                    )
            for path in directory.glob("attempt-*/*/*.pmlprj"):
                result.append(
                    {
                        "path": str(path),
                        "name": path.name,
                        "kind": "model",
                        "attempt": path.parent.parent.name,
                    }
                )
        return result[:300]

    def _launch(self, session_id, action):
        self._engine.store.get(session_id)
        with self._guard:
            if self._busy:
                raise ValueError("Another operation is running. Desktop tools execute one at a time.")
            self._busy = session_id

        def run():
            try:
                action()
            except Exception as exc:
                messages = self._engine.store.messages(session_id)
                if not messages or messages[-1]["content"] != str(exc):
                    self._engine.store.add_message(session_id, "error", str(exc))
                self._engine.store.update(session_id, status="error")
            finally:
                with self._guard:
                    self._busy = None

        self._pool.submit(run)
        return {"started": True}

    def _close(self):
        self._pool.shutdown(wait=True)
        self._engine.close()


def launch(root: Path, *, debug=False):
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError('Install the desktop dependencies: python -m pip install -e ".[desktop]"') from exc
    index = Path(__file__).parent / "assets" / "index.html"
    if not index.is_file():
        raise RuntimeError("UI assets missing. Run npm ci and npm run build inside ui/ first.")
    api = DesktopAPI(root)
    window = webview.create_window(
        "CAD Agent",
        str(index),
        js_api=api,
        width=1440,
        height=940,
        min_size=(1080, 700),
        background_color="#f6f7f4",
        text_select=True,
    )
    api._window = window
    try:
        webview.start(debug=debug, http_server=True, gui="edgechromium" if os.name == "nt" else None)
    finally:
        api._close()
