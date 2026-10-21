import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cad_agent.application.prompts import engineering_context
from cad_agent.config import find_workspace
from cad_agent.integrations.solidworks import read_member
from cad_agent.storage.json_files import read_json, write_json


class MaintenanceTests(unittest.TestCase):
    def test_workspace_discovery_from_child(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            root = Path(folder).resolve()
            (root / "providers.toml").write_text("")
            child = root / "nested"
            child.mkdir()
            self.assertEqual(find_workspace(child), root)

    def test_workspace_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / "providers.toml").write_text("")
            with patch.dict(os.environ, {"CAD_AGENT_WORKSPACE": str(root)}):
                self.assertEqual(find_workspace(), root)

    def test_atomic_write_failure_preserves_previous_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "job.json"
            write_json(path, {"state": "created"})
            with patch("cad_agent.storage.json_files.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    write_json(path, {"state": "executing"})
            self.assertEqual(read_json(path), {"state": "created"})
            self.assertEqual(len(list(Path(folder).iterdir())), 1)

    def test_context_is_packaged_without_prototype_dependency(self):
        self.assertIn("SOLIDWORKS 2025", engineering_context())

    def test_com_object_is_not_invoked(self):
        class Object:
            _oleobj_ = object()

            def __call__(self):
                raise AssertionError("COM object was invoked")

        class Host:
            member = Object()

        self.assertIs(read_member(Host(), "member"), Host.member)
