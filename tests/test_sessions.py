import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cad_agent.application.agent_tools import Arguments, Tool, ToolRegistry
from cad_agent.application.cam import create_cam_from_model, validate_handoff
from cad_agent.application.sessions import SessionEngine
from cad_agent.desktop.app import DesktopAPI
from cad_agent.storage.sessions import execution_lock


class SessionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "providers.toml").write_text(
            'default_provider="codex"\n[providers.codex]\nmode="workspace"'
        )
        self.engines = []
        self.calls = []

    def engine(self, decisions=None, *, actor=None, reviewed=False):
        calls = self.calls

        class Registry(ToolRegistry):
            def __init__(inner, *args):
                super().__init__(*args)
                inner.register(
                    Tool(
                        "test_tool",
                        "Test extension tool",
                        Arguments,
                        lambda a: calls.append("test_tool") or {"observed": 42},
                        reviewed,
                    )
                )

        iterator = iter(decisions or [])
        engine = SessionEngine(
            self.root, actor=actor or (lambda *a: next(iterator)), registry_factory=Registry
        )
        self.engines.append(engine)
        return engine

    def tearDown(self):
        for engine in self.engines:
            engine.close()

    def test_transcript_and_facts_survive_restart(self):
        engine = self.engine([dict(message="Dimensions recorded", facts={"width_mm": "100"})])
        identifier = engine.create()["id"]
        engine.submit(identifier, "The width is 100 mm")
        other = self.engine([dict(message="Continuing the same project")])
        saved = other.snapshot(identifier)
        self.assertEqual(saved["data"]["facts"], {"width_mm": "100"})
        self.assertEqual(len(saved["messages"]), 2)
        continued = other.submit(identifier, "What was the width?")
        self.assertEqual(len(continued["messages"]), 4)
        history = other.graph.get_state(other.config(identifier)).values["history"]
        self.assertIn("The width is 100 mm", str(history))

    def test_delete_removes_pending_chat_and_checkpoints_but_preserves_files(self):
        engine = SessionEngine(self.root)
        self.engines.append(engine)
        identifier = engine.create()["id"]
        other = engine.create()["id"]
        engine.submit(identifier, "A pending request")
        engine.store.begin_operation("operation", identifier, "example", {})
        model = self.root / "saved.SLDPRT"
        model.write_bytes(b"model")
        engine.delete(identifier)
        with self.assertRaisesRegex(ValueError, "not found"):
            engine.snapshot(identifier)
        self.assertEqual(engine.store.list()[0]["id"], other)
        self.assertIsNone(engine.store.operation("operation"))
        self.assertFalse(engine.graph.get_state(engine.config(identifier)).values)
        self.assertEqual(model.read_bytes(), b"model")

    def test_sessions_are_isolated(self):
        engine = self.engine([dict(message="One"), dict(message="Two")])
        first, second = engine.create()["id"], engine.create()["id"]
        engine.submit(first, "Project alpha")
        engine.submit(second, "Project beta")
        history = engine.graph.get_state(engine.config(second)).values["history"]
        self.assertNotIn("Project alpha", str(history))

    def test_registered_tool_can_be_chosen_without_fixed_cad_first_stage(self):
        engine = self.engine(
            [dict(message="Using the selected tool", tool="test_tool"), dict(message="Observed 42")]
        )
        result = engine.submit(engine.create()["id"], "Inspect without SolidWorks")
        self.assertEqual(self.calls, ["test_tool"])
        self.assertEqual(result["status"], "idle")
        self.assertTrue(any(m["role"] == "tool" for m in result["messages"]))

    def test_review_survives_restart_and_runs_only_after_approval(self):
        engine = self.engine([dict(message="Proposing an action", tool="test_tool")], reviewed=True)
        identifier = engine.create()["id"]
        pending = engine.submit(identifier, "Do the action")["pending"]
        self.assertEqual(self.calls, [])
        other = self.engine([dict(message="Action complete")], reviewed=True)
        self.assertEqual(other.snapshot(identifier)["pending"]["operation_id"], pending["operation_id"])
        result = other.resume(identifier, True, pending["operation_id"])
        self.assertEqual(self.calls, ["test_tool"])
        self.assertIsNone(result["pending"])

    def test_declining_does_not_execute_tool(self):
        engine = self.engine(
            [dict(message="Propose", tool="test_tool"), dict(message="Cancelled")], reviewed=True
        )
        identifier = engine.create()["id"]
        pending = engine.submit(identifier, "Do it")["pending"]
        result = engine.resume(identifier, False, pending["operation_id"])
        self.assertEqual(self.calls, [])
        self.assertTrue(next(m["detail"] for m in result["messages"] if m["role"] == "tool")["cancelled"])

    def test_approval_for_wrong_operation_rejected(self):
        engine = self.engine([dict(message="Propose", tool="test_tool")], reviewed=True)
        identifier = engine.create()["id"]
        engine.submit(identifier, "Do it")
        with self.assertRaisesRegex(ValueError, "operation ID"):
            engine.resume(identifier, True, "stale-id")
        self.assertEqual(self.calls, [])

    def test_uncertain_operation_is_not_repeated(self):
        engine = self.engine(
            [dict(message="Propose", tool="test_tool"), dict(message="Inspect before continuing")],
            reviewed=True,
        )
        identifier = engine.create()["id"]
        pending = engine.submit(identifier, "Do it")["pending"]
        engine.store.begin_operation(pending["operation_id"], identifier, "test_tool", {})
        result = engine.resume(identifier, True, pending["operation_id"])
        self.assertEqual(self.calls, [])
        tool_result = next(m["detail"] for m in result["messages"] if m["role"] == "tool")
        self.assertTrue(tool_result["uncertain"])

    def test_workspace_handoff_resumes_without_api_key(self):
        engine = SessionEngine(self.root)
        self.engines.append(engine)
        identifier = engine.create()["id"]
        pending = engine.submit(identifier, "Hello from the UI")["pending"]
        self.assertEqual(pending["kind"], "handoff")
        self.assertTrue(Path(pending["task_file"]).is_file())
        Path(pending["response_file"]).write_text(
            json.dumps(dict(message="Hello back", facts={"units": "mm"}))
        )
        result = engine.resume(identifier)
        self.assertEqual(result["messages"][-1]["content"], "Hello back")
        self.assertEqual(result["data"]["facts"], {"units": "mm"})

    def test_missing_workspace_response_preserves_pending_request(self):
        engine = SessionEngine(self.root)
        self.engines.append(engine)
        identifier = engine.create()["id"]
        pending = engine.submit(identifier, "Design from my reference")["pending"]
        with self.assertRaisesRegex(ValueError, "Codex response is not ready"):
            engine.resume(identifier)
        self.assertEqual(engine.snapshot(identifier)["pending"], pending)
        Path(pending["response_file"]).write_text(json.dumps(dict(message="Reference received")))
        self.assertEqual(engine.resume(identifier)["messages"][-1]["content"], "Reference received")

    def test_new_message_cannot_overwrite_pending_turn(self):
        engine = self.engine([dict(message="Propose", tool="test_tool")], reviewed=True)
        identifier = engine.create()["id"]
        engine.submit(identifier, "Do it")
        with self.assertRaisesRegex(ValueError, "pending action"):
            engine.submit(identifier, "Another task")

    def test_cancelling_pending_turn_allows_a_fresh_message(self):
        engine = self.engine(
            [dict(message="Propose", tool="test_tool"), dict(message="Fresh conversation")], reviewed=True
        )
        identifier = engine.create()["id"]
        engine.submit(identifier, "Do it")
        cancelled = engine.cancel(identifier)
        self.assertFalse(cancelled["can_resume"])
        result = engine.submit(identifier, "Let's discuss instead")
        self.assertEqual(result["messages"][-1]["content"], "Fresh conversation")
        self.assertEqual(self.calls, [])

    def test_workspace_lock_rejects_concurrent_submission_without_losing_chat(self):
        engine = self.engine([dict(message="Not called")])
        identifier = engine.create()["id"]
        with execution_lock(engine.store.directory):
            with self.assertRaises(BlockingIOError):
                engine.submit(identifier, "Do not submit while another process is active")
        self.assertEqual(engine.store.messages(identifier), [])

    def test_completed_operation_replay_uses_journal_instead_of_reexecuting(self):
        engine = self.engine([dict(message="Do it", tool="test_tool"), dict(message="Done")])
        identifier = engine.create()["id"]
        engine.submit(identifier, "Run test tool")
        state = engine.graph.get_state(engine.config(identifier)).values
        # The last decision is the final reply; replay the prior tool step with its stable ID.
        state = {
            **state,
            "decision": dict(message="Do it", tool="test_tool"),
            "steps": 0,
            "operation_id": state["turn_id"] + "-0",
        }
        engine._tool(state)
        self.assertEqual(self.calls, ["test_tool"])

    def test_native_picker_returns_selected_reference_paths(self):
        engine = self.engine()
        api = DesktopAPI(self.root, engine=engine)
        api._window = SimpleNamespace(create_file_dialog=lambda *a, **k: ("C:/style.png",))
        with patch.dict("sys.modules", {"webview": SimpleNamespace(FileDialog=SimpleNamespace(OPEN=1))}):
            self.assertEqual(api.pick_files(), ["C:/style.png"])
        api._pool.shutdown()

    def test_crash_after_tool_started_is_not_reexecuted_on_restart(self):
        class HardCrash(BaseException):
            pass

        calls = self.calls

        def crash(args):
            calls.append("started")
            raise HardCrash()

        class Registry(ToolRegistry):
            def __init__(inner, *args):
                super().__init__(*args)
                inner.register(Tool("test_tool", "Crash fixture", Arguments, crash))

        engine = SessionEngine(
            self.root, actor=lambda *a: dict(message="Start", tool="test_tool"), registry_factory=Registry
        )
        self.engines.append(engine)
        identifier = engine.create()["id"]
        with self.assertRaises(HardCrash):
            engine.submit(identifier, "Run fixture")
        other = self.engine(actor=lambda *a: self.fail("Agent must stop on an uncertain operation"))
        result = other.resume(identifier)
        self.assertEqual(calls, ["started"])
        self.assertTrue(any(m["detail"].get("uncertain") for m in result["messages"] if m["role"] == "tool"))
        self.assertFalse(result["can_resume"])

    def test_api_agent_selects_powermill_without_calling_solidworks(self):
        (self.root / "providers.toml").write_text(
            'default_provider="openai"\n[providers.openai]\nmodel="fixture"'
        )
        engine = SessionEngine(self.root)
        self.engines.append(engine)
        identifier = engine.create()["id"]
        with (
            patch("cad_agent.application.sessions.APIProvider") as provider,
            patch.object(ToolRegistry, "probe", return_value={"models": 1}) as probe,
        ):
            provider.return_value.complete.side_effect = [
                json.dumps(dict(message="Inspecting PowerMill only", tool="powermill_status")),
                json.dumps(dict(message="PowerMill has one model")),
            ]
            result = engine.submit(identifier, "Use only PowerMill")
        probe.assert_called_once_with("powermill")
        self.assertEqual(provider.return_value.complete.call_count, 2)
        self.assertEqual(result["messages"][-1]["content"], "PowerMill has one model")

    def test_archived_history_is_searchable_without_cross_session_leaks(self):
        engine = self.engine()
        one, two = engine.create()["id"], engine.create()["id"]
        message_id = engine.store.add_message(one, "user", "The pocket depth must be 5 mm")
        engine.store.add_message(two, "user", "The pocket depth must be 9 mm")
        registry = engine.registry(one)
        tool, args = registry.validate("search_history", {"query": "pocket"})
        result = tool.handler(args)
        self.assertEqual(result["total_matches"], 1)
        self.assertIn("5 mm", result["matches"][0]["excerpt"])
        tool, args = registry.validate("read_message", {"message_id": message_id})
        self.assertEqual(tool.handler(args)["content"], "The pocket depth must be 5 mm")

    def test_changed_review_content_cannot_use_old_approval(self):
        version = ["first"]
        calls = self.calls

        class Registry(ToolRegistry):
            def __init__(inner, *args):
                super().__init__(*args)
                inner.register(
                    Tool("test_tool", "Fixture", Arguments, lambda a: calls.append("ran") or {}, True)
                )

            def preview(inner, name, args):
                return {"tool": name, "arguments": {}, "version": version[0]}

        engine = SessionEngine(
            self.root, actor=lambda *a: dict(message="Propose", tool="test_tool"), registry_factory=Registry
        )
        self.engines.append(engine)
        identifier = engine.create()["id"]
        pending = engine.submit(identifier, "Run")["pending"]
        version[0] = "changed"
        with self.assertRaisesRegex(ValueError, "Review content changed"):
            engine.resume(identifier, True, pending["operation_id"])
        self.assertEqual(calls, [])

    def test_run_preview_contains_full_script_and_hash(self):
        from cad_agent.application import workflow

        engine = self.engine()
        identifier = engine.create()["id"]
        job = workflow.create_job(self.root, "Fixture")
        workflow.generate(self.root, job)
        workflow.write_json(
            job / "attempt-1/response.json", dict(summary="fixture", code="print('review me')")
        )
        workflow.accept(job)
        registry = engine.registry(identifier)
        registry.link(job)
        _, args = registry.validate("run_job", {"job": str(job)})
        preview = registry.preview("run_job", args)
        self.assertEqual(preview["script"], "print('review me')")
        self.assertEqual(len(preview["script_sha256"]), 64)
        (job / "attempt-1/script.py").write_text("print('changed')")
        with self.assertRaisesRegex(ValueError, "changed"):
            registry.preview("run_job", args)

    def test_bridge_cannot_read_arbitrary_local_files(self):
        engine = self.engine()
        identifier = engine.create()["id"]
        api = DesktopAPI(self.root, engine=engine)
        outside = self.root / "unlinked.txt"
        outside.write_text("private")
        with self.assertRaisesRegex(ValueError, "outside"):
            api.read_artifact(identifier, str(outside))
        api._pool.shutdown()

    def test_standalone_powermill_handoff_needs_review_and_invalidates_on_change(self):
        model = self.root / "external.step"
        model.write_text("fixture geometry")
        with self.assertRaisesRegex(ValueError, "review"):
            create_cam_from_model(self.root, model, "Raster path")
        job = create_cam_from_model(self.root, model, "Raster path", True)
        self.assertEqual(validate_handoff(job)["source_kind"], "external_model")
        from cad_agent.application import workflow

        task = workflow.generate(self.root, job).read_text()
        self.assertIn("PowerMill", task)
        model.write_text("revised")
        with self.assertRaisesRegex(ValueError, "changed"):
            validate_handoff(job)
