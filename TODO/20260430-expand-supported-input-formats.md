# Expand Supported Input Formats

## Purpose

Document the work required to expand the set of officially supported input formats beyond the current guaranteed baseline:

- Audio: `.mp3`, `.wav`
- Video: `.mp4`, `.avi`

At the moment, the backend can sometimes accept additional formats when local codec support is present, but that behavior is best-effort only and is not part of the explicit support contract.

## Why This Needs Its Own Work Item

Adding a new input format is not only a GUI filter change. Support has to be aligned across:

- user documentation
- GUI file-picking filters
- CLI/backend validation behavior
- media decoding dependencies and codec availability
- automated tests for successful and failing decode paths

Without that alignment, the project risks advertising formats that only work on some machines.

## Candidate Formats To Evaluate

Audio candidates:

- `.flac`
- `.m4a`
- `.aac`
- `.ogg`
- `.opus`

Video candidates:

- `.mkv`
- `.mov`
- `.webm`
- `.m4v`

These should be treated as candidates, not commitments.

## Implementation Areas

### 1. Define the support policy

Decide which formats are:

- officially supported and tested
- best-effort only
- rejected explicitly

This policy should distinguish file extension support from codec support, since a container may still fail when an unsupported codec is inside it.

### 2. Tighten backend format handling

Current backend behavior relies on:

- Pydub for audio decoding
- `python-magic` for video detection
- MoviePy plus FFmpeg for audio extraction from video

Future work should decide whether to keep the current capability-based behavior or add explicit allowlists for supported extensions and clearer failure messages when codec support is missing.

### 3. Expand GUI filters carefully

When a format becomes officially supported, update the GUI file picker filter so the GUI and CLI expose the same support contract.

### 4. Improve error reporting

Decode failures should tell the user whether the problem is likely:

- an unsupported file type
- a missing codec/backend dependency
- a corrupt media file

### 5. Add regression tests

For each newly supported format, add tests that cover:

- successful input validation
- working-audio normalization
- video detection and extraction path when applicable
- failure behavior when decoding is unavailable
- GUI filter updates when the support is official

### 6. Update docs and installation guidance

README and installation docs should explicitly state:

- the guaranteed supported formats
- any best-effort formats
- codec and FFmpeg expectations
- platform-specific caveats if they are discovered

## Suggested Execution Order

1. Pick one audio format and one video format to evaluate first.
2. Verify they work on the project's supported environments with the current decoding stack.
3. Add backend tests for the successful and failing paths.
4. Update GUI filters only after backend behavior is stable.
5. Update README and installation guidance.
6. Repeat for the next candidate format.

## Acceptance Criteria For Any New Official Format

- The format works through the CLI on a clean supported environment.
- The format is visible in the GUI picker if the GUI is expected to support it.
- The decode path is covered by automated tests.
- Failure messaging is understandable when the required codec is missing.
- The README lists the format explicitly as supported.