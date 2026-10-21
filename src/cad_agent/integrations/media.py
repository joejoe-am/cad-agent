"""Local image normalization and bounded, timestamp-labelled video sampling."""

import math
import re
import shutil
import subprocess
import warnings
from pathlib import Path

from PIL import Image, ImageOps


def normalize_image(source: Path, output: Path) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(source) as image:
            if image.width * image.height > 40_000_000:
                raise ValueError("Image exceeds the 40 megapixel input limit.")
            if getattr(image, "n_frames", 1) > 1:
                raise ValueError("Animated images are unsupported; attach a video or individual stills.")
            original = image.size
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1536, 1536))
            if "A" in image.getbands() or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGBA", rgba.size, "white")
                image = Image.alpha_composite(background, rgba)
            image.convert("RGB").save(output, "JPEG", quality=88)
            return {"original_size": list(original), "prepared_size": list(image.size)}


def sample_video(source: Path, folder: Path, *, count: int = 8) -> tuple[list[tuple[Path, float]], dict]:
    if not 1 <= count <= 8:
        raise ValueError("Sample count must be between 1 and 8.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("Video input requires FFmpeg on PATH; no frames were silently omitted.")
    # FFmpeg's own header inspection also works on installations without ffprobe.
    header = subprocess.run(
        [ffmpeg, "-nostdin", "-hide_banner", "-protocol_whitelist", "file,pipe", "-i", str(source)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    duration = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", header.stderr)
    if not duration:
        raise ValueError("Could not read finite video duration with FFmpeg.")
    h, m, s = map(float, duration.groups())
    seconds = h * 3600 + m * 60 + s
    if not math.isfinite(seconds) or not 0 < seconds <= 3600:
        raise ValueError("Video must have a known duration between 0 and 3600 seconds.")
    frames = []
    for index in range(count):
        target = seconds * (index + 0.5) / count
        raw = folder / f"frame-{index + 1:02d}-raw.jpg"
        output = folder / f"frame-{index + 1:02d}.jpg"
        result = subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-ss",
                f"{target:.6f}",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-vf",
                "scale=1536:1536:force_original_aspect_ratio=decrease",
                "-y",
                str(raw),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if result.returncode or not raw.is_file() or raw.stat().st_size == 0:
            raise ValueError(f"Could not decode video sample near {target:.3f} seconds.")
        normalize_image(raw, output)
        raw.unlink()
        frames.append((output, target))
    return frames, {
        "duration_seconds": seconds,
        "sample_count": count,
        "sampling": "Uniform midpoint seek targets; times are approximate, not exact frame PTS.",
        "audio_analyzed": False,
    }
