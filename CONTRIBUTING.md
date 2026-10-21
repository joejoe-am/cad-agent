# Development

Use Python 3.11+; desktop SolidWorks automation requires Windows and compatible
64-bit Python. Install into a local virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check src tests
.\.venv\Scripts\python.exe -m build
```

Tests use fake provider transports and do not require credentials, network calls
or SolidWorks. Test API request/response boundaries, workflow transitions and
independent geometry assumptions. Live CAD tests are explicit, create new
documents, and save to a new job directory.

Keep domain code independent of vendor COM and HTTP interfaces. Put integration
details under integrations/, workflow policy under application/, and file/process
operations under storage/ and execution/. Reference-only geometry checks must
state their supported shape and must not claim general validation.

Do not edit historical job scripts as application code. Keep keys in environment
variables. Do not commit local models, help binaries, virtual environments or
IDE settings. Back up local model archives separately from source control.

See docs/architecture.md and docs/providers.md before changing workflow behavior.

Desktop/session behavior is documented in docs/desktop-and-sessions.md. Frontend
source lives in ui/: use Node.js 24, `npm ci`, `npm test`, `npm run format:check`
and `npm run build`. Build the UI before `python -m build` so wheels include its
assets. Use `pip install -e ".[api,desktop,dev]"` for native desktop development.
There is no hosted CI: run the checks in README.md before pushing.
Session/graph tests use local temporary SQLite files and scripted model decisions;
they must not require API credentials or modify existing CAD documents.
