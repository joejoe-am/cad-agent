import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cad_agent.integrations import powermill


class PowerMillTests(unittest.TestCase):
    def test_text_error_with_zero_status_is_rejected(self):
        app = SimpleNamespace(DoCommandEx=lambda command: (0, "#ERROR: Type error"))
        with self.assertRaises(powermill.PowerMillCommandError):
            powermill.execute_command(app, 'PRINT PAR TERSE "bad"')

    def test_numeric_error_is_rejected(self):
        app = SimpleNamespace(DoCommandEx=lambda command: (1, "bad command"))
        with self.assertRaises(powermill.PowerMillCommandError):
            powermill.execute_command(app, "bad")

    def test_command_result(self):
        app = SimpleNamespace(DoCommandEx=lambda command: (0, "  1\r\n"))
        self.assertEqual(powermill.execute_command(app, 'PRINT PAR TERSE "Computed"'), "1")

    def test_saved_project_is_not_cleared(self):
        app = SimpleNamespace(Busy=False, DoCommandEx=lambda command: (0, "C:/existing"))
        with self.assertRaises(ValueError):
            powermill.require_empty_project(app)

    def test_status_reads_counts_without_commands(self):
        project = SimpleNamespace(
            **{
                name: SimpleNamespace(Count=count)
                for name, count in [("Models", 1), ("Tools", 2), ("Toolpaths", 3), ("NCPrograms", 0)]
            }
        )
        app = SimpleNamespace(Version=2027000, Visible=True, Busy=False, Project=project)
        with patch.object(powermill, "connect", return_value=app):
            status = powermill.get_status()
        self.assertEqual(status["models"], 1)
        self.assertEqual(status["toolpaths"], 3)
        self.assertFalse(status["busy"])

    def test_bad_status_is_connection_error(self):
        with patch.object(powermill, "connect", return_value=object()):
            with self.assertRaises(powermill.PowerMillConnectionError):
                powermill.get_status()
