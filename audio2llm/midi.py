from __future__ import annotations

from typing import List, Optional

from .types import NoteEvent, TranscriptionResult


def save_midi(
    events: List[NoteEvent],
    path: str,
    tempo_bpm: Optional[float] = 120.0,
    ticks_per_beat: int = 480,
):
    """
    Save events to a single-track MIDI file via mido.
    """
    try:
        import mido
    except Exception as e:
        raise RuntimeError(
            "mido is required to write MIDI. Install with `pip install mido`."
        ) from e

    # Create a new MIDI file and track
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Set tempo
    tempo_us_per_beat = mido.bpm2tempo(tempo_bpm or 120.0)
    track.append(mido.MetaMessage("set_tempo", tempo=tempo_us_per_beat, time=0))

    # Convert seconds to ticks
    def sec_to_ticks(sec: float) -> int:
        # ticks = sec * (ticks_per_beat / seconds_per_beat)
        spb = (tempo_us_per_beat / 1_000_000.0)
        return int(round(sec * (ticks_per_beat / spb)))

    # Build note on/off events, then sort
    midi_msgs = []
    for ev in events:
        on_time = ev.onset
        off_time = ev.onset + ev.duration
        midi_msgs.append((on_time, True, ev.pitch, ev.velocity))
        midi_msgs.append((off_time, False, ev.pitch, ev.velocity))

    midi_msgs.sort(key=lambda x: (x[0], not x[1]))  # note_off before note_on at same time

    # Emit with delta times in ticks
    last_time_sec = 0.0
    for t, is_on, pitch, vel in midi_msgs:
        delta_sec = max(0.0, t - last_time_sec)
        delta_ticks = sec_to_ticks(delta_sec)
        msg = (
            mido.Message("note_on", note=pitch, velocity=vel, time=delta_ticks)
            if is_on
            else mido.Message("note_off", note=pitch, velocity=0, time=delta_ticks)
        )
        track.append(msg)
        last_time_sec = t

    mid.save(path)

