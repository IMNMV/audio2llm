Audio2LLM — WAV to MIDI and LLM‑friendly text
=============================================

What It Does
------------
- Transcribes audio (e.g., WAV) into time‑aligned musical note events.
- Writes two outputs:
  - `.mid` Standard MIDI for DAWs/notation.
  - `.txt` compact, LLM‑friendly text listing notes and basic meta.
- Prefers a high‑quality polyphonic model (Basic Pitch) when installed; otherwise falls back to a monophonic f0‑based method.

How It Works
------------
- Polyphonic path (preferred):
  - Uses Spotify’s Basic Pitch (>= 0.4) to infer multiple simultaneous notes from the input audio file.
  - Internally runs a Core ML model (mlpackage) via `coremltools` on macOS; no manual model download needed.
- Monophonic fallback:
  - Uses `librosa.pyin` to track f0, then segments stable pitch regions into discrete notes.
- Musical meta:
  - Tempo estimated via `librosa.beat.beat_track`.
  - Key estimated via chroma features + Krumhansl‑Schmuckler profiles (simple best‑match label).
- MIDI writing:
  - Uses `mido`; converts seconds→ticks using the estimated tempo and emits note on/off with velocities.

How It Was Built
----------------
- Language/runtime: Python 3.9–3.11.
- Core libraries: `numpy`, `librosa`, `soundfile`, `mido`.
- Optional polyphonic: `basic-pitch` (>= 0.4.0). The code calls the newer API by passing the audio file path into `basic_pitch.inference.predict`.
- Package layout:
  - `audio2llm/transcribe.py` — transcription pipeline (polyphonic or mono fallback) + tempo/key estimation.
  - `audio2llm/midi.py` — write events to MIDI.
  - `audio2llm/textfmt.py` — produce LLM‑friendly text lines.
  - `audio2llm/types.py` — dataclasses for notes and meta.
  - `audio2llm/cli.py` — command‑line interface.

Setup
-----
Option A — Conda (recommended)
- Create and activate an env named `audio2llm` from the provided spec:
  - `conda env create -f environment.yml -n audio2llm`
  - `conda activate audio2llm`
- Install polyphonic support (recommended):
  - `pip install basic-pitch`
- macOS Apple Silicon note: Basic Pitch 0.4 runs via Core ML and installs `coremltools` automatically. If polyphonic still appears to fall back to mono, ensure `basic-pitch` is installed and re‑run. In some setups, installing `onnxruntime==1.18.1` can help, but it is not strictly required for Core ML.

Option B — Minimal pip (mono only)
- `pip install numpy librosa soundfile mido`

Usage
-----
CLI
- Basic run (auto polyphonic if available):
  - `python -m audio2llm.cli input.wav --out-midi output.mid --out-text output.txt --prefer-polyphonic`
- Force monophonic fallback:
  - `python -m audio2llm.cli input.wav --out-midi output.mid --out-text output.txt --no-polyphonic`

API
- Example:
  - `from audio2llm import transcribe_audio, save_midi, events_to_lines`
  - `result = transcribe_audio("input.wav", prefer_polyphonic=True)`
  - `save_midi(result.events, "out.mid", tempo_bpm=result.meta.tempo_bpm)`
  - `lines = events_to_lines(result.events, tempo_bpm=result.meta.tempo_bpm, key=result.meta.key)`

Outputs
-------
- Text format: header lines then one NOTE per line, e.g.

  `META tempo=118.123 key=G major`

  `NOTE onset=0.512000 dur=0.240000 pitch=67 vel=92 track=0`

- Fields:
  - `onset`: seconds from start
  - `dur`: duration in seconds
  - `pitch`: MIDI note number (0–127)
  - `vel`: MIDI velocity (1–127)
  - `track`: instrument/part index (0 unless a polyphonic model supplies parts)

Troubleshooting
---------------
- Polyphonic didn’t kick in (text looks monophonic, few notes):
  - Verify `pip show basic-pitch` in your env.
  - Reinstall: `pip install --upgrade basic-pitch`
  - On macOS, ensure your Python can import `coremltools` (installed with Basic Pitch). If issues persist, try `pip install onnxruntime==1.18.1` and rerun.
- MIDI file loads with unexpected tempo:
  - Tempo is estimated; you can override when writing MIDI via `save_midi(..., tempo_bpm=...)`.
# audio2llm
