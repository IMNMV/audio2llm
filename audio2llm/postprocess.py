from __future__ import annotations

import random
from typing import Iterable, List, Optional

from .types import NoteEvent


_DIV_MAP = {
    "1/1": 4.0,
    "1/2": 2.0,
    "1/4": 1.0,
    "1/8": 0.5,
    "1/16": 0.25,
    "1/32": 0.125,
    "1/4t": 2.0 / 3.0,
    "1/8t": 1.0 / 3.0,
    "1/16t": 1.0 / 6.0,
}


def _beats_per_unit(division: str) -> float:
    if division not in _DIV_MAP:
        raise ValueError(f"Unknown quantize division: {division}. Use one of {list(_DIV_MAP)}")
    return _DIV_MAP[division]


def quantize(
    events: Iterable[NoteEvent],
    division: str,
    tempo_bpm: float,
    strength: float = 1.0,
    quantize_duration: bool = False,
) -> List[NoteEvent]:
    """Snap onsets (and optionally durations) toward the nearest grid line.

    strength=1.0 fully snaps; 0.5 moves halfway toward the grid (groove-preserving).
    """
    bpu = _beats_per_unit(division)
    sec_per_unit = bpu * (60.0 / tempo_bpm)
    out: List[NoteEvent] = []
    for ev in events:
        snapped_on = round(ev.onset / sec_per_unit) * sec_per_unit
        new_onset = ev.onset + strength * (snapped_on - ev.onset)
        new_dur = ev.duration
        if quantize_duration:
            snapped_dur = max(sec_per_unit, round(ev.duration / sec_per_unit) * sec_per_unit)
            new_dur = ev.duration + strength * (snapped_dur - ev.duration)
        out.append(
            NoteEvent(
                onset=new_onset,
                duration=new_dur,
                pitch=ev.pitch,
                velocity=ev.velocity,
                track=ev.track,
                mute=ev.mute,
            )
        )
    out.sort(key=lambda e: (e.onset, e.pitch))
    return out


def humanize_velocity(
    events: Iterable[NoteEvent],
    amount: int = 8,
    seed: Optional[int] = None,
) -> List[NoteEvent]:
    """Add bounded random jitter to velocities. amount = +/- range."""
    rng = random.Random(seed)
    out: List[NoteEvent] = []
    for ev in events:
        jitter = rng.randint(-amount, amount)
        v = max(1, min(127, ev.velocity + jitter))
        out.append(
            NoteEvent(
                onset=ev.onset,
                duration=ev.duration,
                pitch=ev.pitch,
                velocity=v,
                track=ev.track,
                mute=ev.mute,
            )
        )
    return out


def enforce_min_duration(events: Iterable[NoteEvent], min_duration: float) -> List[NoteEvent]:
    """Drop notes shorter than min_duration (likely transcription artifacts)."""
    return [e for e in events if e.duration >= min_duration]


def apply_postprocess(
    events: List[NoteEvent],
    tempo_bpm: Optional[float],
    quantize_div: Optional[str] = None,
    quantize_strength: float = 1.0,
    quantize_duration: bool = False,
    humanize_vel: Optional[int] = None,
    min_duration: Optional[float] = None,
    humanize_seed: Optional[int] = None,
) -> List[NoteEvent]:
    """Composed pipeline used by the CLI."""
    out = list(events)
    if min_duration is not None:
        out = enforce_min_duration(out, min_duration)
    if quantize_div:
        if tempo_bpm is None:
            raise ValueError("quantize requires tempo_bpm")
        out = quantize(
            out,
            division=quantize_div,
            tempo_bpm=tempo_bpm,
            strength=quantize_strength,
            quantize_duration=quantize_duration,
        )
    if humanize_vel is not None:
        out = humanize_velocity(out, amount=humanize_vel, seed=humanize_seed)
    return out
