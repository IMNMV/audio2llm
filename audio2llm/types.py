from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class NoteEvent:
    onset: float  # seconds
    duration: float  # seconds
    pitch: int  # MIDI note number 0-127
    velocity: int = 64  # 1-127
    track: int = 0  # for polyphony/parts


@dataclass
class TranscriptionMeta:
    sample_rate: int
    tempo_bpm: Optional[float] = None
    time_signature: Optional[str] = None
    key: Optional[str] = None


@dataclass
class TranscriptionResult:
    events: List[NoteEvent]
    meta: TranscriptionMeta

