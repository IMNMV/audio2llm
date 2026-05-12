from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from .types import NoteEvent


@dataclass
class StemSplit:
    bass: List[NoteEvent]
    chords: List[NoteEvent]
    melody: List[NoteEvent]
    all_notes: List[NoteEvent]


def split_parts(
    events: Iterable[NoteEvent],
    bass_max_pitch: int = 47,  # bass = pitches below MIDI 48 (i.e. <= 47)
    melody_window_sec: float = 0.18,
) -> StemSplit:
    """Rule-based bass / melody / chords split.

    - bass: pitch <= bass_max_pitch
    - melody: of the non-bass notes, the highest-pitched note within each rolling time window
              of `melody_window_sec` becomes melody. Ties broken by earlier onset.
    - chords: everything else (non-bass, non-melody).
    """
    events = sorted(events, key=lambda e: (e.onset, -e.pitch))
    all_notes = list(events)

    bass: List[NoteEvent] = []
    upper: List[NoteEvent] = []
    for ev in events:
        (bass if ev.pitch <= bass_max_pitch else upper).append(ev)

    melody: List[NoteEvent] = []
    chords: List[NoteEvent] = []

    # Bucket upper notes into time windows; highest in each window -> melody, rest -> chords.
    if not upper:
        return StemSplit(bass=bass, chords=chords, melody=melody, all_notes=all_notes)

    window: List[NoteEvent] = []
    window_start = upper[0].onset

    def flush(win: List[NoteEvent]):
        if not win:
            return
        top = max(win, key=lambda e: (e.pitch, -e.onset))
        for n in win:
            (melody if n is top else chords).append(n)

    for ev in upper:
        if ev.onset - window_start > melody_window_sec:
            flush(window)
            window = [ev]
            window_start = ev.onset
        else:
            window.append(ev)
    flush(window)

    melody.sort(key=lambda e: (e.onset, e.pitch))
    chords.sort(key=lambda e: (e.onset, e.pitch))
    return StemSplit(bass=bass, chords=chords, melody=melody, all_notes=all_notes)
