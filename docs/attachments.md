# Multimodal reference inputs

CAD jobs can combine a text task with local reference files. All inputs are copied
into the job before generation. Their hashes are checked before generation and
execution, and after execution. The source files are never edited by ingestion.
Original files can subsequently be moved without breaking the snapshot.

```powershell
.\.venv\Scripts\python.exe -m cad_agent new "Refine this toy using the reference styling; preserve its dimensions" --attach "references\requirements.txt" --attach "references\style.png" --attach "references\motion.mp4" --attach "models\toy.SLDPRT"
```

Alternatively create a job, then add references before its first generation:

```powershell
.\.venv\Scripts\python.exe -m cad_agent attach JOB "style.png" "toy.SLDPRT"
.\.venv\Scripts\python.exe -m cad_agent attachments JOB
.\.venv\Scripts\python.exe -m cad_agent generate JOB
```

`attachments` lists the manifest and verifies snapshots and prepared visuals.
An invalid attachment batch leaves the previous manifest intact. If `new` fails
during media preparation it reports the retained job path, so that job can be
reused with valid inputs. Inputs freeze at first generation; use a new job to
change references. Repair attempts reuse the same inputs.

| Input | Handling in this version |
| --- | --- |
| Text task | Existing free-text command argument |
| TXT, MD, CSV, JSON | UTF-8 text included in the prompt; 64 KiB per file |
| PNG, JPEG, WebP, BMP | EXIF orientation applied, white background for transparency, resized to at most 1536 px per side, JPEG prepared for the provider; 20 MiB source limit, 40 megapixels |
| MP4, MOV, MKV, WebM, AVI | Eight still frames sampled at uniform midpoint seek targets across the duration; 512 MiB and one hour maximum |
| SLDPRT | Immutable local snapshot and instructions to inspect/edit a new copy; 512 MiB maximum |

Maximum 16 source attachments and 16 prepared images/frames per job, with a
12 MiB combined prepared-image budget. Binary or invalid UTF-8 text is rejected.
Animated images are rejected; use individual stills or a video instead. Arbitrary
PDFs, archives, STEP, assemblies and drawings are not yet supported by attachment
ingestion. The separate CAM handoff continues to support its existing formats.

## Videos

FFmpeg must be installed and available on PATH. No ffprobe dependency is required.
The original video stays local; remote providers receive the sampled JPEGs and
approximate target timestamps, not video bytes. Audio, exact motion trajectories,
and events between frames are not analyzed. Extraction failures/timeouts are
reported, never silently replaced by a text-only request. Use short, focused
clips and supplement important dimensions with explicit text or drawings.

## Providers

Codex handoff lists all local prepared image paths in CODEX_TASK.md and instructs
the current conversation to view every image before writing code. This remains
an interactive handoff; the CLI does not automatically run a Codex conversation.

For OpenAI, Claude or OpenRouter, configure a vision-capable model and explicitly
enable `supports_images` in that provider's providers.toml section:

```toml
[providers.openai]
model = "YOUR_VISION_CAPABLE_MODEL_ID"
api_key_env = "OPENAI_API_KEY"
supports_images = true
max_output_tokens = 12000
```

This flag declares your selected model's capability; it does not discover or
guarantee it. Unsupported models may still reject the request. Without the flag,
visual jobs fail before consuming an attempt. Text-only jobs need no changes.

API generation transmits task text, attached text, prepared images/video frames,
and repair context to the configured provider. Native CAD and video binaries stay
local. Local paths and filenames appear in prompts. No remote credentials or
provider model IDs are added automatically. API request formats are covered by
mocked tests; live model acceptance has not been exercised with account keys.

## Editing SolidWorks parts

Use self-contained `.SLDPRT` parts. `.SLDASM` and `.SLDDRW` are rejected because
their referenced parts and drawings need dependency packaging. Parts with
external references also require preparation; references are not rewritten.
Header validation is only a format check, not proof that SolidWorks can open the
file or that its geometry is sound.

Generated scripts are instructed to use:

```python
from pathlib import Path
from cad_agent.integrations.solidworks import open_part_copy

model = open_part_copy(input_path, Path(__file__).resolve().parent)
```

The helper creates and opens a uniquely named writable part below the attempt.
It returns an explicit document reference, checks the document path, and stops
on load errors or warnings. It never closes existing documents or edits/saves the
input snapshot. Review generated code before `run JOB --reviewed` as usual.

A remote model cannot see a native feature tree merely because a CAD path is
attached. It needs local inspection feedback and/or accompanying image views to
understand the part. Code must inspect actual feature names and dimensions and
stop when an intended edit cannot be identified. Existing repair feedback can
carry those findings into another generation attempt. Automatic feature-tree
extraction, preview capture and provider tool calls are future work.

The copy helper and hash checks protect normal workflow integrity, not arbitrary
generated code: execution still uses local user permissions. No automatic
geometry, structural, toy-safety or manufacturing approval is granted.

## Protocol references

- [OpenAI image inputs](https://developers.openai.com/api/docs/guides/images-vision)
- [Claude vision](https://platform.claude.com/docs/en/build-with-claude/vision)
- [OpenRouter image understanding](https://openrouter.ai/docs/guides/overview/multimodal/image-understanding)
- [FFmpeg documentation](https://ffmpeg.org/ffmpeg.html)
