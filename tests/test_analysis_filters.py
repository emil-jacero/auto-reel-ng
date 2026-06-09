"""Pure golden-string tests for the two detection passes' ffmpeg args (task 2.x)."""

from __future__ import annotations

from auto_reel_ng.analysis.filters import (
    pass1_args,
    pass1_filter,
    pass2_args,
    pass2_filter,
)
from auto_reel_ng.analysis.models import AnalysisConfig


def test_pass1_filter_defaults() -> None:
    """Pass 1 chains blackdetect then freezedetect with exp-005 default thresholds."""
    assert (
        pass1_filter(AnalysisConfig())
        == "blackdetect=d=2.0:pic_th=0.98:pix_th=0.1,freezedetect=n=0.003:d=2.0"
    )


def test_pass2_filter_defaults() -> None:
    """Pass 2 negates then blackdetects for white, sharing the black thresholds."""
    assert pass2_filter(AnalysisConfig()) == "negate,blackdetect=d=2.0:pic_th=0.98:pix_th=0.1"


def test_pass1_args_full_vector() -> None:
    """The full pass-1 arg vector decodes one input, runs the chain, muxes nothing."""
    assert pass1_args("/clips/a.mp4", AnalysisConfig()) == [
        "-hide_banner",
        "-nostats",
        "-i",
        "/clips/a.mp4",
        "-an",
        "-vf",
        "blackdetect=d=2.0:pic_th=0.98:pix_th=0.1,freezedetect=n=0.003:d=2.0",
        "-f",
        "null",
        "-",
    ]


def test_pass2_args_full_vector() -> None:
    """The full pass-2 arg vector carries the negate,blackdetect chain."""
    assert pass2_args("/clips/a.mp4", AnalysisConfig()) == [
        "-hide_banner",
        "-nostats",
        "-i",
        "/clips/a.mp4",
        "-an",
        "-vf",
        "negate,blackdetect=d=2.0:pic_th=0.98:pix_th=0.1",
        "-f",
        "null",
        "-",
    ]


def test_overridden_thresholds_change_the_args() -> None:
    """Overriding every threshold is reflected verbatim in the emitted strings."""
    config = AnalysisConfig(pic_th=0.9, pix_th=0.2, freeze_noise=0.001, min_duration=5.0)
    assert pass1_filter(config) == (
        "blackdetect=d=5.0:pic_th=0.9:pix_th=0.2,freezedetect=n=0.001:d=5.0"
    )
    assert pass2_filter(config) == "negate,blackdetect=d=5.0:pic_th=0.9:pix_th=0.2"
