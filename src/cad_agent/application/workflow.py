"""File-backed generation, review, execution and bounded repair attempts."""

import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from cad_agent.application import attachments as inputs
from cad_agent.application.prompts import engineering_context, read_resource
from cad_agent.config import config_for
from cad_agent.execution.runner import run_trusted_script
from cad_agent.integrations.providers.adapters import APIProvider, CodexWorkspaceProvider, GeneratedCode
from cad_agent.storage.json_files import read_json, write_json

SYSTEM = read_resource("generation.md")


def create_job(
    root: Path,
    task: str,
    provider: str | None = None,
    *,
    target: str = "solidworks",
    attachments: list[Path] | None = None,
) -> Path:
    if not task.strip():
        raise ValueError("Task cannot be empty.")
    if target not in ("solidworks", "powermill"):
        raise ValueError(f"Unsupported target: {target}")
    name, _ = config_for(root, provider)
    for path in attachments or []:
        inputs.identify(path)
    if attachments and target != "solidworks":
        raise ValueError("Attachments currently support SolidWorks jobs only.")
    job = root / "jobs" / ("agent-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:8])
    job.mkdir(parents=True)
    write_json(job / "job.json", dict(task=task, provider=name, target=target, attempt=0, state="created"))
    if attachments:
        try:
            inputs.add_attachments(job, attachments)
        except Exception as exc:
            raise ValueError(f"Attachment preparation failed. Job retained at {job}: {exc}") from exc
    return job


def current_attempt(job: Path, state: dict) -> Path:
    if state["attempt"] < 1:
        raise ValueError("Generate an attempt first.")
    return job / f"attempt-{state['attempt']}"


def verify_inputs(job: Path, state: dict) -> None:
    expected = state.get("input_manifest_sha256")
    path = job / "attachments.json"
    if expected and (not path.is_file() or inputs.digest(path) != expected):
        raise ValueError("Attachment manifest changed after generation; create a new job for revised inputs.")
    inputs.verify(job)


def generate(root: Path, job: Path) -> Path:
    state = read_json(job / "job.json")
    if state["attempt"] >= 3:
        raise ValueError("Three-attempt limit reached.")
    if state["state"] not in ("created", "generation_failed", "execution_failed", "repair_requested"):
        raise ValueError("Current attempt is pending; finish it or request repair first.")
    name, config = config_for(root, state["provider"])
    target = state.get("target", "solidworks")
    system = SYSTEM if target == "solidworks" else read_resource("generation-cam.md")
    prompt = f"Task:\n{state['task']}\n"
    verify_inputs(job, state)
    reference_context, visuals = inputs.context(job)
    if reference_context:
        prompt += "\n" + reference_context
        if name == "codex" and visuals:
            prompt += (
                "\nUse the image viewing tool on EACH local visual reference above before generating code. "
                "If an image cannot be viewed, report that limitation instead of guessing its contents.\n"
            )
        elif visuals and not config.supports_images:
            raise ValueError(
                f"Configure a vision-capable model and providers.{name}.supports_images=true for visual inputs."
            )
    if target == "powermill":
        from cad_agent.application.cam import validate_handoff

        prompt += "\nReviewed CAD handoff:\n" + json.dumps(validate_handoff(job), indent=2)
    if state["attempt"]:
        previous = current_attempt(job, state)
        for filename in ("script.py", "execution.json", "cam_inspection.json", "feedback.txt"):
            path = previous / filename
            if path.is_file():
                prompt += f"\nPrevious {filename}:\n" + path.read_text(encoding="utf-8")[:40000]
    prompt += "\nAPI context:\n" + engineering_context(target)
    if (job / "attachments.json").is_file():
        state["input_manifest_sha256"] = inputs.digest(job / "attachments.json")
    state["attempt"] += 1
    attempt = current_attempt(job, state)
    attempt.mkdir()
    (attempt / "prompt.txt").write_text(system + "\n\n" + prompt, encoding="utf-8")
    state["state"] = "generating"
    write_json(job / "job.json", state)
    try:
        if name == "codex":
            path = CodexWorkspaceProvider().prepare(attempt, system, prompt)
            state["state"] = "awaiting_codex"
            write_json(job / "job.json", state)
            return path
        provider = APIProvider(name, config)
        result = (
            provider.generate(system, prompt, images=visuals)
            if visuals
            else provider.generate(system, prompt)
        )
        write_json(attempt / "response.json", result.model_dump())
        return accept(job)
    except Exception:
        state["state"] = "generation_failed"
        write_json(job / "job.json", state)
        raise


def accept(job: Path) -> Path:
    state = read_json(job / "job.json")
    if state["state"] not in ("awaiting_codex", "generating", "generation_failed"):
        raise ValueError("No response awaiting acceptance.")
    verify_inputs(job, state)
    attempt = current_attempt(job, state)
    result = GeneratedCode.model_validate_json((attempt / "response.json").read_text(encoding="utf-8"))
    ast.parse(result.code)  # Syntax validation is not a security check.
    path = attempt / "script.py"
    path.write_text(result.code, encoding="utf-8")
    state.update(state="ready_for_review", script_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    write_json(job / "job.json", state)
    return path


def execute(job: Path, reviewed: bool = False, timeout: float = 60) -> dict:
    if not reviewed:
        raise ValueError("Inspect script.py first, then pass --reviewed to execute it.")
    if timeout <= 0:
        raise ValueError("Timeout must be positive.")
    state = read_json(job / "job.json")
    if state["state"] != "ready_for_review":
        raise ValueError("No staged script ready to run.")
    verify_inputs(job, state)
    if state.get("target") == "powermill":
        from cad_agent.application.cam import validate_handoff

        validate_handoff(job)
    attempt = current_attempt(job, state)
    script = attempt / "script.py"
    if hashlib.sha256(script.read_bytes()).hexdigest() != state["script_sha256"]:
        raise ValueError("Script changed after staging; request repair and stage a new attempt.")
    state["state"] = "executing"
    write_json(job / "job.json", state)
    try:
        result = run_trusted_script(script, timeout_seconds=timeout)
        report = dict(
            returncode=result.returncode, stdout=result.stdout, stderr=result.stderr, timed_out=False
        )
    except subprocess.TimeoutExpired as exc:

        def text(value):
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")

        report = dict(returncode=None, stdout=text(exc.stdout), stderr=text(exc.stderr), timed_out=True)
    except OSError as exc:
        report = dict(returncode=None, stdout="", stderr=str(exc), timed_out=False)
    try:
        verify_inputs(job, state)
    except (OSError, ValueError) as exc:
        report["returncode"] = 1
        report["stderr"] += f"\nInput integrity check failed after execution: {exc}"
    write_json(attempt / "execution.json", report)
    state["state"] = "executed_unverified" if report["returncode"] == 0 else "execution_failed"
    write_json(job / "job.json", state)
    return report


def request_repair(job: Path, feedback: str) -> None:
    if not feedback.strip():
        raise ValueError("Provide inspection findings or error feedback.")
    state = read_json(job / "job.json")
    if state["state"] not in (
        "ready_for_review",
        "executed_unverified",
        "execution_failed",
        "awaiting_codex",
        "generation_failed",
    ):
        raise ValueError("Job is not ready for repair feedback.")
    if state["attempt"] >= 3:
        raise ValueError("Three-attempt limit reached.")
    (current_attempt(job, state) / "feedback.txt").write_text(feedback, encoding="utf-8")
    state["state"] = "repair_requested"
    write_json(job / "job.json", state)
