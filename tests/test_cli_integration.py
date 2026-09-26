"""End-to-end CLI render against a real (CPU) ffmpeg (HLD §4.11, task 7.1).

Generates a tiny synthetic clip, lays out a one-event year-event project, runs
``auto-reel render``, and asserts a single playable output is produced — the first
exercise of the whole stack from a shell entry point on real footage.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from auto_reel_ng.cli.main import main
from auto_reel_ng.probe import probe_media


@pytest.mark.has_ffmpeg
def test_render_one_event_end_to_end(tmp_path: Path, runtime, make_clip) -> None:
    clip = make_clip("clip.mp4", duration=1.0)
    event = tmp_path / "proj" / "2024" / "2024-06-21 - Trip"
    event.mkdir(parents=True)
    shutil.copy(clip, event / "clip.mp4")

    # Render on CPU explicitly: this test covers the CLI wiring end to end, not the
    # hardware path (a gpu-marked test covers that), and keeps it deterministic across
    # hosts whose hardware encode is unavailable/pending.
    output_dir = tmp_path / "out"
    assert main(["render", str(tmp_path / "proj"), "-o", str(output_dir), "--device", "cpu"]) == 0

    outputs = list(output_dir.glob("2024/*.mp4"))
    assert len(outputs) == 1

    # Playable-uniform: the output re-probes cleanly with real dimensions (the render
    # itself already passed verify_output before reporting success).
    meta = probe_media(outputs[0], runtime=runtime)
    assert meta.width > 0
    assert meta.height > 0
    assert meta.duration > 0
