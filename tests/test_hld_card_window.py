"""The design document describes the card-window split (video-card-bridge-window).

Bounded by heading: section 4.4 runs to the next ``### `` heading and the D-24 entry to the next
``- **D-`` entry, so a phrase elsewhere in the document cannot satisfy or break these checks.
"""

from __future__ import annotations

import re
from pathlib import Path

HLD = (Path(__file__).resolve().parents[1] / "docs" / "high-level-design.md").read_text(
    encoding="utf-8"
)


def _between(start: str, end_pattern: str) -> str:
    begin = HLD.index(start)
    match = re.search(end_pattern, HLD[begin + len(start) :], flags=re.MULTILINE)
    assert match is not None, end_pattern
    return HLD[begin : begin + len(start) + match.start()]


def test_section_4_4_no_longer_sends_the_whole_anchor_through_the_bridge() -> None:
    section = " ".join(_between("### 4.4 ", r"^### ").split())
    assert "for its whole length" not in section
    assert "split at the first target-frame boundary at or after the window's end" in section
    assert "the tail" in section and "ordinary hardware path" in section


def test_the_d24_entry_names_the_split_its_rules_and_the_version_bump() -> None:
    entry = " ".join(_between("- **D-24 ", r"^- \*\*D-").split())
    assert "video-card-bridge-window" in entry
    assert "N = ceil(window * fps)" in entry
    assert "A tail under 1 s is not split off" in entry
    assert "`RENDER_GRAPH_VERSION` goes 9 to 10" in entry
    assert "Measured (180 s 1080p30 H.264 first clip" in entry
    assert "for its whole length;" in entry  # the history of the cost it replaces
