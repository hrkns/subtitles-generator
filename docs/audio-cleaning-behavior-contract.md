# Audio Cleaning Behavior Contract

This document defines the functional contract for automatic audio cleaning before subtitle generation. It is the reference for implementation work in this branch.

## Goal

The application must let the user choose how input audio is prepared before speech-to-text runs, and it must let the user persist that choice for future executions.

## Supported Cleaning Modes

The application will expose three effective modes:

1. `off`
   - No audio cleaning is applied.
   - The input is only normalized into the internal working format required by the transcription pipeline.

2. `basic`
   - A lightweight cleaning strategy is applied.
   - This mode is optimized for speed and low dependency cost.
   - It is intended to improve noisy speech, not to perform full source separation.

3. `speechbrain`
   - A SpeechBrain-based speech enhancement strategy is applied.
   - This mode is optimized for stronger enhancement quality at higher runtime and dependency cost.
   - It is optional and may be unavailable if its dependencies are not installed.

## Input Processing Contract

Cleaning applies only after the input has been converted into an internal working audio file.

The processing order is:

1. Accept the user input file.
2. If the input is a video file, extract its audio track.
3. Normalize the extracted or original audio into a single internal working format.
4. Apply the selected cleaning mode.
5. Use the cleaned working audio as the source for segmentation and transcription.

The cleaning step must run once per input file, before segment generation.

## Mode Resolution Precedence

The effective cleaning mode for a run is resolved in this order:

1. Explicit per-run user choice.
   - GUI selection made immediately before generation.
   - CLI argument passed for the current execution.

2. Saved user preference.
   - The persisted default cleaning mode from a previous execution.

3. Built-in application default.
   - Default value: `off`.

Per-run selection must override saved configuration without modifying it, unless the user explicitly asks to save the new selection.

## Persistence Contract

The application must persist the cleaning preference independently from the current input and output path values.

The persisted configuration must store at least:

- Default cleaning mode.
- Whether that default should be preselected in future GUI runs.

The user must be able to:

- Use a different mode for one execution only.
- Save the selected mode as the new default for future executions.

## GUI Contract

Before subtitle generation starts, the GUI must provide:

- A cleaning mode selector with `off`, `basic`, and `speechbrain`.
- A control to save the selected mode as the default for future runs.
- A default selection based on the resolved saved preference.

If `speechbrain` is unavailable, the GUI must make that state clear before execution.

## CLI Contract

The CLI must expose:

- A per-run argument for cleaning mode.
- A way to persist the provided cleaning mode as the new default.

The current execution must use the resolved mode even if the persistence step fails.

## Failure Behavior

Failure behavior is explicit and must not silently change modes.

- If `off` is selected, processing continues without cleaning.
- If `basic` is selected and its required dependencies are unavailable, the run fails with a clear actionable error.
- If `speechbrain` is selected and its required dependencies or model assets are unavailable, the run fails with a clear actionable error.
- The application must not silently fall back from `speechbrain` to `basic` or `off`.

Silent fallback can hide quality regressions and make saved preferences unreliable.

## Output Contract

The subtitles generated in a run must be based on the resolved working audio file produced by the selected cleaning mode.

Temporary artifacts created by normalization or cleaning must remain internal implementation details and must not change the user-facing subtitle output path.

## Scope Boundaries For This Feature

This feature does not change:

- Subtitle formatting behavior.
- Subtitle segmentation semantics.
- Merge behavior for existing SRT files.
- Translation behavior.

Those areas may use cleaner input audio indirectly, but their functional contract remains unchanged.
