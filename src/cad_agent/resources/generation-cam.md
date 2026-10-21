Write Python for PowerMill 2027 using cad_agent.integrations.powermill.
Return ONLY JSON with exactly two strings: summary and code.
Use connect(), execute_command(app, text), and require_empty_project(app) BEFORE
changing the application. Use an empty unsaved session; never reset, close or
overwrite an existing project. Stop clearly if the requested setup is unavailable.
Use only the immutable input model specified in the handoff. Inspect imported
units, orientation and dimensions; do not assume neutral-file import is accurate.
Save a native project and preview beneath Path(__file__).resolve().parent.
Write cam_artifacts.json with exactly project_file, preview_file (relative paths),
and toolpaths (list of names). Optional application_process_id selects the same
PowerMill instance for inspection. Use connect(process_id=PID) when explicitly
targeting a dedicated instance. IDs are transient; never fall back to another
window if the chosen process is unavailable. The entire project is an artifact.
Check API command results and computed toolpaths. Restore any changed dialog
settings in finally. Never write false safety/approval claims. No NC programs,
postprocessing, machine transfer, networking, shell commands or secret access.
This stage proposes CAM operations only. Missing machine, fixture, material,
holder or cutting data must be disclosed; do not fabricate a production setup.
For the initial demo, software toolpath calculation is allowed with documented
assumptions; record that it is not a complete process or manufacturing release.
Do not change independent inspection code or derive approval from script success.
