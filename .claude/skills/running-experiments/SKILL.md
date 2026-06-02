---
name: running-experiments
description: Use this skill EVERY TIME an experiment or spike is run — a time-boxed test of a concept, tool, library, or approach that starts with a hypothesis and ends with a written report. Triggers on phrases like "run an experiment", "let's spike", "do a spike on", "test whether X works", "proof of concept / POC", "validate the hypothesis that…", "prototype X to see if…", or any throwaway investigation meant to answer a yes/no/which technical question before committing to a design or OpenSpec change. Dictates where experiments live, how they are structured, and the required report format.
metadata:
  author: auto-reel-ng
  version: "1.0"
---

# Running experiments (spikes)

An **experiment** (a.k.a. spike) is a small, time-boxed, **disposable** investigation that answers ONE
technical question. It is NOT production code. Its only durable output is a **report** that records what
was tried and what was learned, so a future OpenSpec change can be written with confidence.

> Golden rule: **a spike that doesn't end in a written report didn't happen.** The code is throwaway;
> the report is the deliverable.

## When this skill applies

Any time you are about to test a concept/tool/approach to reduce uncertainty before designing — e.g.
"does libplacebo scale+pad on VAAPI?", "can we stream-copy concat these clips?", "is library X fast
enough?". If you catch yourself writing throwaway code to answer a question, you are running an
experiment — follow this skill.

This skill does **not** apply to: shipping features, fixing bugs, refactors, or anything whose output is
meant to live in the codebase. Those go through normal work / OpenSpec changes.

## Principles

1. **One hypothesis per experiment.** A falsifiable statement you expect to confirm or refute. If you have
   three questions, run three experiments (they can share a directory's `NNN` group only if truly one topic).
2. **Time-box it.** State a budget (e.g. "≤ 1 hour"). A spike that balloons is a signal to stop and report
   "inconclusive, needs a real change", not to keep going.
3. **Reproducible.** Record the exact commands, inputs, and the **host/environment** they ran on (OS,
   GPU/driver, tool versions). Someone on different hardware must be able to see what you did and why the
   result may differ for them. Prefer **synthetic inputs** (e.g. `ffmpeg lavfi testsrc`, generated files)
   over real media so the spike is self-contained.
4. **Disposable code.** Spike code lives only under the experiment directory. Never wire it into the app.
   It may be ugly. It must be runnable.
5. **Honest verdict.** End with **Confirmed / Refuted / Partial / Inconclusive** — never massage a result.
   A refuted hypothesis is a successful experiment.
6. **Decision-oriented.** The report must end with what this means for the design and the concrete next
   action (which OpenSpec change it unblocks, what to research next, or "dead end — do X instead").

## Where experiments live

```
experiments/
  NNN-short-slug/            # NNN = zero-padded sequence: 001, 002, …
    report.md               # REQUIRED — the deliverable (template below)
    run.sh                  # the spike script(s) — reproducible entry point
    artifacts/              # generated inputs/outputs, logs, screenshots (gitignore large media)
```

- `NNN` is a monotonically increasing number; pick the next unused one.
- Keep the slug short and specific: `002-vaapi-libplacebo-scalepad`, not `002-gpu-test`.
- Commit `report.md` and `run.sh`. Do **not** commit large generated media; keep only small logs/excerpts
  needed to back up the findings.

## Workflow

1. **State the hypothesis** and time-box, then create `experiments/NNN-slug/` and start `report.md` with
   the hypothesis filled in *before* running anything.
2. **Probe the environment** and record it (versions, hardware) into the report.
3. **Run the spike** via `run.sh` using synthetic inputs where possible. Capture commands + key output.
4. **Record results** — raw enough to be convincing (command lines, timings, error messages, ffprobe
   excerpts). Screenshots/logs go in `artifacts/`.
5. **Write the verdict and decision.** Confirmed/Refuted/Partial/Inconclusive + what it unblocks.
6. **Tell the user**: one-paragraph summary + verdict + the next action. Link the report path.

## Report template (`report.md`)

```markdown
# Experiment NNN — <title>

- **Date:** <YYYY-MM-DD>
- **Author:** <who ran it>
- **Time-box:** <e.g. ≤ 1h>   **Status:** <Confirmed | Refuted | Partial | Inconclusive>
- **Unblocks:** <which OpenSpec change / HLD research item, e.g. §8.1, spec #4>

## Hypothesis
<One falsifiable sentence. "We believe that X. We will know we're right if Y.">

## Why this matters
<1–3 sentences: the design decision riding on this.>

## Environment
<OS, kernel, CPU/GPU + driver, tool versions — anything that affects reproducibility.
Note explicitly which results are hardware-specific (e.g. "AMD VAAPI only — NVIDIA untested").>

## Method
<What was built/run. Reference run.sh. Synthetic inputs and how they were generated. Exact commands.>

## Results
<Raw evidence: command lines + relevant output, timings, ffprobe excerpts, errors. Be concrete.>

## Verdict
<Confirmed / Refuted / Partial / Inconclusive — and the reasoning. Call out what was NOT tested.>

## Decision & next action
<What this means for the design. The concrete next step: which spec it unblocks, what to test next,
or the dead-end and the alternative. Cross-vendor caveats if the spike ran on one vendor only.>

## Open questions / follow-ups
<Anything surfaced but out of scope for this spike.>
```

## Anti-patterns

- Running the spike and reporting only in chat → **no.** Write `report.md`.
- "It works!" with no commands/output to back it → not reproducible, not a result.
- Letting spike code leak into `auto-reel_ng/` (the real package) → keep it under `experiments/`.
- Burying a refuted hypothesis or quietly widening scope mid-spike → state it and stop.
- Generalizing a single-vendor result to "all GPUs" → always caveat the hardware you actually tested.
