from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .transcribe import transcribe_audio
from .midi import save_midi
from .textfmt import events_to_lines
from .jsonio import (
    events_to_ableton_json,
    result_to_json,
    write_json,
    load_notes_json,
)
from .postprocess import apply_postprocess
from .split import split_parts
from .compare import compare_notes, report_to_markdown
from .agent import analyze_render


_SUBCOMMANDS = {"transcribe", "compare", "analyze"}


def _add_transcribe_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("input", help="Path to input audio file (e.g., .wav)")
    p.add_argument("--out-midi", help="Path to write MIDI (.mid)")
    p.add_argument("--out-text", help="Path to write LLM-friendly text (.txt)")
    p.add_argument("--out-json", help="Path to write structured JSON (meta + notes)")
    p.add_argument(
        "--out-ableton-json",
        help="Path to write bare list of Ableton-shaped note dicts",
    )
    p.add_argument(
        "--ableton-units",
        choices=["seconds", "beats"],
        default="seconds",
        help="Time unit for Ableton JSON output (default seconds)",
    )
    p.add_argument(
        "--out-split",
        help="Directory to write bass.json, chords.json, melody.json, all_notes.json",
    )
    p.add_argument(
        "--out-report",
        help="Path to write a human-readable transcription report (.md)",
    )
    p.add_argument("--prefer-polyphonic", action="store_true", help="Prefer polyphonic model")
    p.add_argument("--no-polyphonic", action="store_true", help="Force monophonic fallback")
    p.add_argument("--sr", type=int, default=None, help="Target sample rate for processing")
    # Postprocess
    p.add_argument(
        "--quantize",
        help="Snap onsets to this division (e.g. 1/16, 1/8t). Requires known tempo.",
    )
    p.add_argument(
        "--quantize-strength",
        type=float,
        default=1.0,
        help="0..1. 1.0 = full snap, 0.5 = halfway. Default 1.0.",
    )
    p.add_argument("--quantize-duration", action="store_true", help="Also snap durations")
    p.add_argument(
        "--preserve-human-timing",
        action="store_true",
        help="No-op flag for clarity; means: do not pass --quantize",
    )
    p.add_argument(
        "--humanize-velocity",
        type=int,
        default=None,
        metavar="AMOUNT",
        help="Add +/-AMOUNT velocity jitter",
    )
    p.add_argument(
        "--min-duration",
        type=float,
        default=None,
        help="Drop notes shorter than this many seconds",
    )
    p.add_argument(
        "--tempo-override",
        type=float,
        default=None,
        help="Override estimated tempo (used for quantize + MIDI writing)",
    )


def _run_transcribe(args: argparse.Namespace) -> int:
    prefer_poly = args.prefer_polyphonic and not args.no_polyphonic
    if args.no_polyphonic:
        prefer_poly = False

    result = transcribe_audio(args.input, prefer_polyphonic=prefer_poly, sr=args.sr)

    tempo = args.tempo_override if args.tempo_override else result.meta.tempo_bpm
    if args.tempo_override:
        result.meta.tempo_bpm = float(args.tempo_override)

    if args.preserve_human_timing and args.quantize:
        print("[audio2llm] --preserve-human-timing overrides --quantize; skipping quantize")
        args.quantize = None

    result.events = apply_postprocess(
        result.events,
        tempo_bpm=tempo,
        quantize_div=args.quantize,
        quantize_strength=args.quantize_strength,
        quantize_duration=args.quantize_duration,
        humanize_vel=args.humanize_velocity,
        min_duration=args.min_duration,
    )

    if args.out_midi:
        out_midi = Path(args.out_midi)
        out_midi.parent.mkdir(parents=True, exist_ok=True)
        save_midi(result.events, str(out_midi), tempo_bpm=tempo or 120.0)

    if args.out_text:
        out_text = Path(args.out_text)
        out_text.parent.mkdir(parents=True, exist_ok=True)
        lines = events_to_lines(result.events, tempo_bpm=tempo, key=result.meta.key)
        out_text.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.out_json:
        write_json(args.out_json, result_to_json(result, units=args.ableton_units))

    if args.out_ableton_json:
        write_json(
            args.out_ableton_json,
            events_to_ableton_json(result.events, tempo_bpm=tempo, units=args.ableton_units),
        )

    if args.out_split:
        out_dir = Path(args.out_split)
        out_dir.mkdir(parents=True, exist_ok=True)
        parts = split_parts(result.events)
        for name, evs in (
            ("bass", parts.bass),
            ("chords", parts.chords),
            ("melody", parts.melody),
            ("all_notes", parts.all_notes),
        ):
            write_json(
                str(out_dir / f"{name}.json"),
                events_to_ableton_json(evs, tempo_bpm=tempo, units=args.ableton_units),
            )

    if args.out_report:
        _write_transcription_report(args.out_report, result, tempo)

    print(
        f"Transcribed {len(result.events)} notes. "
        f"Tempo={tempo} Key={result.meta.key}"
    )
    if result.meta.warnings:
        print("[audio2llm] warnings:")
        for w in result.meta.warnings:
            print(f"  - {w}")

    if not any(
        [
            args.out_midi,
            args.out_text,
            args.out_json,
            args.out_ableton_json,
            args.out_split,
            args.out_report,
        ]
    ):
        for line in events_to_lines(result.events[:50], tempo_bpm=tempo, key=result.meta.key):
            print(line)
    return 0


def _write_transcription_report(path: str, result, tempo) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Transcription report",
        "",
        f"- notes: {len(result.events)}",
        f"- tempo: {tempo}",
        f"- key: {result.meta.key}",
    ]
    if result.meta.warnings:
        lines.append("")
        lines.append("## Warnings")
        for w in result.meta.warnings:
            lines.append(f"- {w}")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _add_compare_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("intended", help="Path to intended notes JSON")
    p.add_argument("rendered", help="Path to rendered audio file")
    p.add_argument("--out-report", help="Path to write Markdown report")
    p.add_argument("--out-json", help="Path to write structured JSON report")
    p.add_argument("--time-tolerance", type=float, default=0.08)
    p.add_argument("--wrong-pitch-window", type=int, default=2)
    p.add_argument("--no-polyphonic", action="store_true")


def _run_compare(args: argparse.Namespace) -> int:
    intended = load_notes_json(args.intended)
    result = transcribe_audio(args.rendered, prefer_polyphonic=not args.no_polyphonic)
    report = compare_notes(
        intended,
        result.events,
        time_tolerance=args.time_tolerance,
        wrong_pitch_window=args.wrong_pitch_window,
    )

    if args.out_report:
        Path(args.out_report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_report).write_text(report_to_markdown(report), encoding="utf-8")
    if args.out_json:
        write_json(args.out_json, report.to_dict())

    s = report.summary
    print(
        f"matched {s['matched']}/{s['intended_count']} "
        f"({s['match_rate'] * 100:.1f}%); "
        f"missing={s['missing']} extra={s['extra']} wrong_pitch={s['wrong_pitch']}"
    )
    if not args.out_report and not args.out_json:
        print()
        print(report_to_markdown(report))
    return 0


def _add_analyze_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("intended", help="Path to intended notes JSON")
    p.add_argument("rendered", help="Path to rendered audio file")
    p.add_argument("--out-json", required=True, help="Path to write structured feedback JSON")
    p.add_argument("--time-tolerance", type=float, default=0.08)
    p.add_argument("--wrong-pitch-window", type=int, default=2)
    p.add_argument("--tempo-bpm", type=float, default=None)
    p.add_argument("--no-polyphonic", action="store_true")


def _run_analyze(args: argparse.Namespace) -> int:
    feedback = analyze_render(
        args.intended,
        args.rendered,
        tempo_bpm=args.tempo_bpm,
        prefer_polyphonic=not args.no_polyphonic,
        time_tolerance=args.time_tolerance,
        wrong_pitch_window=args.wrong_pitch_window,
    )
    write_json(args.out_json, feedback)
    s = feedback["summary"]
    print(
        f"analyze: matched {s['matched']}/{s['intended_count']} "
        f"({s['match_rate'] * 100:.1f}%); wrote {args.out_json}"
    )
    return 0


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Back-compat: if first arg isn't a known subcommand and doesn't start with '-',
    # treat the whole invocation as `transcribe`.
    if argv and argv[0] not in _SUBCOMMANDS and not argv[0].startswith("-"):
        argv = ["transcribe"] + argv
    elif not argv:
        argv = ["--help"]

    parser = argparse.ArgumentParser(
        prog="audio2llm",
        description=(
            "Audio-to-LLM bridge: transcribe audio to MIDI/text/JSON, split into stems, "
            "and compare LLM-intended notes against a DAW render."
        ),
    )
    sub = parser.add_subparsers(dest="cmd")

    pt = sub.add_parser("transcribe", help="Transcribe audio to MIDI / text / JSON")
    _add_transcribe_args(pt)

    pc = sub.add_parser(
        "compare", help="Compare intended notes JSON against a rendered audio file"
    )
    _add_compare_args(pc)

    pa = sub.add_parser(
        "analyze",
        help="Agent-loop feedback: writes a single JSON containing report + transcription",
    )
    _add_analyze_args(pa)

    args = parser.parse_args(argv)
    if args.cmd == "transcribe":
        return _run_transcribe(args)
    if args.cmd == "compare":
        return _run_compare(args)
    if args.cmd == "analyze":
        return _run_analyze(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
