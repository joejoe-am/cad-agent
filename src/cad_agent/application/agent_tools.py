"""Extensible, typed tool registry wrapping existing application use cases."""

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field

from cad_agent.application import attachments, workflow
from cad_agent.application.cam import create_cam_from_model, create_cam_job, inspect_cam
from cad_agent.storage.json_files import read_json, write_json
from cad_agent.storage.sessions import SessionStore


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobArgs(Arguments):
    job: str


class CreateCAD(Arguments):
    task: str = Field(min_length=1)
    use_attachments: bool = True


class CreateCAM(Arguments):
    task: str = Field(min_length=1)
    model: str
    cad_job: str | None = None


class RepairArgs(JobArgs):
    feedback: str = Field(min_length=1)


class StageArgs(JobArgs):
    summary: str = Field(min_length=1)
    code: str = Field(min_length=1)


class ReadArgs(JobArgs):
    file: str


class HistoryArgs(Arguments):
    query: str = Field(min_length=1, max_length=200)


class MessageArgs(Arguments):
    message_id: str


@dataclass
class Tool:
    name: str
    description: str
    arguments: type[BaseModel]
    handler: Callable
    review: bool = False

    def schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "requires_review": self.review,
            "parameters": self.arguments.model_json_schema(),
        }


class ToolRegistry:
    def __init__(self, root: Path, store: SessionStore, session_id: str):
        self.root, self.store, self.session_id = root.resolve(), store, session_id
        self.tools: dict[str, Tool] = {}
        self.register(
            Tool(
                "solidworks_status",
                "Inspect SolidWorks and open document titles without edits.",
                Arguments,
                lambda a: self.probe("solidworks"),
            )
        )
        self.register(
            Tool(
                "powermill_status",
                "Inspect PowerMill project and toolpath names; SolidWorks is unnecessary.",
                Arguments,
                lambda a: self.probe("powermill"),
            )
        )
        self.register(
            Tool(
                "start_solidworks",
                "Open SolidWorks after explicit confirmation.",
                Arguments,
                self.start_solidworks,
                True,
            )
        )
        self.register(
            Tool(
                "create_cad_job",
                "Create a SolidWorks generation/editing job using session references.",
                CreateCAD,
                self.create_cad,
            )
        )
        self.register(
            Tool(
                "create_cam_job",
                "Create PowerMill work from a reviewed model, optionally linked to a CAD job. Approval confirms geometry review, not manufacturing approval.",
                CreateCAM,
                self.create_cam,
                True,
            )
        )
        self.register(
            Tool("inspect_job", "Read a session job state and list its files.", JobArgs, self.inspect_job)
        )
        self.register(
            Tool(
                "generate_job",
                "Generate the next script or prepare a Codex task; never executes it.",
                JobArgs,
                self.generate,
            )
        )
        self.register(
            Tool(
                "stage_code",
                "Validate and stage generated code for a job awaiting a response. Code will require separate review to run.",
                StageArgs,
                self.stage,
            )
        )
        self.register(
            Tool(
                "accept_job",
                "Stage a response.json supplied through workspace handoff.",
                JobArgs,
                lambda a: {"script": str(workflow.accept(self.job(a.job)))},
            )
        )
        self.register(
            Tool(
                "run_job",
                "Run the current staged script only after full code review. Successful execution is unverified.",
                JobArgs,
                lambda a: workflow.execute(self.job(a.job), reviewed=True, timeout=180),
                True,
            )
        )
        self.register(
            Tool(
                "repair_job",
                "Record inspection findings for the next generation attempt; maximum three attempts.",
                RepairArgs,
                self.repair,
            )
        )
        self.register(
            Tool(
                "inspect_cam",
                "Run maintained CAM calculation checks on a successfully executed CAM job.",
                JobArgs,
                lambda a: inspect_cam(self.job(a.job)),
            )
        )
        self.register(
            Tool(
                "read_artifact",
                "Read a text artifact from a session job, such as code or an inspection report.",
                ReadArgs,
                self.read,
            )
        )
        self.register(
            Tool(
                "search_history",
                "Search this session's complete saved conversation, including messages outside recent model context.",
                HistoryArgs,
                self.search_history,
            )
        )
        self.register(
            Tool(
                "read_message",
                "Read a saved message from this session by its message ID.",
                MessageArgs,
                self.read_message,
            )
        )

    def register(self, tool: Tool):
        if tool.name in self.tools:
            raise ValueError(f"Duplicate tool: {tool.name}")
        self.tools[tool.name] = tool

    def search_history(self, args: HistoryArgs):
        query = args.query.casefold()
        matches = []
        for message in self.store.messages(self.session_id):
            if query in message["content"].casefold():
                index = message["content"].casefold().find(query)
                matches.append(
                    {
                        "id": message["id"],
                        "role": message["role"],
                        "created": message["created"],
                        "excerpt": message["content"][max(0, index - 200) : index + 800],
                    }
                )
        return {"matches": matches[-20:], "total_matches": len(matches)}

    def read_message(self, args: MessageArgs):
        message = next((m for m in self.store.messages(self.session_id) if m["id"] == args.message_id), None)
        if message is None:
            raise ValueError("Message not found in this session.")
        return {"id": message["id"], "role": message["role"], "content": message["content"]}

    def schemas(self):
        return [tool.schema() for tool in self.tools.values()]

    def validate(self, name: str, arguments: dict):
        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")
        tool = self.tools[name]
        return tool, tool.arguments.model_validate(arguments)

    def job(self, value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = self.root / "jobs" / path
        path = path.resolve(strict=True)
        path.relative_to((self.root / "jobs").resolve())
        if str(path) not in self.store.get(self.session_id)["data"].get("jobs", []):
            raise ValueError("Job is not linked to this session. Import it in the UI first.")
        if not (path / "job.json").is_file():
            raise ValueError("Job metadata missing.")
        return path

    def link(self, path: Path):
        data = self.store.get(self.session_id)["data"]
        if str(path) not in data["jobs"]:
            data["jobs"].append(str(path))
            self.store.update(self.session_id, data=data)

    def reference_context(self):
        references = self.store.get(self.session_id)["data"].get("references")
        return attachments.context(Path(references)) if references else ("", [])

    def create_cad(self, args: CreateCAD):
        session = self.store.get(self.session_id)
        files = []
        if args.use_attachments and session["data"].get("references"):
            ref_job = Path(session["data"]["references"])
            files = [attachments.contained(ref_job, a.path) for a in attachments.verify(ref_job).attachments]
        task = args.task + "\nConfirmed project facts:\n" + json.dumps(session["data"].get("facts", {}))
        job = workflow.create_job(self.root, task, session["provider"], attachments=files)
        self.link(job)
        return {"job": str(job), "state": "created"}

    def create_cam(self, args: CreateCAM):
        provider = self.store.get(self.session_id)["provider"]
        model = Path(args.model).resolve(strict=True)
        if args.cad_job:
            job = create_cam_job(self.root, self.job(args.cad_job), model, args.task, True, provider)
        else:
            job = create_cam_from_model(self.root, model, args.task, True, provider)
        self.link(job)
        return {"job": str(job), "state": "created", "target": "powermill"}

    def generate(self, args: JobArgs):
        job = self.job(args.job)
        path = workflow.generate(self.root, job)
        return {"output": str(path), "job": str(job), "state": read_json(job / "job.json")["state"]}

    def stage(self, args: StageArgs):
        job = self.job(args.job)
        state = read_json(job / "job.json")
        if state["state"] not in ("awaiting_codex", "generation_failed", "generating"):
            raise ValueError("Prepare generation before staging code.")
        attempt = workflow.current_attempt(job, state)
        write_json(attempt / "response.json", {"summary": args.summary, "code": args.code})
        return {"script": str(workflow.accept(job)), "state": "ready_for_review"}

    def repair(self, args: RepairArgs):
        workflow.request_repair(self.job(args.job), args.feedback)
        return {"state": "repair_requested"}

    def inspect_job(self, args: JobArgs):
        job = self.job(args.job)
        return {
            "job": str(job),
            "state": read_json(job / "job.json"),
            "files": [str(p.relative_to(job)) for p in job.rglob("*") if p.is_file()][:300],
        }

    def read(self, args: ReadArgs):
        job = self.job(args.job)
        path = (job / args.file).resolve(strict=True)
        path.relative_to(job)
        if path.suffix.lower() not in (".txt", ".md", ".py", ".json", ".csv", ".log", ".jsonl"):
            raise ValueError("Only text artifacts can be read with this tool.")
        if path.stat().st_size > 500_000:
            raise ValueError("Artifact exceeds the 500 KB text limit.")
        return {"path": str(path), "text": path.read_text(encoding="utf-8-sig")}

    def preview(self, name: str, args: BaseModel) -> dict:
        preview = {"tool": name, "arguments": args.model_dump()}
        if name == "run_job":
            job = self.job(args.job)
            state = read_json(job / "job.json")
            if state["state"] != "ready_for_review":
                raise ValueError("No staged script is ready for review.")
            script = workflow.current_attempt(job, state) / "script.py"
            content = script.read_text(encoding="utf-8")
            preview.update(script=content, script_sha256=hashlib.sha256(script.read_bytes()).hexdigest())
            if preview["script_sha256"] != state.get("script_sha256"):
                raise ValueError("Staged script changed; request repair.")
        elif name == "create_cam_job":
            model = Path(args.model).resolve(strict=True)
            preview.update(
                model=str(model),
                model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                notice="Confirm you reviewed this model's geometry. This does not approve machining.",
            )
        return preview

    @staticmethod
    def probe(target: str):
        result = subprocess.run(
            [sys.executable, "-m", "cad_agent.execution.probe", target],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        if result.returncode and not result.stdout:
            raise RuntimeError(result.stderr.strip() or "Application probe failed")
        return json.loads(result.stdout)

    @staticmethod
    def start_solidworks(args):
        from cad_agent.integrations.solidworks import start

        return start(confirmed=True)
