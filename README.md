Audio2LLM — an agent-readable bridge between audio and your DAW
===============================================================

What it is
----------
`audio2llm` is **not** trying to be a perfect audio-to-MIDI converter. Ableton and Basic Pitch already do that. The value here is that it turns an audio performance into **structured, symbolic data an LLM can reason about**, and gives the LLM a way to **listen back** to its own renders and correct itself.

The intended workflow:

```
audio idea
   → audio2llm           # transcribe
   → note text / JSON    # LLM analyzes, cleans, splits, transposes
   → Ableton MIDI clip   # via your MCP layer
   → bounce              # DAW renders audio
   → audio2llm compare   # confirm the bounce matches the intent
   → corrected notes     # close the loop
```

This is a creative translation layer, not a transcription tool.

Features
--------
- **Transcribe**: audio → MIDI, plus a compact text format and a structured JSON.
- **Ableton-ready JSON**: notes as `{pitch, start_time, duration, velocity, mute}`, in seconds OR beats (Ableton's native unit).
- **Compare mode**: take an intended-notes JSON + a rendered audio file, return a structured diff (missing / extra / wrong-pitch / timing drift / velocity diff / chord match).
- **Analyze (agent loop)**: one-shot `intended.json + rendered.wav → feedback.json` for LLM agents.
- **Stem split**: rule-based bass / chords / melody buckets.
- **Postprocess**: quantize (`1/4`, `1/8`, `1/16`, `1/8t`, …), humanize velocity, drop short notes.
- **Quality flags**: warns on dense full-mix input, pitch bursts, ghost notes, trailing silence — so an agent can decide whether the transcription is trustworthy.
- **Polyphonic** via Spotify Basic Pitch when installed; monophonic `pyin` fallback otherwise.

Setup
-----
Conda (recommended):

```
conda env create -f environment.yml -n audio2llm
conda activate audio2llm
pip install -e .
pip install basic-pitch          # optional, for polyphonic
```

Minimal pip (mono only):
```
pip install numpy librosa soundfile mido
```

CLI
---
The CLI uses subcommands; the old positional form (`audio2llm input.wav --out-midi …`) still works and is mapped to `transcribe`.

### transcribe

```
audio2llm transcribe input.wav \
  --prefer-polyphonic \
  --out-midi out.mid \
  --out-text notes.txt \
  --out-json notes.json \
  --out-ableton-json ableton_notes.json \
  --ableton-units beats \
  --out-split parts/ \
  --quantize 1/16 --quantize-strength 0.8 \
  --humanize-velocity 6 \
  --min-duration 0.05 \
  --out-report report.md
```

Common flags:
- `--ableton-units {seconds,beats}` — units for `start_time`/`duration` in the Ableton JSON. Defaults to seconds; `beats` matches Ableton Live's native time unit.
- `--quantize 1/16` (or `1/8`, `1/4`, `1/8t`, etc.) with `--quantize-strength 0..1`. Requires a known tempo.
- `--preserve-human-timing` — no-op shorthand; equivalent to omitting `--quantize`.
- `--out-split DIR` writes `bass.json`, `chords.json`, `melody.json`, `all_notes.json`.

### compare

Compare LLM-intended notes against an audio bounce from the DAW:

```
audio2llm compare intended.json rendered.wav --out-report feedback.md --out-json feedback.json
```

Prints a one-line summary; the markdown report lists missing notes, extra notes, wrong-pitch hits, chord checks, and timing/velocity drift.

### analyze

Single-call wrapper that bundles compare + transcription metadata into one JSON for an agent:

```
audio2llm analyze intended.json rendered.wav --out-json feedback.json
```

Python API
----------
```python
from audio2llm import (
    transcribe_audio, save_midi, events_to_lines,
    events_to_ableton_json, load_notes_json,
    split_parts, compare_notes, analyze_render,
    apply_postprocess,
)

result = transcribe_audio("input.wav", prefer_polyphonic=True)
save_midi(result.events, "out.mid", tempo_bpm=result.meta.tempo_bpm)

# Ableton-ready dicts, beats units
notes = events_to_ableton_json(result.events,
                               tempo_bpm=result.meta.tempo_bpm,
                               units="beats")

# Agent feedback loop
feedback = analyze_render(
    intended_notes="planned.json",      # or list of dicts / NoteEvent
    rendered_audio="bounce.wav",
    tempo_bpm=120.0,
)
print(feedback["summary"])
print(feedback["report_markdown"])
```

JSON shapes
-----------
**Ableton-shaped note** (matches the fields Ableton's note APIs expect):

```json
{
  "pitch": 60,
  "start_time": 1.0,
  "duration": 0.5,
  "velocity": 80,
  "mute": false
}
```

When units are `seconds` and tempo is known, `start_beat` and `duration_beats` are also included so MCP layers can pick whichever they need.

**Structured transcription** (`--out-json`):

```json
{
  "meta": {
    "sample_rate": 22050,
    "tempo_bpm": 118.1,
    "key": "G major",
    "warnings": ["dense_cluster: 14 notes inside 20 ms (likely full-mix input; feed a stem)"],
    "units": "seconds"
  },
  "notes": [ /* Ableton-shaped notes */ ]
}
```

**Compare report** (`compare --out-json` / `analyze --out-json`):

```json
{
  "summary": {
    "intended_count": 8, "heard_count": 7, "matched": 6,
    "missing": 1, "extra": 0, "wrong_pitch": 1,
    "match_rate": 0.75,
    "mean_timing_drift_sec": 0.012,
    "max_abs_timing_drift_sec": 0.034,
    "mean_velocity_diff": -3.2,
    "chord_match_rate": 1.0
  },
  "matches": [...], "missing": [...], "extra": [...],
  "wrong_pitch": [...], "chord_checks": [...]
}
```

Text format (for prompting an LLM)
----------------------------------
```
META tempo=118.123 key=G major
NOTE onset=0.512000 dur=0.240000 pitch=67 vel=92 track=0
```

Best uses
---------
- Idea capture: voice / piano / guitar / synth sketch → editable MIDI.
- LLM-assisted cleanup: detect chord names, prune ghost notes, transpose, humanize.
- Alternate versions from one performance: bass, pads, arp, melody-double from a single piano take.
- Sampling: extract key, chord progression, and bass movement to layer on top of a loop.
- Sound design by resynthesis: drive a totally different synth from a captured performance.

What it's **not** good for
--------------------------
Dense full mixes, mastered tracks, drums, vocals-over-instruments. Basic Pitch is instrument-agnostic but works best on one instrument at a time — feed stems whenever possible. The quality flags will tell you when the input looks too dense to trust.

Troubleshooting
---------------
- Polyphonic didn't kick in: `pip show basic-pitch` to verify, then `pip install --upgrade basic-pitch`. On macOS, `coremltools` is installed automatically.
- Unexpected tempo in MIDI: pass `--tempo-override` to the CLI, or `tempo_bpm=` to `save_midi`.

Package layout
--------------
```
audio2llm/
  transcribe.py    polyphonic + monophonic transcription, tempo/key estimation
  midi.py          mido-based MIDI writer
  textfmt.py       LLM-friendly NOTE lines
  jsonio.py        Ableton-shaped JSON + structured JSON I/O
  postprocess.py   quantize / humanize / min-duration filtering
  split.py         bass / chords / melody rule-based split
  quality.py       confidence flags on a NoteEvent list
  compare.py       diff intended vs heard, with markdown rendering
  agent.py         analyze_render() one-shot agent loop
  cli.py           transcribe / compare / analyze subcommands
  types.py         NoteEvent, TranscriptionMeta, TranscriptionResult
```
