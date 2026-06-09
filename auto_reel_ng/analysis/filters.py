"""Pure ffmpeg argument building for the two detection passes (decision D-AN1).

Kept free of any I/O so the emitted filter strings and full arg vectors can be
tested against golden values without invoking ffmpeg. Two passes are needed because
``negate`` rewrites the stream and cannot share a chain with the un-negated
black/freeze detection (D-AN2): pass 1 runs ``blackdetect``+``freezedetect`` together,
pass 2 runs ``negate,blackdetect`` for white.
"""

from __future__ import annotations

from typing import List

from .models import AnalysisConfig


def _fmt(value: float) -> str:
    """Format a threshold for an ffmpeg filter, dropping a trailing ``.0`` only.

    ``2.0`` -> ``"2.0"`` (ffmpeg accepts it), ``0.1`` -> ``"0.1"``, ``0.003`` ->
    ``"0.003"``. ``str(float)`` already gives stable, minimal forms here, so this is
    just a single seam the golden-string tests can pin.
    """
    return str(value)


def blackdetect_filter(config: AnalysisConfig) -> str:
    """The ``blackdetect`` filter string for ``config`` (used by black and white)."""
    return (
        f"blackdetect=d={_fmt(config.min_duration)}"
        f":pic_th={_fmt(config.pic_th)}"
        f":pix_th={_fmt(config.pix_th)}"
    )


def freezedetect_filter(config: AnalysisConfig) -> str:
    """The ``freezedetect`` filter string for ``config``."""
    return f"freezedetect=n={_fmt(config.freeze_noise)}:d={_fmt(config.min_duration)}"


def pass1_filter(config: AnalysisConfig) -> str:
    """Pass 1 chain: ``blackdetect`` then ``freezedetect`` on the un-negated stream."""
    return f"{blackdetect_filter(config)},{freezedetect_filter(config)}"


def pass2_filter(config: AnalysisConfig) -> str:
    """Pass 2 chain: ``negate`` then ``blackdetect`` to surface white spans."""
    return f"negate,{blackdetect_filter(config)}"


def _detection_args(input_path: str, filter_chain: str) -> List[str]:
    """Common arg vector: decode one input, run ``filter_chain``, discard output.

    ``-an`` drops audio (detectors are video-only) and ``-f null -`` muxes nothing;
    the detector log lines land on stderr, which the runner parses.
    """
    return [
        "-hide_banner",
        "-nostats",
        "-i",
        input_path,
        "-an",
        "-vf",
        filter_chain,
        "-f",
        "null",
        "-",
    ]


def pass1_args(input_path: str, config: AnalysisConfig) -> List[str]:
    """Full ffmpeg args for pass 1 (black + freeze) over ``input_path``."""
    return _detection_args(input_path, pass1_filter(config))


def pass2_args(input_path: str, config: AnalysisConfig) -> List[str]:
    """Full ffmpeg args for pass 2 (white via ``negate,blackdetect``) over ``input_path``."""
    return _detection_args(input_path, pass2_filter(config))
