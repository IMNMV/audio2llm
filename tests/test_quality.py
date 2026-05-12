from audio2llm.quality import compute_warnings
from audio2llm.types import NoteEvent


def _ev(onset, pitch=60, dur=0.4):
    return NoteEvent(onset=onset, duration=dur, pitch=pitch, velocity=80)


def test_empty_warns():
    assert compute_warnings([]) == ["empty: no notes detected"]


def test_dense_cluster_flagged():
    events = [_ev(0.0 + i * 0.001, pitch=60 + i) for i in range(20)]
    warns = compute_warnings(events)
    assert any(w.startswith("dense_cluster") for w in warns)


def test_short_notes_flagged():
    events = [_ev(i * 0.5, dur=0.01) for i in range(10)]
    warns = compute_warnings(events)
    assert any(w.startswith("short_notes") for w in warns)


def test_trailing_silence_flagged():
    events = [_ev(0.0)]
    warns = compute_warnings(events, audio_duration_sec=30.0)
    assert any(w.startswith("trailing_silence") for w in warns)
