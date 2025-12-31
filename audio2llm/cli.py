from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .transcribe import transcribe_audio
from .midi import save_midi
from .textfmt import events_to_lines


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Transcribe audio (WAV) to MIDI and LLM-friendly text. Uses Basic Pitch if available; otherwise monophonic fallback.",
    )
    p.add_argument("input", help="Path to input audio file (e.g., .wav)")
    p.add_argument("--out-midi", help="Path to write MIDI (.mid)")
    p.add_argument("--out-text", help="Path to write text (.txt)")
    p.add_argument("--prefer-polyphonic", action="store_true", help="Prefer polyphonic model if available (Basic Pitch)")
    p.add_argument("--no-polyphonic", action="store_true", help="Force monophonic fallback")
    p.add_argument("--sr", type=int, default=None, help="Target sample rate for processing")
    args = p.parse_args(argv)

    prefer_poly = args.prefer_polyphonic and not args.no_polyphonic
    if args.no_polyphonic:
        prefer_poly = False

    result = transcribe_audio(args.input, prefer_polyphonic=prefer_poly, sr=args.sr)

    if args.out_midi:
        out_midi = Path(args.out_midi)
        out_midi.parent.mkdir(parents=True, exist_ok=True)
        save_midi(result.events, str(out_midi), tempo_bpm=result.meta.tempo_bpm or 120.0)

    if args.out_text:
        out_text = Path(args.out_text)
        out_text.parent.mkdir(parents=True, exist_ok=True)
        lines = events_to_lines(result.events, tempo_bpm=result.meta.tempo_bpm, key=result.meta.key)
        out_text.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Print a short summary
    print(f"Transcribed {len(result.events)} notes. Tempo={result.meta.tempo_bpm} Key={result.meta.key}")
    if not args.out_midi and not args.out_text:
        # Stream to stdout for quick inspection
        for line in events_to_lines(result.events[:50], tempo_bpm=result.meta.tempo_bpm, key=result.meta.key):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

