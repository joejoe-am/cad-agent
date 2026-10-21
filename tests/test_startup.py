import subprocess
import unittest
from unittest.mock import patch

from cad_agent.cli import main
from cad_agent.integrations.solidworks import SolidWorksConnectionError, start


class StartupTests(unittest.TestCase):
    def test_confirmation_required(self):
        with patch("cad_agent.integrations.solidworks.subprocess.run") as run:
            with self.assertRaises(ValueError):
                start()
            run.assert_not_called()

    def test_timeout_validation(self):
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                start(confirmed=True, timeout=timeout)

    def test_worker_success(self):
        with (
            patch("cad_agent.integrations.solidworks.sys.platform", "win32"),
            patch("cad_agent.integrations.solidworks._sandbox_account", return_value=None),
            patch(
                "cad_agent.integrations.solidworks.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, '{"ready": true}', ""),
            ) as run,
        ):
            self.assertTrue(start(confirmed=True, timeout=30)["ready"])
            self.assertEqual(run.call_args.kwargs["timeout"], 30)

    def test_worker_timeout_explains_application_may_remain(self):
        with (
            patch("cad_agent.integrations.solidworks.sys.platform", "win32"),
            patch("cad_agent.integrations.solidworks._sandbox_account", return_value=None),
            patch(
                "cad_agent.integrations.solidworks.subprocess.run",
                side_effect=subprocess.TimeoutExpired("worker", 1),
            ),
            self.assertRaisesRegex(SolidWorksConnectionError, "may still be opening"),
        ):
            start(confirmed=True)

    def test_isolated_account_does_not_launch_hidden_application(self):
        with (
            patch("cad_agent.integrations.solidworks.sys.platform", "win32"),
            patch("cad_agent.integrations.solidworks._sandbox_account", return_value="CodexSandboxOffline"),
            patch("cad_agent.integrations.solidworks.subprocess.run") as run,
            self.assertRaisesRegex(SolidWorksConnectionError, "isolated Windows account"),
        ):
            start(confirmed=True)
        run.assert_not_called()

    def test_cli_defaults_to_cancel(self):
        for answer in ("", "no", "anything"):
            with (
                self.subTest(answer=answer),
                patch("sys.argv", ["cad-agent", "start"]),
                patch("builtins.input", return_value=answer),
                patch("cad_agent.cli.start") as launch,
                patch("builtins.print"),
            ):
                self.assertEqual(main(), 0)
                launch.assert_not_called()

    def test_cli_confirmation_launches(self):
        with (
            patch("sys.argv", ["cad-agent", "start", "--timeout", "45"]),
            patch("builtins.input", return_value="yes"),
            patch("cad_agent.cli.start", return_value={"ready": True}) as launch,
            patch("builtins.print"),
        ):
            self.assertEqual(main(), 0)
            launch.assert_called_once_with(confirmed=True, timeout=45)
