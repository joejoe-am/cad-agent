# Code generation providers

Default: **codex**, a task-file handoff to this existing Codex conversation. No API
key is needed. This is interactive workspace integration, not a background API
connection to this chat. Codex login credentials are not read or reused.

All four providers support both CAD and linked PowerMill CAM generation through
the same response format. See [CAD-to-CAM workflow](cad-to-cam.md) for CAM commands.

| Provider | Interface | Credentials |
| --- | --- | --- |
| codex | CODEX_TASK.md and response.json | None |
| openai | Responses REST API | OPENAI_API_KEY |
| anthropic | Claude Messages REST API | ANTHROPIC_API_KEY |
| openrouter | Chat Completions REST API | OPENROUTER_API_KEY |

Edit providers.toml to select a default and a model available in your account.
API model IDs are deliberately blank. Set keys in process environment variables;
.env loading is not implemented. Never put keys in TOML, tasks, code or chat.

## Commands

Run with the project virtual environment's Python:

```powershell
.\.venv\Scripts\python.exe -m cad_agent providers
.\.venv\Scripts\python.exe -m cad_agent new "Create a pocket plate" --provider codex
```

Use the resulting job directory instead of JOB below:

```powershell
.\.venv\Scripts\python.exe -m cad_agent generate JOB
```

Codex: ask this conversation to read CODEX_TASK.md and write response.json with
exactly two strings, summary and code. APIs do that remotely and stage script.py
automatically. Incomplete, refused, malformed or non-JSON responses are rejected.
Local syntax and schema checks happen before staging. Provider-side constrained
decoding is not implemented.

```powershell
# Stage Codex's response:
.\.venv\Scripts\python.exe -m cad_agent accept JOB
# Inspect script.py first:
.\.venv\Scripts\python.exe -m cad_agent run JOB --reviewed
# Record inspection findings and generate a revision:
.\.venv\Scripts\python.exe -m cad_agent repair JOB "Pocket position failed inspection"
.\.venv\Scripts\python.exe -m cad_agent generate JOB
```

Jobs retain up to three attempts, generated code and execution logs. Previous
errors and feedback enter repair prompts. Successful execution remains
executed_unverified; it is not engineering approval. The reference geometry
checker only supports the fixed reference pocket plate. Other designs need their
own independent checks. Repair is stepwise, not automatic execution.

APIs receive task text, packaged API context and previous feedback. Jobs can now
include reference text, images, sampled video frames and local SolidWorks parts;
see [attachments](attachments.md) for routing, privacy and editing limits.
CHM binaries are not uploaded. Full documentation retrieval and remote tool
access are not implemented yet. Native CAD binaries stay local.

## Boundaries and tests

The runner is not a security sandbox. Scripts run with local user permissions.
Syntax checks and prompt instructions do not restrict code access. The runner
removes the three standard provider-key variables from the child environment;
custom key variables and other secrets are not isolated. Review code before use.
Timeouts do not guarantee cancellation of ongoing SolidWorks COM operations.
Run one CAD job at a time.

API adapters use fixed HTTPS endpoints, finite timeouts and no automatic retries.
Mocked protocol tests cover all providers. Live requests require your credentials
and model access and have not been tested in this workspace.

## Official references

- [OpenAI quickstart](https://developers.openai.com/api/docs/quickstart)
- [OpenAI Responses reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [Claude Messages reference](https://platform.claude.com/docs/en/api/messages/create)
- [OpenRouter Chat Completions](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion)
