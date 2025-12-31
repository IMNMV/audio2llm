Changelog
=========

0.1.0 — 2025-12-31
- Initial public release.
- Polyphonic transcription via Basic Pitch (>=0.4) with Core ML on macOS; monophonic fallback via librosa.pyin.
- Fixed Basic Pitch API integration to pass the audio file path (not raw arrays) and handle returned tuples.
- Added LLM-friendly text output format (META/NOTE lines) alongside MIDI export.
- CLI and Python API with tempo/key estimation; examples included for quick validation.
- Visible notice when polyphonic is unavailable and the mono fallback is used.

