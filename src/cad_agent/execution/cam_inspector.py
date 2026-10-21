"""Maintained CAM inspection worker; never accepts generated safety assertions."""

import json
import sys
from pathlib import Path

from cad_agent.application.cam import validate_handoff
from cad_agent.domain.cam import CamArtifacts
from cad_agent.integrations.powermill import connect, execute_command
from cad_agent.storage.json_files import read_json, write_json


def contained_file(attempt: Path, relative: str) -> Path:
    path = (attempt / relative).resolve(strict=True)
    path.relative_to(attempt.resolve())
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("Expected a nonempty artifact file inside the current attempt.")
    return path


def inspect_application(app, attempt: Path, artifacts: CamArtifacts) -> dict:
    project_file = contained_file(attempt, artifacts.project_file)
    contained_file(attempt, artifacts.preview_file)
    if project_file.suffix.lower() != ".pmlprj":
        raise ValueError("Expected a native .pmlprj project entry.")
    active_path = execute_command(app, "PRINT VALUE PROJECTPATH")
    if Path(active_path).resolve() != project_file.parent:
        raise ValueError("The active PowerMill project does not match this job.")
    if app.Busy:
        raise ValueError("PowerMill is still busy; inspect after calculation completes.")
    if app.Project.NCPrograms.Count:
        raise ValueError("NC programs are outside this CAM generation stage.")
    if app.Project.Models.Count < 1:
        raise ValueError("No imported model exists in PowerMill.")
    actual_names = [app.Project.Toolpaths.Item(i).Name for i in range(app.Project.Toolpaths.Count)]
    if len(artifacts.toolpaths) != len(set(artifacts.toolpaths)) or set(actual_names) != set(
        artifacts.toolpaths
    ):
        raise ValueError("Declared toolpaths do not match the active project.")
    paths = []
    for name in artifacts.toolpaths:
        if any(c in name for c in ('"', "\n", "\r", ";")):
            raise ValueError("Unsupported characters in toolpath name.")
        execute_command(app, f'ACTIVATE TOOLPATH "{name}"')

        def query(parameter):
            return execute_command(app, f'PRINT PAR TERSE "{parameter}"')

        computed = query("Computed") == "1"
        length = float(query("Statistics.CuttingMoves.Lengths.Linear")) + float(
            query("Statistics.CuttingMoves.Lengths.arcs")
        )
        if not computed or not (0 < length < float("inf")):
            raise ValueError(f"Toolpath {name} is not calculated or has no finite cutting length.")
        paths.append(
            {
                "name": name,
                "computed": computed,
                "cutting_length_project_units": length,
                "gouge_checked": query("Verification.GougeChecked") == "1",
                "cutting_status": query("Safety.Tool.Cutting.Status"),
                "links_status": query("Safety.Tool.Links.Status"),
                "leads_status": query("Safety.Tool.Leads.Status"),
            }
        )
    issues = [
        "Holder, fixture, machine and posted-code verification are not performed by this inspector.",
        "Project units and imported geometry dimensions require separate confirmation.",
    ]
    for item in paths:
        if not item["gouge_checked"] or any(
            item[key].lower() != "safe" for key in ("cutting_status", "links_status", "leads_status")
        ):
            issues.append(f"{item['name']}: gouge verification flag/status is incomplete or inconsistent.")
    return {
        "calculation_checks_passed": True,
        "project_file": str(project_file),
        "toolpaths": paths,
        "validation_issues": issues,
        "manufacturing_approved": False,
        "scope": "Live project identity, artifact presence, inventory and toolpath calculation only; not geometry or process certification.",
    }


def main() -> int:
    job = Path(sys.argv[1]).resolve()
    state = read_json(job / "job.json")
    attempt = job / f"attempt-{state['attempt']}"
    try:
        if state.get("target") != "powermill" or state["state"] != "executed_unverified":
            raise ValueError("Expected an executed CAM job.")
        validate_handoff(job)
        artifacts = CamArtifacts.model_validate(read_json(attempt / "cam_artifacts.json"))
        report = inspect_application(connect(process_id=artifacts.application_process_id), attempt, artifacts)
    except Exception as exc:
        report = {"calculation_checks_passed": False, "error": str(exc), "manufacturing_approved": False}
    write_json(attempt / "cam_inspection.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["calculation_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
