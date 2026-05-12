from audio2llm.compare import compare_notes, report_to_markdown
from audio2llm.types import NoteEvent


def _ev(onset, pitch, dur=0.4, vel=80):
    return NoteEvent(onset=onset, duration=dur, pitch=pitch, velocity=vel)


def test_perfect_match():
    intended = [_ev(0.0, 60), _ev(0.5, 62), _ev(1.0, 64)]
    heard = [_ev(0.0, 60), _ev(0.5, 62), _ev(1.0, 64)]
    r = compare_notes(intended, heard)
    assert r.summary["matched"] == 3
    assert r.summary["missing"] == 0
    assert r.summary["extra"] == 0
    assert r.summary["wrong_pitch"] == 0


def test_timing_drift_within_tolerance():
    intended = [_ev(0.0, 60)]
    heard = [_ev(0.04, 60)]
    r = compare_notes(intended, heard, time_tolerance=0.08)
    assert r.summary["matched"] == 1
    assert abs(r.matches[0].timing_drift_sec - 0.04) < 1e-6


def test_missing_and_extra():
    intended = [_ev(0.0, 60), _ev(0.5, 62)]
    heard = [_ev(0.0, 60), _ev(2.0, 70)]  # 62 missing; 70 extra
    r = compare_notes(intended, heard)
    assert r.summary["matched"] == 1
    assert r.summary["missing"] == 1
    assert r.summary["extra"] == 1
    assert r.missing[0]["pitch"] == 62
    assert r.extra[0]["pitch"] == 70


def test_wrong_pitch_captured_within_semitone_window():
    intended = [_ev(0.0, 60)]
    heard = [_ev(0.0, 61)]  # off by 1 semitone
    r = compare_notes(intended, heard, wrong_pitch_window=2)
    assert r.summary["wrong_pitch"] == 1
    assert r.summary["missing"] == 0
    assert r.wrong_pitch[0]["pitch_diff_semitones"] == 1


def test_chord_check_matches_simultaneous_notes():
    # C major triad at t=0
    intended = [_ev(0.0, 60), _ev(0.0, 64), _ev(0.0, 67)]
    heard = [_ev(0.0, 60), _ev(0.005, 64), _ev(0.01, 67)]
    r = compare_notes(intended, heard)
    assert r.chord_checks
    assert r.chord_checks[0].status == "match"


def test_chord_check_flags_partial():
    intended = [_ev(0.0, 60), _ev(0.0, 64), _ev(0.0, 67)]
    heard = [_ev(0.0, 60), _ev(0.0, 64)]  # missing G
    r = compare_notes(intended, heard)
    assert r.chord_checks[0].status in ("partial", "mismatch")
    assert 67 in r.chord_checks[0].missing


def test_markdown_renders():
    intended = [_ev(0.0, 60), _ev(0.5, 62)]
    heard = [_ev(0.0, 60)]
    md = report_to_markdown(compare_notes(intended, heard))
    assert "Summary" in md
    assert "Missing notes" in md
