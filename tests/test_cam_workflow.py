import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cad_agent.application import workflow
from cad_agent.application.cam import create_cam_job, inspect_cam, validate_handoff
from cad_agent.domain.cam import CamArtifacts
from cad_agent.execution.cam_inspector import contained_file, inspect_application
from cad_agent.storage.json_files import read_json, write_json


class CamWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "providers.toml").write_text(
            'default_provider="codex"\n[providers.codex]\nmode="workspace"\n'
        )
        self.cad = workflow.create_job(self.root, "Plate")
        (self.cad / "attempt-1").mkdir()
        state = read_json(self.cad / "job.json")
        state.update(attempt=1, state="executed_unverified")
        write_json(self.cad / "job.json", state)
        self.model = self.cad / "attempt-1/plate.SLDPRT"
        self.model.write_bytes(b"fake CAD fixture for orchestration tests")

    def create(self):
        return create_cam_job(self.root, self.cad, self.model, "Raster demo", geometry_reviewed=True)

    def test_review_required(self):
        with self.assertRaises(ValueError):
            create_cam_job(self.root, self.cad, self.model, "Raster demo")

    def test_model_must_belong_to_current_cad_attempt(self):
        outside = self.root / "outside.SLDPRT"
        outside.write_bytes(b"other")
        with self.assertRaises(ValueError):
            create_cam_job(self.root, self.cad, outside, "Raster demo", True)

    def test_copy_and_prompt(self):
        job = self.create()
        handoff = validate_handoff(job)
        self.assertEqual(Path(handoff["input_model"]).read_bytes(), self.model.read_bytes())
        prompt = workflow.generate(self.root, job).read_text()
        self.assertIn("PowerMill 2027", prompt)
        self.assertIn("require_empty_project", prompt)
        self.assertIn(handoff["model_sha256"], prompt)
        self.assertNotIn("Write Python scripts for desktop SOLIDWORKS", prompt)

    def test_source_change_invalidates_generation(self):
        job = self.create()
        self.model.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            workflow.generate(self.root, job)

    def test_parent_repair_invalidates_handoff(self):
        job = self.create()
        workflow.request_repair(self.cad, "Change plate dimensions")
        with self.assertRaises(ValueError):
            validate_handoff(job)

    def test_changed_input_blocks_execution(self):
        job = self.create()
        workflow.generate(self.root, job)
        write_json(job / "attempt-1/response.json", {"summary": "demo", "code": 'print("demo")'})
        workflow.accept(job)
        Path(read_json(job / "cad_handoff.json")["input_model"]).write_bytes(b"changed")
        with patch.object(workflow, "run_trusted_script") as runner:
            with self.assertRaises(ValueError):
                workflow.execute(job, reviewed=True)
            runner.assert_not_called()

    def test_inspection_timeout_is_logged(self):
        job = self.create()
        workflow.generate(self.root, job)
        state = read_json(job / "job.json")
        state["state"] = "executed_unverified"
        write_json(job / "job.json", state)
        with patch(
            "cad_agent.application.cam.subprocess.run", side_effect=subprocess.TimeoutExpired("inspect", 1)
        ):
            report = inspect_cam(job, timeout=1)
        self.assertTrue(report["timed_out"])
        self.assertTrue((job / "attempt-1/inspection_execution.json").is_file())
        self.assertFalse(read_json(job / "attempt-1/cam_inspection.json")["calculation_checks_passed"])

    def test_missing_inspection_report_cannot_pass(self):
        job = self.create()
        workflow.generate(self.root, job)
        state = read_json(job / "job.json")
        state["state"] = "executed_unverified"
        write_json(job / "job.json", state)
        with patch(
            "cad_agent.application.cam.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ):
            report = inspect_cam(job)
        self.assertEqual(report["returncode"], 1)
        self.assertFalse(read_json(job / "attempt-1/cam_inspection.json")["calculation_checks_passed"])


class CamInspectorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.attempt = Path(temp.name)
        project = self.attempt / "project"
        project.mkdir()
        (project / "demo.pmlprj").write_text("test fixture")
        (self.attempt / "preview.jpg").write_bytes(b"preview fixture")
        self.artifacts = CamArtifacts(
            project_file="project/demo.pmlprj", preview_file="preview.jpg", toolpaths=["Raster"]
        )
        self.app = SimpleNamespace(
            Busy=False,
            Project=SimpleNamespace(
                NCPrograms=SimpleNamespace(Count=0),
                Models=SimpleNamespace(Count=1),
                Toolpaths=SimpleNamespace(Count=1, Item=lambda i: SimpleNamespace(Name="Raster")),
            ),
        )
        self.computed = "1"
        self.length = "100.0"
        self.gouge = "0"

    def command(self, app, text):
        if text == "PRINT VALUE PROJECTPATH":
            return str(self.attempt / "project")
        if text.startswith("ACTIVATE TOOLPATH"):
            return ""
        parameter = text.split('"')[1]
        return {
            "Computed": self.computed,
            "Statistics.CuttingMoves.Lengths.Linear": self.length,
            "Statistics.CuttingMoves.Lengths.arcs": "0",
            "Verification.GougeChecked": self.gouge,
            "Safety.Tool.Cutting.Status": "safe",
            "Safety.Tool.Links.Status": "safe",
            "Safety.Tool.Leads.Status": "safe",
        }[parameter]

    def inspect(self):
        with patch("cad_agent.execution.cam_inspector.execute_command", side_effect=self.command):
            return inspect_application(self.app, self.attempt, self.artifacts)

    def test_inconsistent_gouge_flag_is_not_approval(self):
        report = self.inspect()
        self.assertTrue(report["calculation_checks_passed"])
        self.assertFalse(report["manufacturing_approved"])
        self.assertTrue(any("incomplete" in issue for issue in report["validation_issues"]))

    def test_uncalculated_toolpath_rejected(self):
        self.computed = "0"
        with self.assertRaises(ValueError):
            self.inspect()

    def test_nonfinite_length_rejected(self):
        self.length = "nan"
        with self.assertRaises(ValueError):
            self.inspect()

    def test_nc_program_rejected(self):
        self.app.Project.NCPrograms.Count = 1
        with self.assertRaises(ValueError):
            self.inspect()

    def test_other_project_rejected(self):
        with patch("cad_agent.execution.cam_inspector.execute_command", return_value=str(self.attempt)):
            with self.assertRaises(ValueError):
                inspect_application(self.app, self.attempt, self.artifacts)

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            contained_file(self.attempt / "project", "../preview.jpg")
