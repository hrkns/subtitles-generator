# Test Coverage and Gap Report

Date: 2026-04-28

## Scope

This report summarizes the current state of the local automated regression coverage before starting the input-pipeline refactor for automatic audio cleaning.

It captures:

- what the current test suite covers
- what still remains outside that scope
- which gaps are intentional versus accidental
- follow-up work that should happen next

## Current State

The current local test suite contains these modules:

- `tests/test_time_utils.py`
- `tests/test_generate_output_helpers.py`
- `tests/test_generate_output_content.py`
- `tests/test_process_input_helpers.py`
- `tests/test_runtime_orchestration.py`
- `tests/test_media_model_boundaries.py`
- `tests/test_gui_behaviour.py`
- `tests/test_parser_and_error_paths.py`

Current command:

```bash
python -m pytest
```

Current observed result:

- `76 passed`
- total coverage: `90%`

Current coverage summary from the latest run:

| Module | Coverage | Notes |
| --- | ---: | --- |
| `process_input.py` | 98% | Core parsing, orchestration, and mocked media/model boundaries are heavily covered. |
| `generate_output.py` | 97% | Helper logic, assembly, merge behavior, and logged failure paths are covered. |
| `gui.py` | 90% | Mocked GUI behavior is covered, but some bootstrap and edge branches remain. |
| `main.py` | 90% | Main control flow is covered, but not every edge branch. |
| `modules/chronometer.py` | 19% | No direct unit tests yet. |

## What The Current Suite Achieves

### Runtime Orchestration

Covered:

- CLI argument parsing
- `process_input()` flow selection
- `generate_output()` wrapper behavior
- `main.py` mainline flow and cleanup

### Media and Model Boundaries

Covered with mocks:

- MP3 validation
- MIME-based video detection
- video audio extraction behavior
- segment export
- Whisper load/transcribe invocation
- JSON output writing
- transcription exception wrapping

### GUI Behavior

Covered with PyQt stubs:

- worker execution and failure handling
- input/output selection behavior
- run and cancel behavior
- close-event handling

### Parser and Error Paths

Covered:

- subtitle parsing round trips
- invalid SRT/time-range parsing behavior
- no-offset filename handling
- checkpoint reordering warnings
- out-of-order and overlapping segment warnings
- logged `process_directory()` failure path

## Remaining Gaps

## 1. Gaps That Are Still Outside The Current Local Test Scope By Design

These were intentionally left out because the goal was a fast, deterministic local regression net.

### Real integration coverage

The current tests do not execute the real external stack end to end:

- real `PyQt5`
- real `python-magic`
- real `moviepy`
- real `pydub`
- real `whisper_timestamped`
- real MP3 or video fixture decoding/transcription

Reason:

- keeping the suite lightweight and reproducible was more important than high-fidelity media integration at this step
- true integration smoke coverage fits better as a later enhancement, not as a prerequisite for the upcoming refactor

### CI and branch protection

The current work is still only local test hardening.

What is still missing here:

- GitHub Actions workflow to run `pytest`
- required status check / branch gate configuration in GitHub

## 2. Gaps Still Visible In Coverage

### `modules/chronometer.py`

Current coverage is only `19%`.

What is missing:

- `seconds_to_formatted_string()` branches
- `Chronometer.start()` / `stop()` lifecycle behavior
- `get_duration()` before start, during run, and after stop
- `print_duration()` output path

Why it is still uncovered:

- the file is not central to the input-cleaning refactor, so it was deprioritized
- existing orchestration tests only touch it indirectly through `main.py`

### `gui.py`

Current coverage is `90%`, which is good, but not complete.

Residual gaps are mostly around:

- module bootstrap block at the bottom of the file
- some empty-selection branches in file dialogs
- some cache fallback branches in `__init__`

Why it is still incomplete:

- GUI tests currently use lightweight stubs rather than a real Qt event loop
- the highest-value interaction paths are covered already

### `main.py`

Current coverage is `90%`.

Residual gaps are mostly around:

- some module bootstrap accounting
- exception-path details inside the `__main__` block

Why it is still incomplete:

- current tests focus on happy-path and version-mode flow
- exception-path assertions were not expanded beyond verifying the main orchestration contract

### Small residual gaps in `process_input.py` and `generate_output.py`

Coverage is already high in both files, but there are still a few missing or partially covered branches.

These are mostly:

- defensive branches with limited practical impact
- minor warning or alternative-flow cases
- edge formatting or branch-only paths

Given current coverage levels of `98%` and `97%`, these are not blockers.

## 3. Previously Confirmed Gap Since Closed

### Temporary segment cleanup on transcription failure

This issue was addressed during the audio-cleaning integration work.

Current behavior:

- `process_audio_segments()` exports temporary segment audio as lossless `temp_segment_1.wav`
- `whisper.transcribe()` failures are wrapped in a `RuntimeError`
- the temporary segment file is removed in a `finally` block before the exception escapes

Why this still matters:

- the temp segment now stays aligned with the lossless working-audio pipeline
- repeated failures no longer leave temporary artifacts behind

Regression coverage:

- `test_process_audio_segments_exports_transcribes_and_writes_json`
- `test_process_audio_segments_wraps_transcription_failures`

## 4. Areas That Are Still Only Partially Asserted

These are not major blockers, but they are still useful follow-up candidates.

### Real subprocess behavior in GUI worker flow

The worker behavior is unit-tested with fake processes, but not with a real subprocess.

### Real CLI invocation through `main.py`

Current orchestration tests call functions directly or use `runpy`, but do not validate a real command-line invocation from the shell.

### Path edge cases

Not every filesystem edge case is covered, for example:

- filename-only output paths
- unusual path separators
- non-ASCII paths

These are lower priority than the current core regression surface.

## Recommended Follow-Up Order

### Immediate next step

1. Implement CI workflow support for `pytest`.

This means:

- create the CI workflow artifacts
- run `pytest` in CI
- make that check the branch gate outside the repository settings once the workflow exists

### Near-term quality follow-up

2. Fix the temporary file leak in `process_audio_segments()` on transcription failure.

This is the most concrete quality issue found while reviewing the remaining gaps.

### Optional coverage improvements

3. Add direct unit tests for `modules/chronometer.py`.
4. Add a few additional GUI bootstrap and empty-selection tests if raising GUI coverage above `90%` is important.
5. Add true integration smoke tests later if the project needs confidence against real media/toolchain behavior.

## Conclusion

The current local test net is strong enough to support the upcoming input-pipeline refactor. The remaining gaps are mostly either:

- intentionally deferred to CI or later
- low-priority residual coverage gaps
- one confirmed cleanup defect in the transcription failure path

That makes CI workflow support the correct next engineering step, with the cleanup defect as the most valuable follow-up issue to keep visible.
