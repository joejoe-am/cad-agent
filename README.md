# CAD Agent

Local Python application for agent-driven SolidWorks automation. Providers:
Codex workspace handoff (default), OpenAI, Anthropic Claude, and OpenRouter.
The working foundation supports generation, script staging, explicit execution,
logs and up to three repair attempts. PowerMill CAM generation and inspection
are integrated as a linked stage; NC posting and machine execution are future work.

[CAD-to-CAM commands and artifact contract](docs/cad-to-cam.md)

[Text, image, video and SolidWorks part inputs](docs/attachments.md)

[Desktop UI, persistent conversations and agent-selected tools](docs/desktop-and-sessions.md)

## Desktop workspace

The React/pywebview interface keeps conversations and project facts in SQLite.
LangGraph chooses tools, saves checkpoints and pauses for execution review.
SolidWorks and standalone PowerMill jobs can share one conversation.

```powershell
cd ui
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,dev]"
.\.venv\Scripts\python.exe -m cad_agent gui
```

After setup, double-click `run-desktop.cmd`. Configure an API provider for an
automatic agent loop; default Codex mode uses an explicit workspace file handoff.
See the desktop guide for provider configuration, review, resume and backups.

## Setup

Use Python 3.11+ (64-bit Windows for SolidWorks):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m cad_agent providers
```

Run commands inside this workspace, or provide `--root PATH`. The CLI can also
find a workspace through `CAD_AGENT_WORKSPACE`. Configure models in providers.toml
and credentials in environment variables. Codex mode requires no API key.

## Start a task

```powershell
.\.venv\Scripts\python.exe -m cad_agent status
.\.venv\Scripts\python.exe -m cad_agent start
.\.venv\Scripts\python.exe -m cad_agent new "Describe the part and dimensions" --provider codex
.\.venv\Scripts\python.exe -m cad_agent generate JOB_PATH
```

Add repeatable `--attach PATH` arguments to `new` for reference text, images,
videos, and native `.SLDPRT` parts. Videos are sampled into still frames using
FFmpeg. CAD edits use new copies; source parts are preserved. API image input
requires a configured vision-capable model and `supports_images = true`.
See [attachment handling and limits](docs/attachments.md).

For Codex, ask the current conversation to read the resulting CODEX_TASK.md.
For API providers, generation requests a remote response. Inspect staged code
before execution. See [provider workflow](docs/providers.md) for the commands.
Successful execution does not mean that geometry has been verified or approved.

`start` asks for confirmation (default No), then opens SolidWorks or makes the
existing instance visible. It waits up to 120 seconds for automation readiness;
use `start --timeout 180` for a slower startup. Complete licensing or startup
dialogs in the desktop application if needed. A timeout leaves SolidWorks open;
check `status` before retrying. Other commands continue to attach only.

If SolidWorks is open but `status` reports an isolated `CodexSandbox...` account,
the agent command is running under a different Windows identity. Run the CLI
from a normal PowerShell window as the same user and privilege level as
SolidWorks. Opening SolidWorks again does not fix account isolation. The `start`
command refuses to launch a hidden instance under that sandbox account.

## Project layout

```text
src/cad_agent/
  cli.py, config.py  CLI and workspace configuration
  application/       Generation and job orchestration
  domain/            Engineering data
  integrations/      SolidWorks and LLM providers
  execution/         Python process runner
  storage/           Atomic JSON persistence
  verification/      Independent reference checks
  resources/         Packaged prompts and API context
 tests/               Automated tests (no CAD or API keys needed)
 docs/                Architecture, setup and local API help
 jobs/                New job output
 archive/             Historical prototypes and CAD sources for saved CAM jobs
```

[Architecture](docs/architecture.md) · [Development](CONTRIBUTING.md) ·
[API documentation](docs/README.md)

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check src tests
.\.venv\Scripts\python.exe -m build
```

The runner executes reviewed code with local user permissions; it is not a
sandbox. A timeout cannot guarantee cancellation of an ongoing COM operation.
Use one CAD job at a time. Independent geometry checks currently cover a fixed
reference plate, not arbitrary products. Vendor help, source models and jobs
remain local and are excluded from source control by default; back them up.
