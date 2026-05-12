import json
import tempfile
from pathlib import Path

from audio2llm.jsonio import (
    events_to_ableton_json,
    load_notes_json,
    result_to_json,
    write_json,
)
from audio2llm.types import NoteEvent, TranscriptionMeta, TranscriptionResult


def _events():
    return [
        NoteEvent(onset=0.0, duration=0.5, pitch=60, velocity=80),
        NoteEvent(onset=1.0, duration=0.25, pitch=64, velocity=72, mute=True),
    ]


def test_ableton_json_seconds_includes_beats_when_tempo_known():
    js = events_to_ableton_json(_events(), tempo_bpm=120.0, units="seconds")
    assert js[0] == {
        "pitch": 60,
        "start_time": 0.0,
        "duration": 0.5,
        "velocity": 80,
        "mute": False,
        "start_beat": 0.0,
        "duration_beats": 1.0,
    }
    assert js[1]["mute"] is True


def test_ableton_json_beats_units():
    js = events_to_ableton_json(_events(), tempo_bpm=120.0, units="beats")
    # 1.0s at 120 BPM = 2 beats; 0.25s = 0.5 beats
    assert js[1]["start_time"] == 2.0
    assert js[1]["duration"] == 0.5
    assert "start_beat" not in js[1]


def test_roundtrip_via_result_json():
    res = TranscriptionResult(
        events=_events(),
        meta=TranscriptionMeta(sample_rate=44100, tempo_bpm=120.0, key="C major"),
    )
    payload = result_to_json(res, units="seconds")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "n.json"
        write_json(str(out), payload)
        loaded = load_notes_json(str(out))
    assert len(loaded) == 2
    assert loaded[0].pitch == 60 and loaded[0].onset == 0.0
    assert loaded[1].mute is True


def test_load_bare_list():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "bare.json"
        out.write_text(
            json.dumps(
                [
                    {"pitch": 60, "start_time": 0.0, "duration": 0.5, "velocity": 80},
                    {"pitch": 64, "start_time": 1.0, "duration": 0.25, "velocity": 72},
                ]
            )
        )
        loaded = load_notes_json(str(out))
    assert [n.pitch for n in loaded] == [60, 64]


def test_load_beats_units_converts_to_seconds():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "beats.json"
        write_json(
            str(out),
            {
                "meta": {"units": "beats", "tempo_bpm": 120.0},
                "notes": [{"pitch": 60, "start_time": 2.0, "duration": 1.0, "velocity": 80}],
            },
        )
        loaded = load_notes_json(str(out))
    assert loaded[0].onset == 1.0  # 2 beats @ 120 = 1.0 s
    assert loaded[0].duration == 0.5
