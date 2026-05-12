from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from .types import NoteEvent


@dataclass
class NoteMatch:
    intended: Dict[str, Any]
    heard: Dict[str, Any]
    timing_drift_sec: float
    velocity_diff: int
    duration_diff_sec: float


@dataclass
class ChordCheck:
    time: float
    intended_pitches: List[int]
    heard_pitches: List[int]
    missing: List[int]
    extra: List[int]
    status: str  # "match" | "partial" | "mismatch"


@dataclass
class CompareReport:
    matches: List[NoteMatch] = field(default_factory=list)
    missing: List[Dict[str, Any]] = field(default_factory=list)
    extra: List[Dict[str, Any]] = field(default_factory=list)
    wrong_pitch: List[Dict[str, Any]] = field(default_factory=list)
    chord_checks: List[ChordCheck] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "matches": [asdict(m) for m in self.matches],
            "missing": self.missing,
            "extra": self.extra,
            "wrong_pitch": self.wrong_pitch,
            "chord_checks": [asdict(c) for c in self.chord_checks],
        }


def _note_dict(ev: NoteEvent) -> Dict[str, Any]:
    return {
        "pitch": ev.pitch,
        "start_time": round(ev.onset, 6),
        "duration": round(ev.duration, 6),
        "velocity": ev.velocity,
    }


def compare_notes(
    intended: List[NoteEvent],
    heard: List[NoteEvent],
    time_tolerance: float = 0.08,
    pitch_tolerance: int = 0,
    wrong_pitch_window: int = 2,
    chord_window: float = 0.06,
) -> CompareReport:
    """Match heard notes against intended notes and produce a structured diff.

    Algorithm:
      1. For each intended note, find nearest unmatched heard note with same pitch
         within time_tolerance. That's a "match".
      2. Remaining intended notes: try to find an unmatched heard note within
         time_tolerance and ±wrong_pitch_window semitones. Those become "wrong_pitch".
      3. Remaining intended notes -> "missing".
      4. Remaining heard notes -> "extra".
      5. Chord check: group intended notes into onset clusters (<= chord_window apart);
         for each cluster compare its pitch-set against heard notes in that window.
    """
    intended_sorted = sorted(intended, key=lambda e: (e.onset, e.pitch))
    heard_sorted = sorted(heard, key=lambda e: (e.onset, e.pitch))
    heard_used = [False] * len(heard_sorted)

    report = CompareReport()

    def _find_best(int_ev: NoteEvent, max_pitch_diff: int) -> Optional[int]:
        best_idx: Optional[int] = None
        best_cost: Optional[float] = None
        for j, h in enumerate(heard_sorted):
            if heard_used[j]:
                continue
            dt = h.onset - int_ev.onset
            if dt > time_tolerance + 0.05:
                # heard list is sorted by onset, so further entries are even later
                break
            if abs(dt) > time_tolerance:
                continue
            pd = abs(h.pitch - int_ev.pitch)
            if pd > max_pitch_diff:
                continue
            cost = abs(dt) + 0.05 * pd
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best_idx = j
        return best_idx

    unmatched_intended_idx: List[int] = []

    # Pass 1: exact-pitch matches
    for i, ev in enumerate(intended_sorted):
        j = _find_best(ev, pitch_tolerance)
        if j is None:
            unmatched_intended_idx.append(i)
            continue
        h = heard_sorted[j]
        heard_used[j] = True
        report.matches.append(
            NoteMatch(
                intended=_note_dict(ev),
                heard=_note_dict(h),
                timing_drift_sec=round(h.onset - ev.onset, 6),
                velocity_diff=int(h.velocity - ev.velocity),
                duration_diff_sec=round(h.duration - ev.duration, 6),
            )
        )

    # Pass 2: wrong-pitch matches
    still_unmatched: List[int] = []
    for i in unmatched_intended_idx:
        ev = intended_sorted[i]
        j = _find_best(ev, wrong_pitch_window)
        if j is None:
            still_unmatched.append(i)
            continue
        h = heard_sorted[j]
        heard_used[j] = True
        report.wrong_pitch.append(
            {
                "intended": _note_dict(ev),
                "heard": _note_dict(h),
                "pitch_diff_semitones": int(h.pitch - ev.pitch),
                "timing_drift_sec": round(h.onset - ev.onset, 6),
            }
        )

    # Missing
    for i in still_unmatched:
        report.missing.append(_note_dict(intended_sorted[i]))

    # Extra
    for j, used in enumerate(heard_used):
        if not used:
            report.extra.append(_note_dict(heard_sorted[j]))

    # Chord checks
    report.chord_checks = _chord_checks(intended_sorted, heard_sorted, chord_window, time_tolerance)

    # Summary
    drifts = [m.timing_drift_sec for m in report.matches]
    vels = [m.velocity_diff for m in report.matches]
    report.summary = {
        "intended_count": len(intended_sorted),
        "heard_count": len(heard_sorted),
        "matched": len(report.matches),
        "wrong_pitch": len(report.wrong_pitch),
        "missing": len(report.missing),
        "extra": len(report.extra),
        "match_rate": round(len(report.matches) / max(1, len(intended_sorted)), 4),
        "mean_timing_drift_sec": round(sum(drifts) / len(drifts), 6) if drifts else None,
        "max_abs_timing_drift_sec": round(max(abs(d) for d in drifts), 6) if drifts else None,
        "mean_velocity_diff": round(sum(vels) / len(vels), 2) if vels else None,
        "chord_match_rate": (
            round(sum(1 for c in report.chord_checks if c.status == "match") / len(report.chord_checks), 4)
            if report.chord_checks
            else None
        ),
    }
    return report


def _cluster_by_onset(events: List[NoteEvent], window: float) -> List[List[NoteEvent]]:
    out: List[List[NoteEvent]] = []
    current: List[NoteEvent] = []
    start = None
    for ev in events:
        if start is None or ev.onset - start <= window:
            current.append(ev)
            if start is None:
                start = ev.onset
        else:
            out.append(current)
            current = [ev]
            start = ev.onset
    if current:
        out.append(current)
    return out


def _chord_checks(
    intended: List[NoteEvent],
    heard: List[NoteEvent],
    chord_window: float,
    time_tolerance: float,
) -> List[ChordCheck]:
    checks: List[ChordCheck] = []
    for cluster in _cluster_by_onset(intended, chord_window):
        if len(cluster) < 2:
            continue
        t0 = min(e.onset for e in cluster)
        t1 = max(e.onset for e in cluster)
        intended_set = sorted({e.pitch for e in cluster})
        heard_set = sorted(
            {
                h.pitch
                for h in heard
                if (t0 - time_tolerance) <= h.onset <= (t1 + time_tolerance)
            }
        )
        missing = [p for p in intended_set if p not in heard_set]
        extra = [p for p in heard_set if p not in intended_set]
        if not missing and not extra:
            status = "match"
        elif not missing:
            status = "match"  # heard extras don't necessarily fail the chord
        elif len(missing) < len(intended_set):
            status = "partial"
        else:
            status = "mismatch"
        checks.append(
            ChordCheck(
                time=round(t0, 6),
                intended_pitches=intended_set,
                heard_pitches=heard_set,
                missing=missing,
                extra=extra,
                status=status,
            )
        )
    return checks


_PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _pitch_name(p: int) -> str:
    return f"{_PITCH_NAMES[p % 12]}{p // 12 - 1}"


def report_to_markdown(report: CompareReport, title: str = "Render comparison") -> str:
    s = report.summary
    lines: List[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- intended: {s['intended_count']} notes")
    lines.append(f"- heard:    {s['heard_count']} notes")
    lines.append(f"- matched:  {s['matched']} ({s['match_rate'] * 100:.1f}%)")
    lines.append(f"- wrong pitch: {s['wrong_pitch']}")
    lines.append(f"- missing:  {s['missing']}")
    lines.append(f"- extra:    {s['extra']}")
    if s["mean_timing_drift_sec"] is not None:
        lines.append(
            f"- timing drift: mean {s['mean_timing_drift_sec'] * 1000:.1f} ms, "
            f"max |Δ| {s['max_abs_timing_drift_sec'] * 1000:.1f} ms"
        )
    if s["mean_velocity_diff"] is not None:
        lines.append(f"- velocity diff: mean {s['mean_velocity_diff']:+.1f}")
    if s["chord_match_rate"] is not None:
        lines.append(f"- chord match rate: {s['chord_match_rate'] * 100:.1f}%")
    lines.append("")

    if report.missing:
        lines.append("## Missing notes (intended, not heard)")
        for n in report.missing[:50]:
            lines.append(
                f"- {_pitch_name(n['pitch'])} (pitch={n['pitch']}) at {n['start_time']:.3f}s "
                f"dur={n['duration']:.3f}s"
            )
        if len(report.missing) > 50:
            lines.append(f"- … +{len(report.missing) - 50} more")
        lines.append("")

    if report.extra:
        lines.append("## Extra notes (heard, not intended)")
        for n in report.extra[:50]:
            lines.append(
                f"- {_pitch_name(n['pitch'])} (pitch={n['pitch']}) at {n['start_time']:.3f}s "
                f"dur={n['duration']:.3f}s"
            )
        if len(report.extra) > 50:
            lines.append(f"- … +{len(report.extra) - 50} more")
        lines.append("")

    if report.wrong_pitch:
        lines.append("## Wrong-pitch hits")
        for w in report.wrong_pitch[:50]:
            intended_p = w["intended"]["pitch"]
            heard_p = w["heard"]["pitch"]
            lines.append(
                f"- intended {_pitch_name(intended_p)} → heard {_pitch_name(heard_p)} "
                f"({w['pitch_diff_semitones']:+d} st) at {w['intended']['start_time']:.3f}s"
            )
        lines.append("")

    if report.chord_checks:
        lines.append("## Chord checks")
        for c in report.chord_checks[:25]:
            iset = ",".join(_pitch_name(p) for p in c.intended_pitches)
            hset = ",".join(_pitch_name(p) for p in c.heard_pitches)
            lines.append(f"- t={c.time:.3f}s [{c.status}] intended {{{iset}}} heard {{{hset}}}")
        lines.append("")

    return "\n".join(lines) + "\n"
