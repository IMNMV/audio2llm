from audio2llm.types import NoteEvent
from audio2llm.textfmt import events_to_lines


def test_events_to_lines_basic():
    events = [
        NoteEvent(onset=0.0, duration=0.5, pitch=60),
        NoteEvent(onset=0.5, duration=0.25, pitch=64),
    ]
    lines = events_to_lines(events, tempo_bpm=120.0, key="C major")
    assert lines[0] == "META tempo=120.000 key=C major"
    assert lines[1] == "NOTE onset=0.000000 dur=0.500000 pitch=60 vel=64 track=0"
    assert lines[2] == "NOTE onset=0.500000 dur=0.250000 pitch=64 vel=64 track=0"

