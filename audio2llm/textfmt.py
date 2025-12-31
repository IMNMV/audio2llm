from __future__ import annotations

from typing import Iterable, List

from .types import NoteEvent, TranscriptionResult


def events_to_lines(events: Iterable[NoteEvent], tempo_bpm: float | None = None, key: str | None = None) -> List[str]:
    """
    Produce a compact, LLM-friendly line format.

    Header lines first (if available), then one NOTE line per event.
    Format:
    - META tempo=120.0 key=C major
    - NOTE onset=1.234 dur=0.567 pitch=64 vel=96 track=0
    """
    lines: List[str] = []
    if tempo_bpm is not None or key is not None:
        meta_bits = []
        if tempo_bpm is not None:
            meta_bits.append(f"tempo={tempo_bpm:.3f}")
        if key is not None:
            meta_bits.append(f"key={key}")
        lines.append("META " + " ".join(meta_bits))

    for ev in events:
        lines.append(
            f"NOTE onset={ev.onset:.6f} dur={ev.duration:.6f} pitch={ev.pitch} vel={ev.velocity} track={ev.track}"
        )
    return lines

