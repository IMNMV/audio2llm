from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from .compare import compare_notes, report_to_markdown, CompareReport
from .jsonio import load_notes_json
from .transcribe import transcribe_audio
from .types import NoteEvent


_NotesArg = Union[str, List[NoteEvent], List[Dict[str, Any]]]


def _coerce_notes(notes: _NotesArg) -> List[NoteEvent]:
    if isinstance(notes, str):
        return load_notes_json(notes)
    if not notes:
        return []
    first = notes[0]
    if isinstance(first, NoteEvent):
        return list(notes)  # type: ignore[arg-type]
    if isinstance(first, dict):
        # Accept dicts in either our schema or with "onset"/"dur" keys
        out: List[NoteEvent] = []
        for n in notes:  # type: ignore[assignment]
            out.append(
                NoteEvent(
                    onset=float(n.get("start_time", n.get("onset", 0.0))),
                    duration=float(n.get("duration", n.get("dur", 0.0))),
                    pitch=int(n["pitch"]),
                    velocity=int(n.get("velocity", 80)),
                    track=int(n.get("track", 0)),
                    mute=bool(n.get("mute", False)),
                )
            )
        return out
    raise TypeError(f"Unsupported notes type: {type(first)}")


def analyze_render(
    intended_notes: _NotesArg,
    rendered_audio: str,
    tempo_bpm: Optional[float] = None,
    prefer_polyphonic: bool = True,
    time_tolerance: float = 0.08,
    wrong_pitch_window: int = 2,
) -> Dict[str, Any]:
    """High-level agent loop: take an intended note list + a rendered audio bounce
    and return structured musical feedback.

    Args:
        intended_notes: path to notes JSON OR a list of NoteEvent / dicts.
        rendered_audio: path to the audio file that the DAW bounced from those notes.
        tempo_bpm: optional override; otherwise estimated from the audio.
        prefer_polyphonic: pass through to transcribe_audio.

    Returns a dict containing:
        - "summary": top-line metrics (match_rate, drift, etc.)
        - "report": full CompareReport.to_dict()
        - "report_markdown": human/agent-readable text
        - "transcription": the heard notes + meta (warnings included)
    """
    intended = _coerce_notes(intended_notes)
    result = transcribe_audio(rendered_audio, prefer_polyphonic=prefer_polyphonic)
    heard = result.events
    cmp = compare_notes(
        intended,
        heard,
        time_tolerance=time_tolerance,
        wrong_pitch_window=wrong_pitch_window,
    )
    effective_tempo = tempo_bpm if tempo_bpm is not None else result.meta.tempo_bpm
    return {
        "summary": cmp.summary,
        "report": cmp.to_dict(),
        "report_markdown": report_to_markdown(cmp),
        "transcription": {
            "tempo_bpm": effective_tempo,
            "key": result.meta.key,
            "warnings": list(result.meta.warnings),
            "notes": [
                {
                    "pitch": e.pitch,
                    "start_time": round(e.onset, 6),
                    "duration": round(e.duration, 6),
                    "velocity": e.velocity,
                }
                for e in heard
            ],
        },
    }
