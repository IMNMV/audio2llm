from audio2llm.postprocess import (
    apply_postprocess,
    enforce_min_duration,
    humanize_velocity,
    quantize,
)
from audio2llm.types import NoteEvent


def _ev(onset, dur=0.4, pitch=60, vel=80):
    return NoteEvent(onset=onset, duration=dur, pitch=pitch, velocity=vel)


def test_quantize_snaps_to_grid():
    # 1/16 at 120 BPM = 0.125s per unit
    events = [_ev(0.13), _ev(0.51)]
    out = quantize(events, "1/16", tempo_bpm=120.0)
    assert abs(out[0].onset - 0.125) < 1e-9
    assert abs(out[1].onset - 0.500) < 1e-9


def test_quantize_strength_partial():
    events = [_ev(0.13)]
    out = quantize(events, "1/16", tempo_bpm=120.0, strength=0.5)
    # halfway between 0.13 and 0.125 = 0.1275
    assert abs(out[0].onset - 0.1275) < 1e-9


def test_min_duration_filter():
    events = [_ev(0.0, dur=0.02), _ev(0.5, dur=0.5)]
    out = enforce_min_duration(events, 0.05)
    assert len(out) == 1
    assert out[0].duration == 0.5


def test_humanize_velocity_is_deterministic_with_seed():
    events = [_ev(0.0, vel=80), _ev(0.5, vel=80)]
    a = humanize_velocity(events, amount=8, seed=42)
    b = humanize_velocity(events, amount=8, seed=42)
    assert [n.velocity for n in a] == [n.velocity for n in b]
    for n in a:
        assert 72 <= n.velocity <= 88


def test_apply_postprocess_pipeline():
    events = [_ev(0.13, dur=0.02), _ev(0.51, dur=0.5)]
    out = apply_postprocess(
        events,
        tempo_bpm=120.0,
        quantize_div="1/16",
        min_duration=0.05,
        humanize_vel=2,
        humanize_seed=0,
    )
    # short note dropped, remaining one quantized
    assert len(out) == 1
    assert abs(out[0].onset - 0.5) < 1e-9
