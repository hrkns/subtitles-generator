# Input Audio Cleaning Improvement Options

Date: 2026-04-30

## Purpose

This document captures the current state of the input audio cleaning feature, why the project chose SpeechBrain for the first heavy backend, what failed during real runtime validation on Windows with Python 3.13, and which future improvement paths remain viable.

It is intended to serve as planning input for a later follow-up change, not as product-facing documentation.

## Current Feature State

The application currently exposes three cleaning modes:

- `off`
- `basic`
- `speechbrain`

The current heavy backend is implemented through SpeechBrain's `SpectralMaskEnhancement` with model source `speechbrain/metricgan-plus-voicebank`.

Important implementation facts:

- the model source is currently hard-coded in `process_input.py`
- the app config structure already contains `speechbrain_strategy_settings.model_source`
- the GUI currently checks SpeechBrain availability in-process through Python imports and validates runtime readiness by calling the backend loader directly
- unavailable heavy backends must fail explicitly instead of silently falling back to `basic` or `off`

## Why SpeechBrain Was Chosen Initially

SpeechBrain was the lowest-friction first choice for an optional heavy backend.

Reasons:

- it already provides ready-to-use inference interfaces for speech enhancement
- the integration shape matched the existing pipeline well: load a model once, enhance one working WAV file, continue with segmentation and transcription
- it fit the product split between a lightweight built-in mode (`basic`) and a heavier optional mode (`speechbrain`)
- it allowed the project to keep the default install small and move the heavy stack into a separate optional installer

In other words, SpeechBrain was chosen because it minimized architecture change while still offering a meaningful quality-oriented enhancement mode.

## What Was Validated And What Failed

The repository-level code integration for SpeechBrain is complete, but the current Windows and Python 3.13 environment exposed real runtime problems.

### Code-Level Issue Identified During Investigation

The GUI originally produced a false negative for SpeechBrain availability because import validation happened inside the PyQt process.

During investigation, a stronger fix was identified and tested outside the current checked-out code by:

- moving dependency probing into a clean subprocess
- moving runtime readiness validation into a clean subprocess
- improving backend error messages so original import and model-load failures are surfaced

That fix is not currently present in this checkout.

Current code status:

- the GUI still performs dependency probing in-process
- the GUI still shows generic unavailability messages rather than the original import failure details
- the backend still reports generic dependency/model-load failures rather than surfacing the original exception text

This means the repository still has two separate concerns:

- a real backend/runtime compatibility problem for the current SpeechBrain model path on this environment
- a known GUI/backend diagnostic weakness that can make troubleshooting less precise

### Runtime Findings In The Current Environment

Environment used during validation:

- Windows
- Python 3.13.1
- project virtual environment at `.venv`

Validated results:

1. `speechbrain 1.1.0 + torch 2.11.0 + torchaudio 2.11.0`
   - dependency import succeeds
   - actual model load for `speechbrain/metricgan-plus-voicebank` fails through the `speechbrain.integrations.k2_fsa` path

2. Installing `k2`
   - installation succeeded superficially
   - runtime import still failed because the wheel could not import `_k2`

3. `speechbrain 1.0.3 + torch 2.10.0 + torchaudio 2.10.0`
   - model path changed, but runtime still failed
   - failure reason: `torchaudio.list_audio_backends()` is missing in the available Python 3.13 build

4. `speechbrain 1.0.3 + torch 2.9.1 + torchaudio 2.9.1`
   - same failure as the 2.10.0 attempt
   - `torchaudio.list_audio_backends()` is still unavailable in this environment

Conclusion:

- straightforward dependency pinning did not produce a validated working SpeechBrain enhancement stack on this Windows and Python 3.13 setup
- the blocker is now model-path and runtime-compatibility specific, not just package-installation specific

## Alternatives While Still Using SpeechBrain

The current branch uses one SpeechBrain path only. The following alternatives remain possible while keeping SpeechBrain as the heavy backend family.

### 1. Switch To `WaveformEnhancement` With `speechbrain/mtl-mimic-voicebank`

Summary:

- still a SpeechBrain-native enhancement path
- small code change compared with the current implementation

Pros:

- preserves the current product model: one optional heavy enhancement mode
- likely reuses the current file-in/file-out pipeline shape with minimal surrounding refactor
- smallest conceptual change from the current implementation

Cons:

- runtime probing in this environment still failed through a `k2`-related import path
- therefore it is not currently a validated escape route on Windows and Python 3.13

Assessment:

- low implementation cost
- low confidence for this environment

### 2. Switch To `SGMSEEnhancement` With `speechbrain/sgmse-voicebank`

Summary:

- still SpeechBrain
- meaningfully different from the current MetricGAN-based path

Pros:

- most plausible SpeechBrain-native non-`k2` direction currently identified
- preserves the existing product concept of a heavier quality-oriented enhancement mode

Cons:

- runtime probing failed because the `sgmse` package is not installed in the current optional dependency set
- requires broadening the optional dependency surface and validating the new stack carefully
- may increase installation complexity and model-download size

Assessment:

- medium implementation cost
- medium technical promise
- best current candidate for a follow-up implementation if the project wants to stay on SpeechBrain

### 3. Use `SepformerSeparation` Instead Of Enhancement

Summary:

- this path loaded successfully during probing with `speechbrain/sepformer-wsj02mix`
- it is source separation, not speech denoising

Pros:

- first SpeechBrain route that was observed loading successfully in the current environment
- keeps the project within the SpeechBrain ecosystem

Cons:

- does not solve the same problem as the current enhancement mode
- would require new product and implementation decisions about which separated source to keep or how to combine outputs
- carries a higher risk of harming subtitle input quality if the wrong source is selected
- increases behavioral complexity relative to the current contract

Assessment:

- technically viable
- weaker product fit for subtitle preprocessing

### 4. Keep SpeechBrain But Run It In A Separate Helper Environment

Summary:

- the main app stays on its current runtime
- SpeechBrain runs in a separately validated environment or helper process

Pros:

- keeps SpeechBrain as the heavy backend
- isolates fragile ML dependencies from the main application runtime
- can target a Python version known to work with the chosen SpeechBrain model path

Cons:

- higher operational and installation complexity
- requires cross-process orchestration and error handling
- adds another environment the project must support and document

Assessment:

- higher implementation cost
- highest chance of keeping SpeechBrain without blocking the main app runtime

### 5. Keep The Current SpeechBrain Path But Restrict Support To A Known-Good Python Version

Summary:

- keep the existing integration shape
- narrow support to a validated runtime such as Python 3.11 or 3.12 if needed

Pros:

- smallest code change
- preserves the current product story and implementation shape

Cons:

- does not solve the current Windows and Python 3.13 problem
- reduces runtime compatibility for end users
- shifts the burden onto environment management and documentation

Assessment:

- pragmatic fallback
- not a true improvement for the current runtime target

## Alternatives Outside SpeechBrain

If the project decides not to stay on SpeechBrain, several other backend families are plausible for a future heavy cleaning mode.

### DeepFilterNet

Pros:

- strong fit for noisy speech enhancement before transcription
- generally a better conceptual match than full source separation
- good chance of improving speech intelligibility for subtitle generation

Cons:

- requires a new backend integration and packaging strategy
- still needs full Windows validation
- adds a new model family and maintenance surface

### RNNoise

Pros:

- lightweight and CPU-friendly
- simpler operational footprint than a larger Torch model stack
- good for steady background-noise reduction

Cons:

- lower quality ceiling on harder cases
- weaker for reverberation, overlapping speakers, or complex non-stationary noise
- less likely to be the strongest “advanced” mode

### FFmpeg Audio Filters

Examples:

- `afftdn`
- `anlmdn`
- `arnndn`

Pros:

- likely the lowest deployment complexity if FFmpeg is already available
- no extra Python ML inference stack required
- fast to prototype and test

Cons:

- more manual tuning required
- easier to over-filter and hurt recognition quality
- may not match the quality of a stronger speech-specific enhancement model

### Demucs Or Similar Separation Models

Pros:

- strong separation capability when the real problem is competing sources
- useful for music-heavy or mixed-source inputs

Cons:

- heavier than necessary for many subtitle-generation cases
- source separation is not always the same as speech cleanup
- more product complexity around source selection

### Spectral Gating / `noisereduce`-Style Approaches

Pros:

- easy to integrate
- lightweight and fast to validate
- good fallback candidate if a heavier model proves too fragile

Cons:

- lower quality and higher artifact risk
- weaker as a premium “advanced” cleaning mode

## Pros And Cons Summary

### Why SpeechBrain Still Has Value

Pros:

- already integrated into the current product and code structure
- conceptually matches the current optional-heavy-backend design
- exposes multiple inference families under one ecosystem

Cons:

- this environment exposed model-path and dependency fragility
- Windows and Python 3.13 compatibility is not yet validated for the current enhancement route
- model-level success cannot be inferred from successful pip installation alone

### Why Another Backend May Still Be Attractive

Pros:

- may avoid the current `k2` and dependency-chain problems entirely
- could offer a better tradeoff between quality, install complexity, and runtime compatibility

Cons:

- requires new integration work and new test coverage
- changes the current “SpeechBrain” product surface and install story

## Recommended Priority Order For Future Work

If the project wants to keep SpeechBrain:

1. evaluate `SGMSEEnhancement` as the first non-`k2` candidate
2. if that is unstable, consider isolating SpeechBrain in a separate helper environment
3. treat `SepformerSeparation` as a last-resort SpeechBrain fallback, because it is a weaker product fit

If the project is willing to change backend families:

1. evaluate DeepFilterNet first
2. evaluate an FFmpeg-filter-based advanced mode as a lower-complexity fallback
3. keep RNNoise or spectral gating as lightweight backup options

## Suggested Validation Plan For A Future Follow-Up

For any future heavy cleaning backend change, validate in this order:

1. clean-process import probe succeeds
2. real model-load probe succeeds
3. one real sample enhancement run produces an output file
4. GUI pre-launch validation reports the correct state
5. CLI execution works with explicit mode selection
6. saved preference reuse still behaves correctly
7. automated tests are updated for the new backend behavior and error surfaces

## Recommendation For The Next Improvement Step

The strongest follow-up candidate while still using SpeechBrain is:

- replace the current `SpectralMaskEnhancement` + `speechbrain/metricgan-plus-voicebank` path with a non-`k2` SpeechBrain route, starting with `SGMSEEnhancement` if its dependency stack can be validated

The strongest follow-up candidate outside SpeechBrain is:

- evaluate DeepFilterNet as a replacement heavy cleanup backend

Until a replacement path is validated, the current `basic` mode remains the most reliable cleanup option on Windows with Python 3.13.