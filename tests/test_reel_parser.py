"""Tests for the fail-loud v0 ``reel.yaml`` parser/validator."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from auto_reel_ng.errors import ReelError, ReelParseError
from auto_reel_ng.reel.parser import load_document, loads_document
from auto_reel_ng.reel.writer import dumps_document
from auto_reel_ng.staleness.fingerprint import editorial_hash

VALID_DOC = """\
version: 0
metadata:
  title: Midsummer
  date: 2024-06-21
  location: Dalarna
  description: A long summer day.
look:
  font: Inter
  unknown_future_key: 42
chapters:
  - name: ""
    clips:
      - 00400.mp4
      - 00401.mp4
  - name: Reception
    clips:
      - Reception/00400.mp4
clips:
  00400.mp4:
    trims:
      - {in: 0, out: 3.2, reason: black}
      - {in: 58.1, out: 60.0, reason: freeze}
    title: true
  Reception/00400.mp4:
    exclude: true
    rotate: 90
ignore:
  - junk/IMG_0001.mp4
"""


def test_valid_document_parses_to_expected_model() -> None:
    doc = loads_document(VALID_DOC)

    assert doc.version == 0
    assert doc.metadata.title == "Midsummer"
    assert doc.metadata.date == date(2024, 6, 21)
    assert doc.metadata.location == "Dalarna"
    assert doc.metadata.description == "A long summer day."

    # look is carried opaquely, including a field v0 does not model.
    assert doc.look["font"] == "Inter"
    assert doc.look["unknown_future_key"] == 42

    # Chapters keep document order and reference identities only.
    assert [c.name for c in doc.chapters] == ["", "Reception"]
    assert [r.identity for r in doc.chapters[0].clips] == ["00400.mp4", "00401.mp4"]
    assert [r.identity for r in doc.chapters[1].clips] == ["Reception/00400.mp4"]

    # Properties live in the clips map keyed by the same identity.
    props = doc.clips["00400.mp4"]
    assert props.title is True
    assert [(t.start, t.end, t.reason) for t in props.trims] == [
        (0.0, 3.2, "black"),
        (58.1, 60.0, "freeze"),
    ]
    reception = doc.clips["Reception/00400.mp4"]
    assert reception.exclude is True
    assert reception.rotate == 90

    assert doc.ignore == ("junk/IMG_0001.mp4",)


def test_properties_survive_a_reorder() -> None:
    # The same clip ("a.mp4") with the same `clips` entry, but moved to a different
    # chapter and position. Because properties are keyed by identity (D-B), the
    # property record is unaffected by where the clip is referenced.
    before = loads_document("""\
version: 0
chapters:
  - name: ""
    clips: [a.mp4, b.mp4]
clips:
  a.mp4:
    trims:
      - {in: 0, out: 2.0, reason: black}
""")
    after = loads_document("""\
version: 0
chapters:
  - name: ""
    clips: [b.mp4]
  - name: Reception
    clips: [a.mp4]
clips:
  a.mp4:
    trims:
      - {in: 0, out: 2.0, reason: black}
""")
    # The clip's position genuinely changed (default chapter -> Reception).
    assert before.chapters[0].clips[0].identity == "a.mp4"
    assert after.chapters[1].clips[0].identity == "a.mp4"
    # ...but its properties record is identical and still carries the trims.
    assert before.clips["a.mp4"] == after.clips["a.mp4"]
    assert [(t.start, t.end, t.reason) for t in after.clips["a.mp4"].trims] == [(0.0, 2.0, "black")]


def test_same_basename_in_different_subdirs_are_distinct() -> None:
    text = """\
version: 0
chapters:
  - name: Reception
    clips: [Reception/00400.mp4]
  - name: Speeches
    clips: [Speeches/00400.mp4]
"""
    doc = loads_document(text)
    identities = doc.referenced_identities()
    assert identities == ("Reception/00400.mp4", "Speeches/00400.mp4")
    assert len(set(identities)) == 2


def test_unknown_version_is_rejected() -> None:
    with pytest.raises(ReelParseError, match="unsupported version"):
        loads_document("version: 99\n")


def test_invalid_trim_out_le_in_is_rejected() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4]
clips:
  a.mp4:
    trims:
      - {in: 5.0, out: 5.0}
"""
    with pytest.raises(ReelParseError) as exc:
        loads_document(text)
    assert "a.mp4" in str(exc.value)
    assert "out" in str(exc.value)


def test_negative_time_is_rejected() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4]
clips:
  a.mp4:
    trims:
      - {in: -1.0, out: 2.0}
"""
    with pytest.raises(ReelParseError, match="non-negative"):
        loads_document(text)


def test_dangling_clip_properties_are_rejected() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4]
clips:
  b.mp4:
    title: true
"""
    with pytest.raises(ReelParseError, match="dangling"):
        loads_document(text)


def test_duplicate_identity_is_rejected() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4]
  - name: Two
    clips: [a.mp4]
"""
    with pytest.raises(ReelParseError, match="duplicate clip reference"):
        loads_document(text)


def test_ignore_conflicting_with_structure_is_rejected() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4]
ignore:
  - a.mp4
"""
    with pytest.raises(ReelParseError, match="both referenced"):
        loads_document(text)


def test_malformed_yaml_is_rejected() -> None:
    with pytest.raises(ReelParseError, match="malformed YAML"):
        loads_document("version: 0\n  bad: : :\n")


def test_reel_parse_error_is_a_reel_error() -> None:
    assert issubclass(ReelParseError, ReelError)


def test_sort_rule_loads() -> None:
    from auto_reel_ng.reel.document import ClipOrder, SortMethod

    doc = loads_document("version: 0\nsort:\n  method: filename\n  reverse: true\n")
    assert doc.sort == ClipOrder(method=SortMethod.FILENAME, reverse=True)


def test_sort_is_optional() -> None:
    assert loads_document("version: 0\n").sort is None


def test_custom_sort_with_custom_order_loads() -> None:
    from auto_reel_ng.reel.document import SortMethod

    doc = loads_document("version: 0\nsort:\n  method: custom\n  custom_order: {a.mp4: 2}\n")
    assert doc.sort is not None
    assert doc.sort.method is SortMethod.CUSTOM
    assert dict(doc.sort.custom_order) == {"a.mp4": 2}


@pytest.mark.parametrize(
    ("sort", "field"),
    [
        ("{method: shuffle}", "sort.method"),
        ("{reverse: 1}", "sort.reverse"),
        ("{custom_order: {a.mp4: 1}}", "sort.custom_order"),
        ("{method: filename, custom_order: {a.mp4: 1}}", "sort.custom_order"),
        ("{method: custom, custom_order: {a.mp4: first}}", "sort.custom_order"),
        ("{method: custom, custom_order: [a.mp4]}", "sort.custom_order"),
        ("[filename]", "sort"),
    ],
)
def test_malformed_sort_fails_loud_naming_the_field(sort: str, field: str) -> None:
    with pytest.raises(ReelParseError, match=field.replace(".", r"\.")):
        loads_document(f"version: 0\nsort: {sort}\n")


# --- Content that cannot be loaded is a parse error, never a builtin error -------------

BARBECUE = "version: 0\nmetadata:\n  title: Barbecue\n  date: 2024-02-30\n"

#: A double-quoted escape beyond the last code point. Raw, so the file holds the backslash:
#: in a plain literal Python itself rejects ``\UFFFFFFFF`` at compile time.
ESCAPE_BEYOND_UNICODE = r"""version: 0
metadata:
  title: "Fest \UFFFFFFFF"
"""


def _load_file(tmp_path: Path, content: str | bytes) -> tuple[Path, ReelParseError]:
    """Write ``content`` as ``reel.yaml``, load it, and return the parse error it raises."""
    reel = tmp_path / "reel.yaml"
    if isinstance(content, bytes):
        reel.write_bytes(content)
    else:
        reel.write_text(content, encoding="utf-8")
    with pytest.raises(ReelParseError) as exc:
        load_document(reel)
    return reel, exc.value


@pytest.mark.parametrize(
    ("text", "value", "line", "kind"),
    [
        pytest.param(BARBECUE, "'2024-02-30'", 4, "real date", id="v0-date"),
        pytest.param(
            "version: 0\nmetadata:\n  date: 2024-13-45\n",
            "'2024-13-45'",
            3,
            "real date",
            id="v0-month",
        ),
        pytest.param(
            "metadata:\n  date: 2024-02-30\n", "'2024-02-30'", 2, "real date", id="legacy-date"
        ),
        pytest.param(
            "metadata:\n  date: 2024-13-45\n", "'2024-13-45'", 2, "real date", id="legacy-month"
        ),
        pytest.param(
            "version: 0\nlook:\n  generated: 2024-02-29T25:00:00\n",
            "'2024-02-29T25:00:00'",
            3,
            "real date and time",
            id="look-timestamp",
        ),
        pytest.param("version: 0\nlook: {n: !!int abc}\n", "'abc'", 2, "valid int", id="int-tag"),
        pytest.param(
            "version: 0\nlook:\n  shadow: !!bool maybe\n", "'maybe'", 3, "valid bool", id="bool-tag"
        ),
        pytest.param(
            "version: 0\nlook:\n  size: !!int\n", "''", 3, "valid int", id="empty-int-tag"
        ),
    ],
)
def test_a_value_its_tag_cannot_hold_is_a_parse_error_naming_it_and_its_line(
    tmp_path: Path, text: str, value: str, line: int, kind: str
) -> None:
    """Well-formed YAML, so the message says what is wrong with the value, not the syntax."""
    reel, error = _load_file(tmp_path, text)

    message = str(error)
    assert message.startswith(f"{reel}: invalid value: {value} on line {line}, column ")
    assert f" is not a {kind}" in message
    assert "malformed YAML" not in message


def test_an_impossible_date_carries_the_reason_python_gives(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as reason:
        date(2024, 2, 30)

    reel, error = _load_file(tmp_path, BARBECUE)

    assert str(error) == (
        f"{reel}: invalid value: '2024-02-30' on line 4, column 9 is not a real date"
        f" ({reason.value})"
    )


def test_a_builtin_reason_that_only_describes_ruamel_is_left_out(tmp_path: Path) -> None:
    """``!!bool maybe`` fails as a KeyError whose text is only ``'maybe'`` again."""
    reel, error = _load_file(tmp_path, "version: 0\nlook:\n  shadow: !!bool maybe\n")

    assert str(error) == f"{reel}: invalid value: 'maybe' on line 3, column 11 is not a valid bool"


def test_loads_document_reports_an_impossible_date_as_a_parse_error() -> None:
    with pytest.raises(ReelParseError, match=r"^<string>: invalid value: '2024-02-30' on line 4"):
        loads_document(BARBECUE)


def test_a_value_ruamel_itself_refuses_is_an_invalid_value_too() -> None:
    """ruamel's own construction errors share the prefix: the YAML is not malformed."""
    with pytest.raises(ReelParseError, match="^<string>: invalid value: failed to construct"):
        loads_document("version: 0\nlook: {n: !!timestamp foo}\n")


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("version: 0\nlook: {n: !!set abc}\n", id="attribute-error"),
        pytest.param("version: 0\nlook:\n  ? {a: [b]}\n  : x\n", id="type-error"),
        pytest.param("? {a: [b]}\n: x\nmetadata: {title: t}\n", id="type-error-at-the-root"),
        # A bare assert in ruamel's omap constructor: an AssertionError with no text.
        pytest.param("!!omap [{version: 0}, {version: 0}]\n", id="empty-assertion-at-the-root"),
    ],
)
def test_no_other_builtin_error_escapes_the_load_step(text: str) -> None:
    """Whatever ruamel raises, the reason after the prefix is never empty."""
    with pytest.raises(ReelParseError, match=r"^<string>: (invalid value|malformed YAML): \S"):
        loads_document(text)


#: An integer too long to print in decimal (about 6000 digits). Written in decimal, ruamel
#: refuses it (Python's int-to-str digit limit); written in hex it loaded, and every message,
#: fingerprint or JSON body that printed it failed with a bare ValueError.
UNPRINTABLE_INT = "0x" + "f" * 5000


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(f"version: {UNPRINTABLE_INT}\n", id="version"),
        pytest.param(f"version: 0\nsort: {{method: {UNPRINTABLE_INT}}}\n", id="sort-method"),
        pytest.param(
            f"version: 0\nchapters: [{{name: '', clips: [{UNPRINTABLE_INT}]}}]\n",
            id="clip-reference",
        ),
        pytest.param(f"version: 0\nignore: [{UNPRINTABLE_INT}]\n", id="ignore"),
        pytest.param(
            f"version: 0\nchapters: [{{name: '', clips: [a.mp4]}}]\n"
            f"clips: {{a.mp4: {{trims: [{{in: -{UNPRINTABLE_INT}, out: 1}}]}}}}\n",
            id="negative-trim",
        ),
        pytest.param(
            f"version: 0\nchapters: [{{name: '', clips: [a.mp4]}}]\n"
            f"clips: {{a.mp4: {{rotate: {UNPRINTABLE_INT}}}}}\n",
            id="rotate",
        ),
        pytest.param(f"version: 0\nlook: {{n: {UNPRINTABLE_INT}}}\n", id="look"),
        pytest.param(f"sort: {{method: {UNPRINTABLE_INT}}}\n", id="legacy-sort-method"),
    ],
)
def test_an_integer_too_long_to_print_is_an_invalid_value(text: str) -> None:
    with pytest.raises(ReelParseError, match=r"^<string>: invalid value: '-?0xfff") as exc:
        loads_document(text)
    assert "is not a valid int (" in str(exc.value)


@pytest.mark.parametrize("field", ["in", "out"])
def test_a_trim_time_too_large_for_a_float_is_a_parse_error(field: str) -> None:
    """A 400-digit integer prints fine but is past the largest float (about 1.8e308)."""
    times = {"in": "0", "out": "1"}
    times[field] = "9" * 400
    text = (
        "version: 0\nchapters: [{name: '', clips: [a.mp4]}]\n"
        f"clips: {{a.mp4: {{trims: [{{in: {times['in']}, out: {times['out']}}}]}}}}\n"
    )

    with pytest.raises(
        ReelParseError, match=rf"trims\[0\]\.{field}: time out of range, got 9{{400}}$"
    ):
        loads_document(text)


def test_a_real_leap_day_still_loads_as_a_date() -> None:
    doc = loads_document("version: 0\nmetadata:\n  date: 2024-02-29\n")
    assert doc.metadata.date == date(2024, 2, 29)


def test_a_quoted_impossible_date_keeps_its_validation_message() -> None:
    with pytest.raises(ReelParseError, match=r"metadata\.date: invalid date '2024-02-30'"):
        loads_document("version: 0\nmetadata:\n  date: '2024-02-30'\n")


def test_an_escape_that_names_no_character_is_a_parse_error(tmp_path: Path) -> None:
    """ruamel's scanner fails with no node to blame: the file and the reader's reason."""
    reel, error = _load_file(tmp_path, ESCAPE_BEYOND_UNICODE)

    assert str(error).startswith(f"{reel}: malformed YAML: ")
    assert "chr()" in str(error)


@pytest.mark.parametrize(
    "depth",
    [
        # Deep enough to exhaust the stack while constructing: no single node is at fault.
        pytest.param(300, id="too-deep-to-construct"),
        # Deeper still: the stack runs out while composing, before construction starts.
        pytest.param(3000, id="too-deep-to-compose"),
    ],
)
def test_a_document_nested_too_deep_is_a_parse_error(tmp_path: Path, depth: int) -> None:
    reel, error = _load_file(tmp_path, "version: 0\nlook: " + "[" * depth + "]" * depth + "\n")

    assert str(error).startswith(f"{reel}: nested too deeply to load (")
    assert "maximum recursion depth exceeded" in str(error)


def test_a_reel_yaml_that_is_not_utf8_is_a_parse_error(tmp_path: Path) -> None:
    latin1 = "version: 0\nmetadata:\n  title: Kräftskiva\n".encode("latin-1")

    reel, error = _load_file(tmp_path, latin1)

    assert str(error) == f"{reel}: not UTF-8 text (invalid continuation byte at byte 32)"


@pytest.mark.parametrize(
    ("second", "written"),
    [
        ("{in: 2, out: 5}", [(1.0, 3.0), (2.0, 5.0)]),
        ("{in: 3, out: 5}", [(1.0, 3.0), (3.0, 5.0)]),
    ],
    ids=["overlap", "touch"],
)
def test_overlapping_or_touching_cuts_are_accepted_as_written(
    second: str, written: list[tuple[float, float]]
) -> None:
    """The document keeps every cut as written; the render joins them (not an error)."""
    text = (
        "version: 0\nchapters: [{name: '', clips: [a.mp4]}]\n"
        f"clips: {{a.mp4: {{trims: [{{in: 1, out: 3}}, {second}]}}}}\n"
    )

    doc = loads_document(text)

    assert [(t.start, t.end) for t in doc.clips["a.mp4"].trims] == written


def test_an_invalid_cut_beside_an_overlap_still_names_its_index() -> None:
    text = (
        "version: 0\nchapters: [{name: '', clips: [a.mp4]}]\n"
        "clips: {a.mp4: {trims: [{in: 1, out: 3}, {in: 2, out: 2}]}}\n"
    )

    with pytest.raises(ReelParseError, match=r"trims\[1\]"):
        loads_document(text)


# --------------------------------------------------------------------------- #
# Value validation: finite times, integer version, unique ignore, string look
# keys, UTF-8 encodable text
# --------------------------------------------------------------------------- #


def _trim_doc(span: str) -> str:
    return (
        "version: 0\nchapters: [{name: '', clips: [a.mp4]}]\n"
        f"clips: {{a.mp4: {{trims: [{span}]}}}}\n"
    )


@pytest.mark.parametrize(
    ("span", "field"),
    [
        ("{in: .nan, out: 5}", "in"),
        ("{in: 0, out: .nan}", "out"),
        ("{in: .nan, out: .nan}", "in"),
        ("{in: 1, out: .inf}", "out"),
        ("{in: .inf, out: 5}", "in"),
    ],
)
def test_a_non_finite_trim_time_is_a_parse_error(span: str, field: str) -> None:
    with pytest.raises(ReelParseError, match=rf"a\.mp4.*trims\[0\]\.{field}: time must be finite"):
        loads_document(_trim_doc(span))


def test_negative_infinity_is_still_a_negative_time() -> None:
    with pytest.raises(ReelParseError, match="non-negative"):
        loads_document(_trim_doc("{in: -.inf, out: 5}"))


@pytest.mark.parametrize("span", ["{in: &t true, out: 5}", "{in: 1, out: &t false}"])
def test_an_anchored_boolean_is_not_a_trim_time(span: str) -> None:
    with pytest.raises(ReelParseError, match="expected a number of seconds"):
        loads_document(_trim_doc(span))


def test_a_finite_trim_still_loads() -> None:
    doc = loads_document(_trim_doc("{in: 0, out: 3.2}"))

    assert (doc.clips["a.mp4"].trims[0].start, doc.clips["a.mp4"].trims[0].end) == (0.0, 3.2)


@pytest.mark.parametrize(
    "version", ["false", "0.0", "'0'", "", "null", "true", "99", "&v false", "&v true"]
)
def test_a_version_that_is_not_the_integer_zero_is_rejected(version: str) -> None:
    with pytest.raises(ReelParseError, match="unsupported version"):
        loads_document(f"version: {version}\n")


def test_version_zero_loads() -> None:
    assert loads_document("version: 0\n").version == 0


@pytest.mark.parametrize("ignore", ["[x.mp4, y.mp4, x.mp4]", "[x.mp4, ./x.mp4]"])
def test_a_duplicate_ignore_entry_is_a_parse_error(ignore: str) -> None:
    with pytest.raises(
        ReelParseError,
        match=r"ignore\[(2|1)\]: duplicate ignore entry 'x.mp4' \(first at ignore\[0\]\)",
    ):
        loads_document(f"version: 0\nignore: {ignore}\n")


def test_distinct_ignore_entries_still_load() -> None:
    assert loads_document("version: 0\nignore: [x.mp4, y.mp4, sub/x.mp4]\n").ignore == (
        "x.mp4",
        "y.mp4",
        "sub/x.mp4",
    )


@pytest.mark.parametrize(
    ("look", "where", "key", "kind"),
    [
        ("{2024-01-01: x}", "look", "2024-01-01", "a date"),
        ("{1: a, b: c}", "look", "1", "an integer"),
        ("{layers: [{1: x}]}", r"look\.layers\[0\]", "1", "an integer"),
        ("{a: {b: {true: 1}}}", r"look\.a\.b", "True", "a boolean"),
    ],
)
def test_a_non_string_look_key_is_a_parse_error(look: str, where: str, key: str, kind: str) -> None:
    with pytest.raises(ReelParseError, match=rf"{where}: key {key} is {kind}, not a string"):
        loads_document(f"version: 0\nlook: {look}\n")


def test_a_non_string_key_in_a_legacy_title_card_is_a_parse_error() -> None:
    with pytest.raises(ReelParseError, match=r"look: key 1 is an integer"):
        loads_document("title_card: {1: a}\n")


def test_quoted_and_unknown_look_keys_still_load_and_round_trip() -> None:
    text = "version: 0\nlook:\n  '2024-01-01': x\n  unknown_future_key: 42\n"
    doc = loads_document(text)

    assert doc.look == {"2024-01-01": "x", "unknown_future_key": 42}
    assert dumps_document(doc) == text


def test_the_editorial_hash_of_a_valid_document_is_unchanged() -> None:
    """Literal taken from main before the value checks existed: valid documents hash alike."""
    assert (
        editorial_hash(loads_document(VALID_DOC))
        == "c700787458200777f425cc8e2a87656dc64835d5388f5dfc81f2ffaf1ae5163a"
    )


@pytest.mark.parametrize(
    ("text", "where"),
    [
        ('version: 0\nmetadata: {title: "Fest \\ud800"}\n', "metadata.title"),
        ('version: 0\nlook: {font: "x\\ud800"}\n', "look.font"),
        ('version: 0\nlook: {"a\\ud800": 1}\n', "look"),
        (
            'version: 0\nchapters: [{name: "", clips: ["a\\ud800.mp4"]}]\n',
            r"chapters\[0\]\.clips\[0\]",
        ),
        ('version: 0\nmetadata: {description: "x\\ud800y"}\n', "metadata.description"),
        ('title: "x\\ud800"\n', "title"),
        ('"k\\ud800": 1\n', r"\['k"),
    ],
)
def test_a_lone_surrogate_is_a_parse_error_naming_its_path(text: str, where: str) -> None:
    with pytest.raises(ReelParseError, match=rf"{where}.*lone surrogate") as exc:
        loads_document(text)

    str(exc.value).encode("utf-8")  # the message itself can be printed


def test_a_character_beyond_the_bmp_loads() -> None:
    doc = loads_document('version: 0\nmetadata: {title: "Fest \\U0001F386"}\n')

    assert doc.metadata.title == "Fest \U0001f386"


PLACEHOLDER = "<unicode string>"


@pytest.mark.parametrize(
    ("text", "line"),
    [
        pytest.param('version: 0\ntitle: "\\x"\n', 2, id="scanner-error"),
        pytest.param("version: 0\ntitle: x\n\t- a\n", 3, id="tab-starting-a-line"),
        pytest.param("version: 0\ntitle: [a\nb: : :\n", 3, id="unclosed-flow-sequence"),
        pytest.param("version: 0\ntitle: a\ntitle: b\n", 3, id="repeated-top-level-key"),
    ],
)
def test_a_positioned_yaml_error_names_the_document_not_the_stand_in(
    tmp_path: Path, text: str, line: int
) -> None:
    path = tmp_path / "reel.yaml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ReelParseError) as from_file:
        load_document(path)
    with pytest.raises(ReelParseError) as from_text:
        loads_document(text, source="draft-reel")

    for error, source in ((from_file, str(path)), (from_text, "draft-reel")):
        message = str(error.value)
        assert PLACEHOLDER not in message
        assert f'in "{source}", line' in message
        assert f", line {line}," in message


def test_a_renamed_excerpt_leaves_the_documents_own_text_alone() -> None:
    """Only the reader's stream name is replaced, never a copy of it inside the document."""
    text = f'version: 0\ntitle: "{PLACEHOLDER} \\x"\n'

    with pytest.raises(ReelParseError) as exc:
        loads_document(text, source="draft-reel")

    assert 'in "draft-reel", line 2' in str(exc.value)
    assert PLACEHOLDER in str(exc.value)  # the excerpt of the user's own line


def test_a_scanner_failure_without_a_position_says_how_far_reading_got(tmp_path: Path) -> None:
    path = tmp_path / "reel.yaml"
    path.write_text('version: 0\nmetadata:\n  title: x\n  extra: "\\U00110000"\n', encoding="utf-8")

    with pytest.raises(ReelParseError) as exc:
        load_document(path)

    message = str(exc.value)
    assert message.startswith(f"{path}: malformed YAML: chr() arg not in range")
    assert "reading got as far as line 4" in message


def test_a_valid_document_is_never_scanned_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(self: object, text: str) -> None:
        raise AssertionError("the re-scan ran for a document that loads")

    monkeypatch.setattr("auto_reel_ng.reel.parser.YAML.scan", refuse)

    assert loads_document(VALID_DOC).metadata.title == "Midsummer"


def test_a_failing_rescan_still_raises_the_original_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(self: object, text: str) -> None:
        raise RuntimeError("scan is broken")

    monkeypatch.setattr("auto_reel_ng.reel.parser.YAML.scan", broken)

    with pytest.raises(ReelParseError, match=r"x\.yaml: malformed YAML: chr\(\) arg") as exc:
        loads_document('version: 0\ntitle: "\\U00110000"\n', source="x.yaml")

    assert "reading got as far as" not in str(exc.value)


def test_a_document_nested_too_deeply_is_named_as_such(tmp_path: Path) -> None:
    path = tmp_path / "reel.yaml"
    path.write_text("version: 0\ntitle: " + "[" * 250 + "]" * 250 + "\n", encoding="utf-8")

    with pytest.raises(ReelParseError) as exc:
        load_document(path)

    message = str(exc.value)
    assert message.startswith(f"{path}: nested too deeply to load")
    assert "maximum recursion depth exceeded" in message
    assert "line" not in message.replace(str(path), "")


def test_a_document_nested_fifty_deep_still_loads() -> None:
    text = "version: 0\nlook: {future: " + "[" * 50 + "]" * 50 + "}\n"

    assert loads_document(text).version == 0


# --------------------------------------------------------------------------- #
# chapter names: unpadded, non-blank, unique ignoring case (chapter-name-rules-engine)
# --------------------------------------------------------------------------- #


def _chapters_text(*names: str) -> str:
    """A ``reel.yaml`` listing one empty chapter per name, each name a JSON-quoted scalar."""
    import json

    body = "".join(f"  - name: {json.dumps(name)}\n    clips: []\n" for name in names)
    return f"version: 0\nchapters:\n{body}"


@pytest.mark.parametrize("blank", ["  ", "\t", "   "])
def test_a_blank_chapter_name_is_refused(blank: str) -> None:
    with pytest.raises(ReelParseError, match=r"chapters\[1\]: blank chapter name"):
        loads_document(_chapters_text("", blank))


@pytest.mark.parametrize("padded", [" Party", "Party ", "\tParty"])
def test_a_padded_chapter_name_is_refused_and_not_trimmed(padded: str) -> None:
    with pytest.raises(ReelParseError, match=r"chapters\[0\].*leading or trailing whitespace") as e:
        loads_document(_chapters_text(padded))
    assert repr(padded) in str(e.value)


def test_names_equal_ignoring_case_are_duplicates_naming_both() -> None:
    with pytest.raises(ReelParseError) as caught:
        loads_document(_chapters_text("Party", "party"))
    message = str(caught.value)
    assert "chapters[1]" in message and "chapters[0]" in message
    assert "'Party'" in message and "'party'" in message
    assert "duplicate chapter name" in message and "ignoring case" in message


def test_case_folding_follows_str_casefold() -> None:
    # str.lower() leaves the sharp s alone; str.casefold() folds it to "ss".
    with pytest.raises(ReelParseError, match="duplicate chapter name"):
        loads_document(_chapters_text("Straße", "STRASSE"))


def test_exact_duplicate_chapter_names_and_two_default_chapters_are_still_refused() -> None:
    with pytest.raises(ReelParseError, match="duplicate chapter name 'Reception'"):
        loads_document(_chapters_text("Reception", "Reception"))
    with pytest.raises(ReelParseError, match=r"chapters\[1\]: duplicate chapter name ''"):
        loads_document(_chapters_text("", ""))


def test_the_default_chapter_and_ordinary_names_load_unchanged() -> None:
    document = loads_document(_chapters_text("", "Reception", "Dag 2", "Party night"))
    assert [chapter.name for chapter in document.chapters] == [
        "",
        "Reception",
        "Dag 2",
        "Party night",
    ]
