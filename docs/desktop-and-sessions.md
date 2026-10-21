# Desktop workspace and persistent agent

The React UI runs in a local pywebview window. A conversation has a stable ID,
full transcript, explicit project facts, attachment snapshots, linked jobs and
durable LangGraph checkpoints. Existing CLI job commands continue to work.

## Start

Use Node.js 24 and Python 3.11+ for a source checkout:

```powershell
cd ui
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,dev]"
.\.venv\Scripts\python.exe -m cad_agent gui
```

After setup, double-click `run-desktop.cmd`. Built wheels contain compiled assets
and need no Node.js at runtime. Windows uses Edge WebView2; install its runtime
if pywebview reports it unavailable. Run as the same Windows account/privilege
level as SolidWorks and PowerMill; isolated sandbox accounts cannot attach.

## Providers

Configure OpenAI, Anthropic or OpenRouter in providers.toml and set its key
environment variable **before starting the application** for an automatic loop.
Select the provider when creating a conversation. Enable `supports_images` only
for a vision-capable model. The setup panel shows configuration/readiness, never
keys. API providers receive relevant conversation context, project facts, tool
results and prepared reference images. Native CAD and original videos stay local.

Default **Codex** mode is an interactive workspace handoff, not a background API
connection to a coding conversation. Sending a message creates a task under
`.cad-agent/handoffs/<session>/`. The UI offers View task. Ask your workspace
conversation to read it and write the requested Decision JSON, then click Load
response. The graph executes the chosen tool and may request another decision.
Its task tells the conversation to view every referenced local image and leave
execution to the graph. Cancel the handoff to end that turn without an API call.
Create a new conversation to change providers.

## Conversations, files and memory

- Reopen sessions in the sidebar; history survives restarts. Export saves a
  readable JSON transcript and metadata.
- Attach text, images, videos and self-contained `.SLDPRT` files to a message.
  A reference job stores immutable copies; see attachments.md for formats/limits.
- Project facts keep explicit requirements visible. They can be edited in the
  right panel and never count as manufacturing approval.
- Import existing workspace jobs or let the agent create them. Only linked job
  artifacts can be read/executed through the registry.
- Files previews images, code and reports, and opens native CAD/CAM models.
- The agent chooses tools or answers without tools; no CAD-first route is forced.

The model receives at most 30 recent messages/about 60000 characters, plus facts
and references. The complete transcript is retained. `search_history` and
`read_message` retrieve older details. No automatic history pruning or
cross-conversation memory sharing is implemented. A turn has a 12-tool limit.

## Review, execution and recovery

LangGraph pauses before application startup, generated-code execution and model
geometry handoff. Code review shows the full script and binds approval to its
SHA-256; geometry review binds the actual model path/hash. An approval is for one
pending operation. The agent cannot approve itself by writing a project fact.

Decline returns a cancellation result to the agent for replanning. Cancel pending
turn ends a stalled turn without a new model call. Neither stops an in-flight COM
operation. Closing during an active operation waits for the worker to finish;
a hard-killed process may leave the desktop operation's effect uncertain.

Checkpoints use synchronous durability. The operation journal records a tool
before it starts and its result when finished. Replayed completed operations use
the cached result. A journal entry still marked running is treated as uncertain:
the graph stops and requires application-state inspection before a fresh action.
This is not an exactly-once guarantee across COM/filesystem/database crashes.

Thread and OS locks serialize agent operations across processes in a workspace.
Direct CLI `run` commands are outside that scheduler; do not run them alongside
desktop work. Generated Python still runs with local permissions, not in a
sandbox. Hash/copy/review helpers do not restrict arbitrary generated code.
The three-attempt limit remains; success is `executed_unverified`.

## Standalone PowerMill

The agent can inspect PowerMill directly or create CAM from a supplied model
without a SolidWorks job/process. Geometry review is still required:

```powershell
.\.venv\Scripts\python.exe -m cad_agent cam-from-model --model "part.step" --task "Propose a raster finishing demonstration; save native project and preview" --geometry-reviewed
```

Source/copy hashes are rechecked during generation, execution and inspection.
New CAM generation still requires an empty PowerMill project. Automatic mutation
of existing saved projects, NC posting and machine execution are not implemented.

## Storage and extension

`.cad-agent/sessions.sqlite3` holds transcripts, facts and the operation journal;
`checkpoints.sqlite3` holds graph state. Handoffs and JSON exports are in the same
directory. Model outputs remain in jobs/. Back up both directories with the app
closed. JSON export does not include large files or a complete checkpoint restore
package. Moving the workspace can invalidate recorded absolute paths.

Register a Tool with a Pydantic argument schema, description, handler and review
policy in application/agent_tools.py to add a capability. The graph can select
it without new fixed pipeline edges. COM details remain in integrations/ or
bounded workers; checkpoints contain plain data, never COM handles.

React source is in ui/. `npm run dev` serves UI development assets, but the Python
bridge exists only inside pywebview; a standalone browser stays in connecting
state. Run `npm test`, `npm run format:check` and `npm run build`, plus Python
checks and package build. Run those checks locally on Python 3.11 or newer;
the project has no hosted continuous integration.

Tests cover sessions, isolation, approvals, declines, cancellation, operation
replay/crash uncertainty, dynamic tool routing, standalone CAM provenance,
attachments, artifact containment and frontend bridge interactions. A native
WebView2 test verified React submission, graph/tool execution and result display
in a separate test workspace. That probe reported SolidWorks unavailable, so it
verified error reporting rather than CAD execution. Live API behavior requires
configured credentials and model access and remains untested here.

References: [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers),
[interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts),
[pywebview API](https://pywebview.flowrl.com/api/).
