"""The levers under test: `auto-reel worker` with the proxy x264 encode capped to N threads, or with
the proxy job's yield to running renders switched off (the control of the re-run).

Disposable: wraps the engine's command builder for this process only (experiment 007)."""

import dataclasses
import os
import sys

from auto_reel_ng.cli.main import main
from auto_reel_ng.proxies import EncodePath
from auto_reel_ng.proxies import ensure as ensure_module
from auto_reel_ng.scheduler.proxy_job import ProxyJobHandler

THREADS = os.environ.get("PROXY_X264_THREADS", "")
FORCE_CPU = os.environ.get("PROXY_FORCE_CPU") == "1"
_build = ensure_module.build_proxy_command


def capped(*args, **kwargs):  # type: ignore[no-untyped-def]
    if FORCE_CPU:  # diagnostic: decode and scale on the CPU, not the GPU (no hardware proxy path)
        kwargs["path"] = EncodePath.CPU
    command = _build(*args, **kwargs)
    if not THREADS:
        return command
    argv = list(command.args)
    at = argv.index("-movflags")  # output options come before this
    argv[at:at] = ["-threads", THREADS]
    return dataclasses.replace(command, args=tuple(argv))


ensure_module.build_proxy_command = capped
if os.environ.get("PROXY_NO_YIELD") == "1":  # the control: the proxy job never yields to a render
    ProxyJobHandler._render_running = lambda self: False  # type: ignore[method-assign]
raise SystemExit(main(sys.argv[1:]))
