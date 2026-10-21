"""Connection, provider selection, generation, execution and repair CLI."""

import argparse
import json
from pathlib import Path

from cad_agent.application import workflow
from cad_agent.application.attachments import add_attachments, verify
from cad_agent.application.cam import create_cam_from_model, create_cam_job, inspect_cam
from cad_agent.config import find_workspace
from cad_agent.integrations.powermill import get_status as get_powermill_status
from cad_agent.integrations.solidworks import get_status, start


def main() -> int:
    parser = argparse.ArgumentParser(description="Local CAD agent tools")
    parser.add_argument("--root", type=Path, help="Workspace containing providers.toml")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    startup = commands.add_parser("start", help="Ask for confirmation, then open SolidWorks")
    startup.add_argument("--timeout", type=float, default=120)
    commands.add_parser("powermill-status")
    commands.add_parser("providers")
    gui = commands.add_parser("gui", help="Open the React desktop workspace")
    gui.add_argument("--debug", action="store_true")
    commands.add_parser("sessions", help="List saved conversations")
    session_new = commands.add_parser("session-new", help="Create a persistent conversation")
    session_new.add_argument("--title", default="New conversation")
    session_new.add_argument("--provider", choices=["codex", "openai", "anthropic", "openrouter"])
    chat = commands.add_parser("chat", help="Send a message to a saved conversation")
    chat.add_argument("session")
    chat.add_argument("message")
    chat.add_argument("--attach", type=Path, action="append", default=[])
    show = commands.add_parser("session-show", help="Inspect a saved conversation and pending action")
    show.add_argument("session")
    resume = commands.add_parser("session-resume", help="Resume a pending handoff or reviewed action")
    resume.add_argument("session")
    review = resume.add_mutually_exclusive_group()
    review.add_argument("--approve", action="store_true")
    review.add_argument("--decline", action="store_true")
    resume.add_argument("--operation-id")
    new = commands.add_parser("new")
    new.add_argument("task")
    new.add_argument("--provider", choices=["codex", "openai", "anthropic", "openrouter"])
    new.add_argument(
        "--attach", type=Path, action="append", default=[], help="Local reference file; repeatable"
    )
    attach = commands.add_parser("attach", help="Snapshot reference files before first generation")
    attach.add_argument("job", type=Path)
    attach.add_argument("files", type=Path, nargs="+")
    attachments = commands.add_parser("attachments", help="List and verify this job's reference files")
    attachments.add_argument("job", type=Path)
    cam = commands.add_parser("cam-new", help="Create a PowerMill job from reviewed CAD geometry")
    cam.add_argument("cad_job", type=Path)
    cam.add_argument("--model", type=Path, required=True)
    cam.add_argument("--task", required=True)
    cam.add_argument("--geometry-reviewed", action="store_true")
    cam.add_argument("--provider", choices=["codex", "openai", "anthropic", "openrouter"])
    external_cam = commands.add_parser(
        "cam-from-model", help="Start PowerMill directly from a reviewed existing model"
    )
    external_cam.add_argument("--model", type=Path, required=True)
    external_cam.add_argument("--task", required=True)
    external_cam.add_argument("--geometry-reviewed", action="store_true")
    external_cam.add_argument("--provider", choices=["codex", "openai", "anthropic", "openrouter"])
    inspect = commands.add_parser("cam-inspect", help="Independently inspect an executed CAM job")
    inspect.add_argument("job", type=Path)
    inspect.add_argument("--timeout", type=float, default=60)
    for name in ("generate", "accept", "run", "repair"):
        command = commands.add_parser(name)
        command.add_argument("job", type=Path)
        if name == "run":
            command.add_argument("--reviewed", action="store_true")
            command.add_argument("--timeout", type=float, default=60)
        if name == "repair":
            command.add_argument("feedback")
    args = parser.parse_args()
    try:
        args.root = args.root.resolve() if args.root else find_workspace()
        if args.command == "gui":
            from cad_agent.desktop.app import launch

            launch(args.root, debug=args.debug)
        elif args.command in ("sessions", "session-new", "chat", "session-show", "session-resume"):
            from cad_agent.application.sessions import SessionEngine

            engine = SessionEngine(args.root)
            try:
                if args.command == "sessions":
                    result = engine.store.list()
                elif args.command == "session-new":
                    result = engine.create(args.title, args.provider)
                elif args.command == "chat":
                    result = engine.submit(args.session, args.message, args.attach)
                elif args.command == "session-show":
                    result = engine.snapshot(args.session)
                else:
                    approved = True if args.approve else False if args.decline else None
                    result = engine.resume(args.session, approved, args.operation_id)
                print(json.dumps(result, indent=2, ensure_ascii=False))
            finally:
                engine.close()
        elif args.command == "status":
            print(json.dumps(get_status(), indent=2))
        elif args.command == "start":
            try:
                answer = input("Open SolidWorks on this desktop? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if answer not in ("y", "yes"):
                print("SolidWorks startup cancelled.")
                return 0
            print("Opening SolidWorks; waiting for its automation interface...", flush=True)
            print(json.dumps(start(confirmed=True, timeout=args.timeout), indent=2))
        elif args.command == "powermill-status":
            print(json.dumps(get_powermill_status(), indent=2))
        elif args.command == "providers":
            for name in ("codex", "openai", "anthropic", "openrouter"):
                _, config = workflow.config_for(args.root, name)
                print(
                    f"{name}: "
                    + (
                        "workspace handoff; no key required"
                        if name == "codex"
                        else f"model={config.model or '(not configured)'}; key env={config.api_key_env}; "
                        f"images={'enabled' if config.supports_images else 'disabled'}"
                    )
                )
        elif args.command == "new":
            print(workflow.create_job(args.root.resolve(), args.task, args.provider, attachments=args.attach))
        elif args.command == "attach":
            print(add_attachments(args.job, args.files).model_dump_json(indent=2))
        elif args.command == "attachments":
            print(verify(args.job).model_dump_json(indent=2))
        elif args.command == "cam-new":
            print(
                create_cam_job(
                    args.root, args.cad_job, args.model, args.task, args.geometry_reviewed, args.provider
                )
            )
        elif args.command == "cam-from-model":
            print(
                create_cam_from_model(args.root, args.model, args.task, args.geometry_reviewed, args.provider)
            )
        elif args.command == "cam-inspect":
            report = inspect_cam(args.job, args.timeout)
            print(json.dumps(report, indent=2))
            return 0 if report["returncode"] == 0 else 1
        elif args.command == "generate":
            print(workflow.generate(args.root.resolve(), args.job.resolve()))
        elif args.command == "accept":
            print(workflow.accept(args.job.resolve()))
        elif args.command == "run":
            report = workflow.execute(args.job.resolve(), args.reviewed, args.timeout)
            print(json.dumps(report, indent=2))
            return 0 if report["returncode"] == 0 else 1
        elif args.command == "repair":
            workflow.request_repair(args.job.resolve(), args.feedback)
            print("Feedback saved. Run generate for the next attempt.")
    except Exception as exc:
        parser.exit(1, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
