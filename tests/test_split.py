from audio2llm.split import split_parts
from audio2llm.types import NoteEvent


def _ev(onset, pitch):
    return NoteEvent(onset=onset, duration=0.5, pitch=pitch, velocity=80)


def test_bass_below_48():
    events = [_ev(0.0, 36), _ev(0.0, 60), _ev(0.0, 72)]
    parts = split_parts(events)
    assert [n.pitch for n in parts.bass] == [36]
    # Of the upper window {60, 72}, melody = highest = 72; chords = {60}
    assert [n.pitch for n in parts.melody] == [72]
    assert [n.pitch for n in parts.chords] == [60]


def test_melody_picks_highest_per_window():
    # Two clusters: 0.0s {60,67}, 1.0s {62,69}
    events = [_ev(0.0, 60), _ev(0.0, 67), _ev(1.0, 62), _ev(1.0, 69)]
    parts = split_parts(events)
    melody_pitches = sorted(n.pitch for n in parts.melody)
    chord_pitches = sorted(n.pitch for n in parts.chords)
    assert melody_pitches == [67, 69]
    assert chord_pitches == [60, 62]
    assert parts.bass == []


def test_all_notes_preserved():
    events = [_ev(0.0, 36), _ev(0.0, 60), _ev(0.5, 72)]
    parts = split_parts(events)
    assert len(parts.all_notes) == 3
