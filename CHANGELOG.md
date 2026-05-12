Changelog
=========

0.2.0 — 2026-05-12
- Re-framed audio2llm as an LLM/DAW agent loop, not just an audio-to-MIDI converter.
- Added Ableton-ready JSON output (`pitch`, `start_time`, `duration`, `velocity`, `mute`) with
  `--ableton-units {seconds,beats}` for Ableton Live's native beat-based timing.
- New `compare` subcommand: diff intended notes JSON against a rendered audio file
  (missing / extra / wrong-pitch / timing drift / velocity diff / chord checks). Emits
  Markdown and/or structured JSON reports.
- New `analyze` subcommand and `analyze_render()` Python API for one-shot agent feedback.
- New `--out-split DIR` writes `bass.json` / `chords.json` / `melody.json` / `all_notes.json`
  using a rule-based separation (bass < MIDI 48; melody = highest per time window; rest = chords).
- New postprocess flags: `--quantize 1/16` (etc.) with `--quantize-strength`, `--humanize-velocity`,
  `--min-duration`, `--preserve-human-timing`, `--tempo-override`.
- Quality / confidence flags on transcription: dense clusters, pitch bursts, short ghost notes,
  trailing silence. Surfaced in `TranscriptionMeta.warnings` and the structured JSON output.
- CLI refactored to subcommand style (`transcribe` / `compare` / `analyze`) with back-compat for
  the old `audio2llm input.wav --out-midi ...` positional form.
- Added tests for compare, split, postprocess, quality, and jsonio.

0.1.0 — 2025-12-31
- Initial public release.
- Polyphonic transcription via Basic Pitch (>=0.4) with Core ML on macOS; monophonic fallback via librosa.pyin.
- Fixed Basic Pitch API integration to pass the audio file path (not raw arrays) and handle returned tuples.
- Added LLM-friendly text output format (META/NOTE lines) alongside MIDI export.
- CLI and Python API with tempo/key estimation; examples included for quick validation.
- Visible notice when polyphonic is unavailable and the mono fallback is used.

