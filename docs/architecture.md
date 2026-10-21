# Application architecture

The application is a local, single-job-at-a-time Windows CAD assistant, with a
React/pywebview desktop and a persistent LangGraph conversation loop. The LLM
generates Python; an explicit execution step runs reviewed code. Geometry checks
and engineering approval remain separate from the model's own assertions.

```text
src/cad_agent/
  cli.py                    CLI argument parsing and presentation
  config.py                 Workspace discovery and provider configuration
  application/
    workflow.py             Generate, stage, execute and repair use cases
    sessions.py             Agent decisions, checkpoints and review interrupts
    agent_tools.py          Typed extensible tool registry
    prompts.py              Packaged context loading
  domain/
    specifications.py       Engineering specifications and unit conventions
  integrations/
    solidworks.py           COM connection and member access
    providers/adapters.py   OpenAI, Claude, OpenRouter and Codex handoff
  execution/
    runner.py               Trusted script child process and timeout handling
  storage/
    json_files.py           Atomic JSON state and report persistence
    sessions.py             SQLite transcript, project facts and operation journal
  desktop/                  Native host, JS bridge and packaged React assets
  verification/
    reference.py            Explicitly limited reference-part geometry checks
  resources/                Versioned prompt/context text included in wheels
```

Top-level solidworks.py and checks.py retain compatibility for saved CAD job
scripts. Application code imports from the modules above. The CLI is available
through both `cad-agent` and
`python -m cad_agent`.

## Data and control flow

Task -> job.json -> provider -> response.json -> syntax/schema checks -> script.py
-> explicit review -> child process -> execution.json -> external inspection
-> feedback -> next generation attempt (maximum three).

Successful execution produces `executed_unverified`, never engineering approval.
Each attempt is retained. JSON files use atomic replacement to reduce corruption
from interrupted writes. The workflow is not concurrency-safe: use one process
and one SolidWorks job at a time. A process crash while executing requires manual
inspection of application and job state before recovery.

Provider HTTP calls use fixed endpoints and timeouts. Codex uses an interactive
file handoff through an existing session. Models and keys are not hard-coded.
API providers receive packaged text context and optional reference text/images or
sampled video frames; they cannot browse CHM help or inspect SolidWorks directly.
Native parts stay local and edits use new copies. Streaming and retrieval are
not implemented. See attachments.md for ingestion and provider capability limits.

## Workspace and distribution

providers.toml is workspace configuration. The CLI discovers it from the current
directory upward, or uses --root / CAD_AGENT_WORKSPACE. Package code does not
assume it is running from src/. Prompt text is installed as package data.

jobs/ contains local run output. archive/ contains historical prototypes, including
CAD source records referenced by saved CAM jobs. Those source paths and hashes
must remain intact for existing handoffs to validate.
docs/solidworks/2025 holds local vendor reference files. Source control excludes
large local artifacts; separate backups must preserve those files.

The runner is not a sandbox, and a timeout cannot reliably cancel an in-flight
COM operation. The current connection attaches to one existing SolidWorks session.
PowerMill CAM jobs share the generation loop with CAD jobs, using hash-bound
geometry handoffs and a separate inspection worker. See cad-to-cam.md. There is
no NC posting, machine execution or generic design certification.

## Next development milestones

1. Typed task, artifact and inspection contracts with recoverable job states.
2. Version-specific API documentation retrieval and structured tool feedback.
3. SolidWorks worker lifecycle management and per-job document tracking.
4. Independent verification plugins and artifact-bound approval records.
5. Richer geometry inspection and better context selection for the desktop agent.
6. Extend PowerMill inspection to units, geometry transfer, stock and machine
   verification before adding a separate machine-specific posting stage.
