from pathlib import Path
import tempfile

import mido

from audio2llm.types import NoteEvent
from audio2llm.midi import save_midi


def test_save_midi_roundtrip():
    events = [
        NoteEvent(onset=0.0, duration=0.5, pitch=60, velocity=80),
        NoteEvent(onset=0.6, duration=0.4, pitch=64, velocity=70),
    ]
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "test.mid"
        save_midi(events, str(out), tempo_bpm=120.0)
        assert out.exists() and out.stat().st_size > 0

        mid = mido.MidiFile(str(out))
        # Expect one tempo meta
        tempos = [msg.tempo for tr in mid.tracks for msg in tr if msg.type == "set_tempo"]
        assert len(tempos) == 1
        assert tempos[0] == mido.bpm2tempo(120.0)

        note_on = 0
        note_off = 0
        for tr in mid.tracks:
            for msg in tr:
                if msg.type == "note_on" and msg.velocity > 0:
                    note_on += 1
                if msg.type == "note_off":
                    note_off += 1
        assert note_on == 2
        assert note_off == 2

