# CAD to PowerMill workflow

CAD and CAM are separate linked jobs sharing the same provider, generation,
execution, error logging and three-attempt repair workflow. Codex workspace
handoff, OpenAI, Claude and OpenRouter can generate either stage.

The desktop agent can also start in PowerMill directly from an existing reviewed
model, without a SolidWorks job. See [desktop sessions and standalone CAM](desktop-and-sessions.md).

## 1. Finish and review CAD

Run the existing new/generate/accept/run commands. Save the native part or neutral
model inside its current attempt directory. Inspect geometry independently.
The parent job must be executed_unverified: successful code execution alone is
not approval, so an explicit geometry review is required for handoff.

## 2. Create the linked CAM job

In these commands, CAD_JOB, MODEL_FILE and CAM_JOB are placeholders for paths:

```powershell
.\.venv\Scripts\python.exe -m cad_agent cam-new CAD_JOB --model MODEL_FILE --task "Demonstrate one raster finishing path using a 6 mm ball-nose tool; save native project and preview; no NC output" --geometry-reviewed --provider codex
.\.venv\Scripts\python.exe -m cad_agent generate CAM_JOB
```

The model must be a supported file in the CAD job's current attempt. Supported
extensions are SLDPRT, STEP/STP, Parasolid X_T/X_B and IGES/IGS; actual translator
availability depends on the installed PowerMill edition. The file is copied to
CAM_JOB/inputs. Original geometry, copy and parent job state are hashed.

Generation, execution and inspection recheck the hashes. Changes to original CAD,
copied input, parent attempt/state or approval scope require a fresh handoff.
Moving linked jobs or their sources invalidates their recorded paths; archive
completed artifacts together. Do not edit the handoff JSON to bypass checks.

## 3. Generate and execute CAM code

Codex reads CODEX_TASK.md and writes response.json. API providers do this remotely.
The prompt contains the reviewed input path and PowerMill-specific context; it
does not upload the CAD binary. Remote models generate local execution code.

```powershell
.\.venv\Scripts\python.exe -m cad_agent accept CAM_JOB
.\.venv\Scripts\python.exe -m cad_agent run CAM_JOB --reviewed --timeout 180
```

The generated script should call require_empty_project before changing anything.
The connector refuses a busy, saved or nonempty project; it never resets an
existing project. Use a new empty unsaved PowerMill project for each attempt.
Failed attempts can leave entities behind; save/review them before manually
preparing another empty project. The application does not clear them for retries.

execute_command validates both numeric return code and text errors. PowerMill
calculation may be queued: scripts must wait for Computed with a bounded timeout.
Any modified dialog settings must be restored in finally. Code review and the
existing local-permissions execution boundary still apply; prompt restrictions
and helpers are not a security sandbox and cannot enforce arbitrary generated code.

## 4. Artifact contract and independent inspection

The script saves a native project and image below its attempt directory and writes
cam_artifacts.json containing:

```json
{
  "project_file": "project/project.pmlprj",
  "preview_file": "preview.jpg",
  "toolpaths": ["Raster"]
}
```

When several PowerMill instances are open, generated scripts can call
`connect(process_id=PID)` and include optional `application_process_id` in this
manifest. The inspector selects that same live process through the Running
Object Table and refuses unavailable instances. IDs are transient; after reopening
a project, record its new process ID or use a single unambiguous instance.

Keep the entire project directory, not just the small PMLPRJ entry file.

```powershell
.\.venv\Scripts\python.exe -m cad_agent cam-inspect CAM_JOB --timeout 60
```

This runs maintained code in a fresh process. It checks artifact paths/presence,
active project identity, model/toolpath inventory, Computed, finite nonzero cut
length, gouge flag and cutting/links/leads statuses. It activates declared
toolpaths for parameter queries; it does not recalculate or repair them.
Results are saved to cam_inspection.json and inspection_execution.json.

A zero exit means calculation checks passed, not complete safety verification.
The live demo's safe statuses plus GougeChecked=0 discrepancy remains visible as
an issue. Units, import geometry accuracy, holder, workholding, machine motion,
stock removal, feeds/speeds and posted code require further checks. Reports never
grant manufacturing approval. No NC/posting workflow is implemented.

```powershell
.\.venv\Scripts\python.exe -m cad_agent repair CAM_JOB "Inspection found an uncalculated path; correct the calculation and explain remaining checks"
.\.venv\Scripts\python.exe -m cad_agent generate CAM_JOB
```

Prior script errors and CAM inspection feedback enter the next generation prompt.
The three-attempt cap applies separately to each CAM job.

## Validation so far

Unit tests cover hash invalidation, handoff provenance, prompt routing, existing
project preservation, error responses, inspection timeouts and failed calculations.
The maintained inspector was exercised against the saved live PowerMill demo.
A sample linked Codex CAM task is prepared under jobs/agent-20261019-192411-5a5dd1ff.
It has not been executed because the existing saved demo project remains open.
