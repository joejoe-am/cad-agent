import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cad_agent.application import workflow as w


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "providers.toml").write_text(
            'default_provider="codex"\n[providers.codex]\nmode="workspace"\n'
        )
        self.job = w.create_job(self.root, "Read connection status")
        w.generate(self.root, self.job)

    def stage(self, code='print("ok")'):
        attempt = w.current_attempt(self.job, w.read_json(self.job / "job.json"))
        w.write_json(attempt / "response.json", dict(summary="demo", code=code))
        return w.accept(self.job)

    def test_codex_handoff(self):
        self.assertTrue((self.job / "attempt-1/CODEX_TASK.md").is_file())
        self.assertEqual(w.read_json(self.job / "job.json")["state"], "awaiting_codex")

    def test_success_stays_unverified(self):
        self.stage()
        with patch.object(w, "run_trusted_script", return_value=subprocess.CompletedProcess([], 0, "ok", "")):
            w.execute(self.job, reviewed=True)
        self.assertEqual(w.read_json(self.job / "job.json")["state"], "executed_unverified")

    def test_review_required(self):
        self.stage()
        with self.assertRaises(ValueError):
            w.execute(self.job)

    def test_changed_script_rejected(self):
        self.stage().write_text('print("changed")')
        with self.assertRaises(ValueError):
            w.execute(self.job, reviewed=True)

    def test_syntax_error_rejected(self):
        with self.assertRaises(SyntaxError):
            self.stage("def invalid(")

    def test_timeout_logged(self):
        self.stage()
        with patch.object(
            w, "run_trusted_script", side_effect=subprocess.TimeoutExpired("script", 1, output=b"partial")
        ):
            report = w.execute(self.job, reviewed=True)
        self.assertTrue(report["timed_out"])
        self.assertEqual(report["stdout"], "partial")
        self.assertEqual(w.read_json(self.job / "job.json")["state"], "execution_failed")

    def test_repair_context_and_limit(self):
        for attempt in (2, 3):
            w.request_repair(self.job, "Pocket is misplaced")
            prompt_path = w.generate(self.root, self.job)
            self.assertIn("Pocket is misplaced", prompt_path.read_text())
            self.assertEqual(w.read_json(self.job / "job.json")["attempt"], attempt)
        with self.assertRaises(ValueError):
            w.request_repair(self.job, "Try again")
