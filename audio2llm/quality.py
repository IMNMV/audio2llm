from __future__ import annotations

from typing import Iterable, List, Optional

from .types import NoteEvent


def compute_warnings(
    events: List[NoteEvent],
    audio_duration_sec: Optional[float] = None,
    dense_window_sec: float = 0.020,
    dense_max_notes: int = 12,
    burst_max_semitones: float = 24.0,
    short_note_sec: float = 0.05,
    trailing_silence_threshold: float = 0.5,
) -> List[str]:
    """Heuristic confidence / quality flags for downstream LLM consumption.

    Returned as a list of short human-readable strings. Designed so an agent can
    say "this transcription looks risky, ask the user to provide a stem".
    """
    warnings: List[str] = []
    if not events:
        warnings.append("empty: no notes detected")
        return warnings

    # Dense simultaneous notes
    by_onset = sorted(events, key=lambda e: e.onset)
    max_density = 0
    for i, ev in enumerate(by_onset):
        j = i
        cluster = 0
        while j < len(by_onset) and by_onset[j].onset - ev.onset <= dense_window_sec:
            cluster += 1
            j += 1
        max_density = max(max_density, cluster)
    if max_density > dense_max_notes:
        warnings.append(
            f"dense_cluster: {max_density} notes inside {int(dense_window_sec * 1000)} ms "
            f"(likely full-mix input; feed a stem)"
        )

    # Large pitch burst between consecutive notes
    sorted_by_onset = by_onset
    for prev, curr in zip(sorted_by_onset, sorted_by_onset[1:]):
        if abs(curr.pitch - prev.pitch) >= burst_max_semitones and (curr.onset - prev.onset) < 0.05:
            warnings.append(
                f"pitch_burst: {abs(curr.pitch - prev.pitch)} semitones between adjacent notes "
                f"near {prev.onset:.2f}s"
            )
            break

    # Lots of short notes (likely ghost / hallucinated)
    short = sum(1 for e in events if e.duration < short_note_sec)
    if short / max(1, len(events)) > 0.25:
        warnings.append(
            f"short_notes: {short}/{len(events)} notes shorter than {int(short_note_sec * 1000)} ms"
        )

    # Trailing silence hallucination
    if audio_duration_sec is not None:
        last = max(events, key=lambda e: e.onset + e.duration)
        last_end = last.onset + last.duration
        if last_end < audio_duration_sec - trailing_silence_threshold:
            gap = audio_duration_sec - last_end
            if gap > trailing_silence_threshold * 2:
                warnings.append(
                    f"trailing_silence: last note ends {gap:.2f}s before audio end"
                )

    return warnings
