from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .types import NoteEvent, TranscriptionMeta, TranscriptionResult


def _seconds_to_beats(seconds: float, tempo_bpm: float) -> float:
    return seconds * (tempo_bpm / 60.0)


def _beats_to_seconds(beats: float, tempo_bpm: float) -> float:
    return beats * (60.0 / tempo_bpm)


def note_to_ableton_dict(
    ev: NoteEvent,
    tempo_bpm: Optional[float] = None,
    units: str = "seconds",
) -> Dict[str, Any]:
    """One note in the shape Ableton's note APIs expect.

    units="seconds": start_time/duration in seconds (also exports start_beat/duration_beats if tempo known).
    units="beats":   start_time/duration in beats (Ableton Live native unit). Requires tempo_bpm.
    """
    if units == "beats":
        if tempo_bpm is None:
            raise ValueError("tempo_bpm required when units='beats'")
        return {
            "pitch": int(ev.pitch),
            "start_time": round(_seconds_to_beats(ev.onset, tempo_bpm), 6),
            "duration": round(_seconds_to_beats(ev.duration, tempo_bpm), 6),
            "velocity": int(ev.velocity),
            "mute": bool(ev.mute),
        }

    d: Dict[str, Any] = {
        "pitch": int(ev.pitch),
        "start_time": round(ev.onset, 6),
        "duration": round(ev.duration, 6),
        "velocity": int(ev.velocity),
        "mute": bool(ev.mute),
    }
    if tempo_bpm:
        d["start_beat"] = round(_seconds_to_beats(ev.onset, tempo_bpm), 6)
        d["duration_beats"] = round(_seconds_to_beats(ev.duration, tempo_bpm), 6)
    return d


def events_to_ableton_json(
    events: Iterable[NoteEvent],
    tempo_bpm: Optional[float] = None,
    units: str = "seconds",
) -> List[Dict[str, Any]]:
    return [note_to_ableton_dict(e, tempo_bpm=tempo_bpm, units=units) for e in events]


def result_to_json(
    result: TranscriptionResult,
    units: str = "seconds",
) -> Dict[str, Any]:
    """Full structured JSON: meta + notes. Designed for LLM consumption."""
    tempo = result.meta.tempo_bpm
    return {
        "meta": {
            "sample_rate": result.meta.sample_rate,
            "tempo_bpm": tempo,
            "time_signature": result.meta.time_signature,
            "key": result.meta.key,
            "warnings": list(result.meta.warnings),
            "units": units,
        },
        "notes": events_to_ableton_json(result.events, tempo_bpm=tempo, units=units),
    }


def write_json(path: str, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_notes_json(path: str) -> List[NoteEvent]:
    """Load a notes JSON file written by us OR a bare list of Ableton-shaped dicts.

    Accepts either:
      [{"pitch":60, "start_time":1.0, "duration":0.5, "velocity":80, "mute":false}, ...]
    or our full result dict {"meta":..., "notes":[...]}.

    If "units" is "beats" in meta and tempo_bpm is provided, times are converted to seconds.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "notes" in raw:
        meta = raw.get("meta", {}) or {}
        units = meta.get("units", "seconds")
        tempo = meta.get("tempo_bpm")
        items = raw["notes"]
    elif isinstance(raw, list):
        units = "seconds"
        tempo = None
        items = raw
    else:
        raise ValueError(f"Unrecognized notes JSON format: {path}")

    out: List[NoteEvent] = []
    for n in items:
        start = float(n.get("start_time", n.get("onset", 0.0)))
        dur = float(n.get("duration", n.get("dur", 0.0)))
        if units == "beats":
            if tempo is None:
                raise ValueError("notes units='beats' but meta.tempo_bpm missing")
            start = _beats_to_seconds(start, float(tempo))
            dur = _beats_to_seconds(dur, float(tempo))
        out.append(
            NoteEvent(
                onset=start,
                duration=dur,
                pitch=int(n["pitch"]),
                velocity=int(n.get("velocity", 80)),
                track=int(n.get("track", 0)),
                mute=bool(n.get("mute", False)),
            )
        )
    out.sort(key=lambda e: (e.onset, e.pitch))
    return out
