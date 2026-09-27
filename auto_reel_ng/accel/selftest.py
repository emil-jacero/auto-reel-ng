"""Empirically self-test candidate hardware operations.

The locked lesson of ``experiments/003-004`` is that ffmpeg listing a filter or encoder
does *not* mean the driver can run it: on AMD, ``overlay_vaapi`` is rejected and
``tonemap_opencl`` faults the GPU outright, yet ``scale_vaapi,pad_vaapi`` works and is
fastest. So every candidate op is *run* on a tiny synthetic clip and classified:

* exit 0                      -> :attr:`OpStatus.WORKING`
* exit 0, output check fails  -> :attr:`OpStatus.UNSUPPORTED` (ran, but wrong; exp 006)
* clean non-zero exit         -> :attr:`OpStatus.UNSUPPORTED` (driver said "no")
* killed by a signal / hang   -> :attr:`OpStatus.FAULTING` (e.g. the GPU page-faulted)

Each probe runs as a child process (ffmpeg itself) with a timeout, so a crash or hang is
contained and recorded, never fatal to detection. A 1-frame ``lavfi`` source keeps the
whole pass fast enough to run at startup (and the result is cached; see ``detection``).
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from ..ffmpeg.runtime import FfmpegRuntime
from .models import Device, OpClass, OpStatus, Vendor

logger = logging.getLogger(__name__)

#: Per-probe wall-clock ceiling; a probe that exceeds it is treated as faulting (hung).
DEFAULT_PROBE_TIMEOUT = 30.0

#: Frame size for the synthetic probe inputs. Must clear every hardware encoder's
#: minimum dimensions or a capable encoder is falsely excluded — notably AMD
#: ``hevc_vaapi`` requires width >= 384 (h264/av1 have no such floor), so a smaller
#: probe (the old 320x240) made HEVC report as unusable on cards that support it.
_PROBE_SIZE = "640x480"

#: Allowed chroma distance from neutral (128) for a padded region to count as black.
_FILL_TOLERANCE = 8

#: codec -> hardware encoder name, per vendor. Only probed if ffmpeg lists the encoder.
_HW_ENCODERS = {
    Vendor.AMD: {"h264": "h264_vaapi", "hevc": "hevc_vaapi", "av1": "av1_vaapi"},
    Vendor.NVIDIA: {"h264": "h264_nvenc", "hevc": "hevc_nvenc", "av1": "av1_nvenc"},
    Vendor.INTEL: {"h264": "h264_qsv", "hevc": "hevc_qsv", "av1": "av1_qsv"},
}


@dataclass(frozen=True)
class Probe:
    """One candidate operation to self-test, identified by a stable ``key``.

    ``expect`` is applied to the probe's stdout after a zero exit: "runs" is not
    "correct" (exp 006), so a probe that checks its output can still fail as
    :attr:`OpStatus.UNSUPPORTED`.
    """

    key: str
    vendor: Vendor
    op: OpClass
    args: tuple[str, ...]
    codec: Optional[str] = None
    expect: Optional[Callable[[str], bool]] = None


@dataclass(frozen=True)
class SyntheticInputs:
    """Tiny generated inputs used by probes; ``hdr`` is None if it couldn't be built."""

    sdr: Path
    hdr: Optional[Path]


def build_synthetic_inputs(runtime: FfmpegRuntime, directory: Path) -> SyntheticInputs:
    """Build 1-frame SDR (and best-effort HDR) clips with ``ffmpeg lavfi``.

    The SDR clip is an h264 file usable as a hardware-decode input; the HDR clip is a
    PQ/bt2020 10-bit file for tonemap probes. If the HDR build fails (e.g. no x265),
    tonemap probes are simply skipped rather than failing detection.
    """
    sdr = directory / "sdr.mp4"
    runtime.run(
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={_PROBE_SIZE}:rate=30",
            "-frames:v",
            "1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(sdr),
        ]
    )

    hdr: Optional[Path] = directory / "hdr.mp4"
    try:
        runtime.run(
            [
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size={_PROBE_SIZE}:rate=30",
                "-frames:v",
                "1",
                "-vf",
                "format=yuv420p10le,setparams=range=tv:color_primaries=bt2020"
                ":color_trc=smpte2084:colorspace=bt2020nc",
                "-c:v",
                "libx265",
                "-pix_fmt",
                "yuv420p10le",
                str(hdr),
            ]
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.debug("Could not build synthetic HDR clip, tonemap probes skipped: %s", exc)
        hdr = None
    return SyntheticInputs(sdr=sdr, hdr=hdr)


def candidate_probes(
    device: Device,
    *,
    inputs: SyntheticInputs,
    encoders: frozenset[str],
    filters: frozenset[str],
) -> list[Probe]:
    """Build the candidate probes for one device, gated by ffmpeg's listings.

    Only operations ffmpeg actually advertises are probed; the self-test then decides
    which of *those* truly work. Vendors without a known recipe yield no probes.
    """
    if device.vendor is Vendor.AMD:
        return _vaapi_probes(device, inputs=inputs, encoders=encoders, filters=filters)
    if device.vendor is Vendor.NVIDIA:
        return _cuda_probes(device, inputs=inputs, encoders=encoders, filters=filters)
    if device.vendor is Vendor.INTEL:
        return _qsv_probes(device, inputs=inputs, encoders=encoders, filters=filters)
    return []


def run_selftest(
    runtime: FfmpegRuntime,
    devices: Sequence[Device],
    *,
    encoders: frozenset[str],
    filters: frozenset[str],
    timeout: float = DEFAULT_PROBE_TIMEOUT,
    extra_probes: Sequence[Probe] = (),
) -> dict[str, OpStatus]:
    """Run every candidate probe and return ``probe.key -> OpStatus``.

    Builds the synthetic inputs once, then runs each probe sequentially (a faulting GPU
    makes parallel hardware probes unsafe). ``extra_probes`` lets callers/tests inject
    additional ops (e.g. a deliberately-bad one) to confirm classification.
    """
    results: dict[str, OpStatus] = {}
    with tempfile.TemporaryDirectory(prefix="auto-reel-selftest-") as tmp:
        inputs = build_synthetic_inputs(runtime, Path(tmp))
        probes: list[Probe] = []
        for device in devices:
            probes.extend(
                candidate_probes(device, inputs=inputs, encoders=encoders, filters=filters)
            )
        probes.extend(extra_probes)

        for probe in probes:
            status = run_probe(runtime, probe, timeout=timeout)
            logger.debug("self-test %s -> %s", probe.key, status.value)
            results[probe.key] = status
    return results


def run_probe(
    runtime: FfmpegRuntime, probe: Probe, *, timeout: float = DEFAULT_PROBE_TIMEOUT
) -> OpStatus:
    """Run a single probe in a child process and classify the result.

    ffmpeg is itself the child process, so a GPU fault that kills it (signal exit) or a
    hang (timeout) is contained here and reported as :attr:`OpStatus.FAULTING`.
    """
    cmd = [runtime.ffmpeg_path, "-hide_banner", "-nostdin", "-y", *probe.args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        return OpStatus.FAULTING
    if result.returncode == 0:
        if probe.expect is not None and not probe.expect(result.stdout):
            logger.info(
                "self-test %s ran but its output check failed: %s",
                probe.key,
                result.stdout.strip() or "<no output>",
            )
            return OpStatus.UNSUPPORTED
        return OpStatus.WORKING
    if result.returncode < 0:
        # Negative return code = terminated by a signal (e.g. SIGABRT from a GPU fault).
        return OpStatus.FAULTING
    return OpStatus.UNSUPPORTED


def black_fill(stdout: str) -> bool:
    """True when every ``signalstats`` chroma reading in ``stdout`` is neutral (black).

    Black is chroma 128 in both the limited and the full value range; the faulty
    ``pad_vaapi`` fill on Mesa is all-zero YUV, chroma 0 (exp 006). No reading at all
    counts as a failure: an unmeasured fill is not a verified one.
    """
    readings = [
        float(value) for value in re.findall(r"lavfi\.signalstats\.[UV]AVG=([0-9.]+)", stdout)
    ]
    return bool(readings) and all(abs(value - 128) <= _FILL_TOLERANCE for value in readings)


# -- per-vendor candidate recipes -------------------------------------------


def _encode_probes(device: Device, encoders: frozenset[str], hwupload: str) -> list[Probe]:
    """Encoder probes shared in shape across vendors; ``hwupload`` is the upload snippet."""
    probes: list[Probe] = []
    for codec, encoder in _HW_ENCODERS[device.vendor].items():
        if encoder not in encoders:
            continue
        probes.append(
            Probe(
                key=f"{device.vendor.value}.encode.{codec}",
                vendor=device.vendor,
                op=OpClass.ENCODE,
                codec=codec,
                args=(
                    "-f",
                    "lavfi",
                    "-i",
                    f"testsrc2=size={_PROBE_SIZE}:rate=30",
                    "-frames:v",
                    "1",
                    "-vf",
                    hwupload,
                    "-c:v",
                    encoder,
                    "-f",
                    "null",
                    "-",
                ),
            )
        )
    return probes


def _vaapi_probes(
    device: Device,
    *,
    inputs: SyntheticInputs,
    encoders: frozenset[str],
    filters: frozenset[str],
) -> list[Probe]:
    """AMD/VAAPI candidate probes (grounded in exp 003/004)."""
    node = device.render_node or "/dev/dri/renderD128"
    sdr = str(inputs.sdr)
    decode = ("-hwaccel", "vaapi", "-hwaccel_device", node, "-hwaccel_output_format", "vaapi")
    probes: list[Probe] = [
        Probe(
            key=f"{device.vendor.value}.decode",
            vendor=device.vendor,
            op=OpClass.DECODE,
            args=(
                *decode,
                "-i",
                sdr,
                "-vf",
                "hwdownload,format=nv12",
                "-frames:v",
                "1",
                "-f",
                "null",
                "-",
            ),
        )
    ]
    if "scale_vaapi" in filters and "pad_vaapi" in filters:
        probes.append(
            Probe(
                key=f"{device.vendor.value}.normalize",
                vendor=device.vendor,
                op=OpClass.NORMALIZE,
                args=(
                    *decode,
                    "-i",
                    sdr,
                    "-vf",
                    "scale_vaapi=w=1920:h=1080:force_original_aspect_ratio=decrease,"
                    "pad_vaapi=w=1920:h=1080:x=(ow-iw)/2:y=(oh-ih)/2:color=black,"
                    "hwdownload,format=nv12",
                    "-frames:v",
                    "1",
                    "-f",
                    "null",
                    "-",
                ),
            )
        )
        # Scale a 64x36 frame into 64x64 so a padded band exists, then read the top of
        # that band back. The normalize probe above proves the op runs; this one proves
        # its fill is the requested colour (exp 006: Mesa paints all-zero YUV, green).
        probes.append(
            Probe(
                key=f"{device.vendor.value}.pad_fill",
                vendor=device.vendor,
                op=OpClass.NORMALIZE,
                args=(
                    "-init_hw_device",
                    f"vaapi=va:{node}",
                    "-filter_hw_device",
                    "va",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=white:size=64x36",
                    "-frames:v",
                    "1",
                    "-vf",
                    "format=nv12,hwupload,"
                    "scale_vaapi=w=64:h=64:force_original_aspect_ratio=decrease,"
                    "pad_vaapi=w=64:h=64:x=(ow-iw)/2:y=(oh-ih)/2:color=black,"
                    "hwdownload,format=nv12,crop=64:8:0:0,signalstats,"
                    "metadata=mode=print:file=-",
                    "-f",
                    "null",
                    "-",
                ),
                expect=black_fill,
            )
        )
    if "overlay_vaapi" in filters:
        probes.append(
            Probe(
                key=f"{device.vendor.value}.overlay",
                vendor=device.vendor,
                op=OpClass.OVERLAY,
                args=(
                    *decode,
                    "-i",
                    sdr,
                    "-i",
                    sdr,
                    "-filter_complex",
                    "[0:v][1:v]overlay_vaapi",
                    "-frames:v",
                    "1",
                    "-f",
                    "null",
                    "-",
                ),
            )
        )
    if inputs.hdr is not None and "tonemap_vaapi" in filters:
        probes.append(
            Probe(
                key=f"{device.vendor.value}.tonemap",
                vendor=device.vendor,
                op=OpClass.TONEMAP,
                args=(
                    *decode,
                    "-i",
                    str(inputs.hdr),
                    "-vf",
                    "tonemap_vaapi=format=nv12,hwdownload,format=nv12",
                    "-frames:v",
                    "1",
                    "-f",
                    "null",
                    "-",
                ),
            )
        )
    upload = "format=nv12,hwupload"
    enc = [
        Probe(
            key=p.key,
            vendor=p.vendor,
            op=p.op,
            codec=p.codec,
            args=("-init_hw_device", f"vaapi=va:{node}", "-filter_hw_device", "va", *p.args),
        )
        for p in _encode_probes(device, encoders, upload)
    ]
    return probes + enc


def _cuda_probes(
    device: Device,
    *,
    inputs: SyntheticInputs,
    encoders: frozenset[str],
    filters: frozenset[str],
) -> list[Probe]:
    """NVIDIA/CUDA candidate probes (best-guess, unverified on this host)."""
    sdr = str(inputs.sdr)
    decode = ("-hwaccel", "cuda", "-hwaccel_output_format", "cuda")
    probes: list[Probe] = [
        Probe(
            key=f"{device.vendor.value}.decode",
            vendor=device.vendor,
            op=OpClass.DECODE,
            args=(
                *decode,
                "-i",
                sdr,
                "-vf",
                "hwdownload,format=nv12",
                "-frames:v",
                "1",
                "-f",
                "null",
                "-",
            ),
        )
    ]
    if "scale_cuda" in filters:
        probes.append(
            Probe(
                key=f"{device.vendor.value}.normalize",
                vendor=device.vendor,
                op=OpClass.NORMALIZE,
                args=(
                    *decode,
                    "-i",
                    sdr,
                    "-vf",
                    "scale_cuda=w=1920:h=1080,hwdownload,format=nv12,pad=1920:1080",
                    "-frames:v",
                    "1",
                    "-f",
                    "null",
                    "-",
                ),
            )
        )
    if "overlay_cuda" in filters:
        probes.append(
            Probe(
                key=f"{device.vendor.value}.overlay",
                vendor=device.vendor,
                op=OpClass.OVERLAY,
                args=(
                    *decode,
                    "-i",
                    sdr,
                    "-i",
                    sdr,
                    "-filter_complex",
                    "[0:v][1:v]overlay_cuda",
                    "-frames:v",
                    "1",
                    "-f",
                    "null",
                    "-",
                ),
            )
        )
    # NVENC accepts system-memory frames directly, no hwupload needed.
    enc = _encode_probes(device, encoders, "format=nv12")
    return probes + enc


def _qsv_probes(
    device: Device,
    *,
    inputs: SyntheticInputs,
    encoders: frozenset[str],
    filters: frozenset[str],
) -> list[Probe]:
    """Intel/QSV candidate probes (best-guess, unverified on this host)."""
    sdr = str(inputs.sdr)
    decode = ("-hwaccel", "qsv", "-hwaccel_output_format", "qsv")
    probes: list[Probe] = [
        Probe(
            key=f"{device.vendor.value}.decode",
            vendor=device.vendor,
            op=OpClass.DECODE,
            args=(
                *decode,
                "-i",
                sdr,
                "-vf",
                "hwdownload,format=nv12",
                "-frames:v",
                "1",
                "-f",
                "null",
                "-",
            ),
        )
    ]
    if "vpp_qsv" in filters:
        # vpp_qsv scales+crops only (research §4); pad happens on CPU after a download.
        probes.append(
            Probe(
                key=f"{device.vendor.value}.normalize",
                vendor=device.vendor,
                op=OpClass.NORMALIZE,
                args=(
                    *decode,
                    "-i",
                    sdr,
                    "-vf",
                    "vpp_qsv=w=1920:h=1080,hwdownload,format=nv12,pad=1920:1080",
                    "-frames:v",
                    "1",
                    "-f",
                    "null",
                    "-",
                ),
            )
        )
    if "overlay_qsv" in filters:
        probes.append(
            Probe(
                key=f"{device.vendor.value}.overlay",
                vendor=device.vendor,
                op=OpClass.OVERLAY,
                args=(
                    *decode,
                    "-i",
                    sdr,
                    "-i",
                    sdr,
                    "-filter_complex",
                    "[0:v][1:v]overlay_qsv",
                    "-frames:v",
                    "1",
                    "-f",
                    "null",
                    "-",
                ),
            )
        )
    enc = _encode_probes(device, encoders, "format=nv12,hwupload=extra_hw_frames=16")
    return probes + enc
