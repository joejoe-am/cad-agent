"""Hash-bound CAD handoff and CAM job inspection orchestration."""

import hashlib
import subprocess
import sys
from pathlib import Path

from cad_agent.storage.json_files import read_json, write_json

MODEL_FORMATS = {".sldprt", ".step", ".stp", ".x_t", ".x_b", ".iges", ".igs"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_cam_job(
    root: Path,
    cad_job: Path,
    model: Path,
    task: str,
    geometry_reviewed: bool = False,
    provider: str | None = None,
) -> Path:
    from cad_agent.application.workflow import create_job, current_attempt

    if not geometry_reviewed:
        raise ValueError("Review CAD geometry, then pass --geometry-reviewed for this handoff.")
    cad_job, model = cad_job.resolve(), model.resolve(strict=True)
    state = read_json(cad_job / "job.json")
    if state.get("target", "solidworks") != "solidworks" or state["state"] != "executed_unverified":
        raise ValueError("Handoff requires a successfully executed CAD job and explicit geometry review.")
    model.relative_to(current_attempt(cad_job, state).resolve())
    if model.suffix.lower() not in MODEL_FORMATS or not model.is_file():
        raise ValueError("Choose a supported CAD model inside the CAD job current attempt.")
    content = model.read_bytes()
    if not content:
        raise ValueError("CAD model is empty.")
    job = create_job(root, task, provider or state["provider"], target="powermill")
    inputs = job / "inputs"
    inputs.mkdir()
    copy = inputs / model.name
    copy.write_bytes(content)
    write_json(
        job / "cad_handoff.json",
        {
            "cad_job": str(cad_job),
            "cad_job_sha256": digest(cad_job / "job.json"),
            "source_model": str(model),
            "model_sha256": hashlib.sha256(content).hexdigest(),
            "input_model": str(copy),
            "geometry_reviewed": True,
            "scope": "Geometry handoff only; machining and manufacturing release are not approved.",
        },
    )
    validate_handoff(job)
    return job


def validate_handoff(job: Path) -> dict:
    handoff = read_json(job / "cad_handoff.json")
    model = Path(handoff["input_model"]).resolve(strict=True)
    model.relative_to((job / "inputs").resolve())
    if not handoff["geometry_reviewed"]:
        raise ValueError("CAD geometry handoff has not been reviewed.")
    checks = [(Path(handoff["source_model"]), handoff["model_sha256"]), (model, handoff["model_sha256"])]
    if handoff.get("source_kind") != "external_model":
        checks.append((Path(handoff["cad_job"]) / "job.json", handoff["cad_job_sha256"]))
    if any(digest(path) != expected for path, expected in checks):
        raise ValueError("CAD source, job state or input copy changed; create a new geometry handoff.")
    return handoff


def create_cam_from_model(
    root: Path, model: Path, task: str, geometry_reviewed: bool = False, provider: str | None = None
) -> Path:
    """Start in PowerMill from an existing reviewed model, without a SolidWorks job."""
    from cad_agent.application.workflow import create_job

    if not geometry_reviewed:
        raise ValueError("Explicit geometry review is required for an external model.")
    model = model.resolve(strict=True)
    if not model.is_file() or model.suffix.lower() not in MODEL_FORMATS or model.stat().st_size == 0:
        raise ValueError("Choose a nonempty supported CAD model.")
    job = create_job(root, task, provider, target="powermill")
    inputs = job / "inputs"
    inputs.mkdir()
    copy = inputs / model.name
    import shutil

    shutil.copyfile(model, copy)
    if digest(model) != digest(copy):
        raise ValueError("Model changed during copying; create a fresh handoff.")
    write_json(
        job / "cad_handoff.json",
        {
            "source_kind": "external_model",
            "source_model": str(model),
            "input_model": str(copy),
            "model_sha256": digest(copy),
            "geometry_reviewed": True,
            "scope": "Reviewed external geometry only; machining and manufacturing release are not approved.",
        },
    )
    validate_handoff(job)
    return job


def inspect_cam(job: Path, timeout: float = 60) -> dict:
    """Run maintained inspection code in a fresh process, separate from generated code."""
    if timeout <= 0:
        raise ValueError("Timeout must be positive.")
    job = job.resolve()
    state = read_json(job / "job.json")
    if state.get("target") != "powermill" or state["state"] != "executed_unverified":
        raise ValueError("Execute a CAM job successfully before inspection.")
    validate_handoff(job)
    from cad_agent.application.workflow import current_attempt

    attempt = current_attempt(job, state)
    inspection_file = attempt / "cam_inspection.json"
    write_json(
        inspection_file,
        {"calculation_checks_passed": False, "status": "running", "manufacturing_approved": False},
    )
    try:
        result = subprocess.run(
            [sys.executable, "-m", "cad_agent.execution.cam_inspector", str(job)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        report = {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        report = {
            "returncode": None,
            "stdout": "",
            "stderr": "Inspection timed out; COM may still be busy.",
            "timed_out": True,
        }
    except OSError as exc:
        report = {"returncode": None, "stdout": "", "stderr": str(exc), "timed_out": False}
    if read_json(inspection_file).get("status") == "running":
        if report["returncode"] == 0:
            report["returncode"] = 1
        write_json(
            inspection_file,
            {
                "calculation_checks_passed": False,
                "error": report["stderr"] or "Inspection did not produce a report.",
                "manufacturing_approved": False,
            },
        )
    write_json(attempt / "inspection_execution.json", report)
    return report
