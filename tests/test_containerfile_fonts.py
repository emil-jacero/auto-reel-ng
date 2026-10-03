"""The Containerfile carries the bundled title-card fonts (static checks; no image is built here).

The image build itself is exercised by hand (the change's verification notes); these tests pin the
text that makes it work: the fonts are copied, verified at build time, not taken from Debian, and
the build context keeps every file of ``fonts/`` (license texts are ``.txt`` because
``.dockerignore`` drops ``**/*.md``).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTAINERFILE = (ROOT / "Containerfile").read_text(encoding="utf-8")
FONTS = ROOT / "fonts"


def _instructions() -> list[str]:
    """The Containerfile's instructions with comments dropped and continuations joined."""
    text = re.sub(r"\\\n", " ", CONTAINERFILE)
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _ignore_regex(pattern: str) -> re.Pattern[str]:
    """A .dockerignore pattern as a regex over root-relative POSIX paths (and their parents)."""
    pattern = pattern.rstrip("/")
    out = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    # the pattern names the path itself or a directory above it
    return re.compile(rf"^{out}(?:/.*)?$")


def _ignored(path: str) -> list[str]:
    patterns = [
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#") and not line.startswith("!")
    ]
    return [p for p in patterns if _ignore_regex(p).match(path)]


def test_the_containerfile_copies_the_fonts_directory() -> None:
    assert "COPY fonts/ /app/fonts/" in _instructions()


def test_the_build_verifies_the_bundled_fonts_after_the_sources_are_copied() -> None:
    instructions = _instructions()
    copy_sources = instructions.index("COPY . /app")
    verify = [
        i
        for i, line in enumerate(instructions)
        if line.startswith("RUN") and "verify_bundled_fonts()" in line
    ]
    assert len(verify) == 1
    assert verify[0] > copy_sources


def test_the_image_does_not_install_a_debian_font_package() -> None:
    assert "fonts-dejavu" not in "\n".join(_instructions())
    assert re.search(r"^\s*fontconfig\s*\\?$", CONTAINERFILE, re.MULTILINE)


def test_the_ignore_matcher_catches_what_it_should() -> None:
    # guards the matcher the next test relies on
    assert _ignored("docs/x.txt") == ["docs/"]
    assert _ignored("fonts/inter/README.md") == ["**/*.md"]
    assert _ignored("tests/a.py") == ["tests/"]


def test_no_dockerignore_pattern_matches_a_file_under_fonts() -> None:
    files = [p.relative_to(ROOT).as_posix() for p in FONTS.rglob("*") if p.is_file()]
    assert len(files) >= 19
    assert not {f: _ignored(f) for f in files if _ignored(f)}
