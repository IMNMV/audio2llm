from __future__ import annotations

from typing import List, Optional, Tuple

from .types import NoteEvent, TranscriptionMeta, TranscriptionResult


def transcribe_audio(
    path: str,
    prefer_polyphonic: bool = True,
    hop_length: int = 512,
    sr: Optional[int] = None,
) -> TranscriptionResult:
    """
    Transcribe a WAV (or other audio) file to note events.

    Strategy:
    - If `prefer_polyphonic` and Basic Pitch is available, use it for polyphonic notes.
    - Else, run a monophonic fallback via librosa.pyin f0 tracking + note segmentation.
    - Estimate tempo via beat tracking and key via chroma profile.

    Returns a TranscriptionResult with events and meta.
    """
    # Try polyphonic first if requested
    if prefer_polyphonic:
        result = _try_basic_pitch(path)
        if result is not None:
            # Fill meta
            events = result
            sr_loaded, tempo, key = _estimate_meta(path, sr=sr)
            return TranscriptionResult(
                events=events,
                meta=TranscriptionMeta(sample_rate=sr_loaded, tempo_bpm=tempo, key=key),
            )
        else:
            # Visible notice for users when polyphonic path is unavailable
            print("[audio2llm] Basic Pitch not available or failed; using monophonic fallback.")

    # Fallback to monophonic
    events, sr_loaded = _monophonic_transcribe(path, hop_length=hop_length, sr=sr)
    _, tempo, key = _estimate_meta(path, sr=sr_loaded)
    return TranscriptionResult(
        events=events, meta=TranscriptionMeta(sample_rate=sr_loaded, tempo_bpm=tempo, key=key)
    )


def _try_basic_pitch(path: str) -> Optional[List[NoteEvent]]:
    """
    Use Spotify Basic Pitch if installed. Returns list of NoteEvent or None.

    Note: basic_pitch>=0.4 expects an audio PATH, not a raw array.
    """
    try:
        # Lazy import so CLI --help doesn't require deps
        from basic_pitch.inference import predict
        from basic_pitch import ICASSP_2022_MODEL_PATH as MODEL_PATH

        # Call predict with file path and model path. Keep conservative thresholds.
        model_output, midi_data, note_events = predict(
            path,
            MODEL_PATH,
            onset_threshold=0.5,
            frame_threshold=0.3,
        )

        events: List[NoteEvent] = []
        # basic_pitch returns tuples: (start, end, pitch_midi, amplitude, [optional bends])
        for tup in note_events:
            # Unpack first four elements, ignore any extras
            start, end, pitch, amp = tup[:4]
            dur = max(0.0, float(end) - float(start))
            vel = int(max(1, min(127, round(float(amp) * 127))))
            events.append(
                NoteEvent(onset=float(start), duration=dur, pitch=int(pitch), velocity=vel, track=0)
            )

        # Sort by onset
        events.sort(key=lambda e: (e.onset, e.pitch))
        return events
    except Exception:
        return None


def _monophonic_transcribe(
    path: str, hop_length: int = 512, sr: Optional[int] = None
) -> Tuple[List[NoteEvent], int]:
    """
    Fallback monophonic transcription using librosa.pyin for f0, then segment to notes.
    """
    import numpy as np
    import librosa

    y, sr_loaded = librosa.load(path, sr=sr, mono=True)
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr_loaded,
        frame_length=2048,
        hop_length=hop_length,
    )

    times = librosa.frames_to_time(np.arange(len(f0)), sr=sr_loaded, hop_length=hop_length)

    # Convert f0 to midi, with NaNs for unvoiced
    midi = librosa.hz_to_midi(f0)

    # Segment into notes: group contiguous voiced frames with stable pitch
    events: List[NoteEvent] = []
    idx = 0
    min_note_frames = 3  # ~3*hop seconds
    max_pitch_jump = 0.75  # semitones within a note

    while idx < len(midi):
        # Skip unvoiced
        while idx < len(midi) and (np.isnan(midi[idx]) or not voiced_flag[idx]):
            idx += 1
        if idx >= len(midi):
            break

        start = idx
        last_pitch = midi[idx]
        idx += 1
        while idx < len(midi):
            if np.isnan(midi[idx]) or not voiced_flag[idx]:
                break
            if abs(midi[idx] - last_pitch) > max_pitch_jump:
                break
            last_pitch = 0.8 * last_pitch + 0.2 * midi[idx]  # smooth
            idx += 1

        end = idx
        if end - start >= min_note_frames:
            onset = float(times[start])
            offset = float(times[end - 1] + (times[1] - times[0]))
            duration = max(0.01, offset - onset)
            pitch_val = int(round(np.nanmean(midi[start:end])))
            events.append(NoteEvent(onset=onset, duration=duration, pitch=pitch_val, velocity=90, track=0))

    # Merge very short gaps between same-pitch notes
    merged: List[NoteEvent] = []
    for ev in sorted(events, key=lambda e: (e.onset, e.pitch)):
        if merged and ev.pitch == merged[-1].pitch and ev.onset <= merged[-1].onset + merged[-1].duration + 0.05:
            # extend
            prev = merged[-1]
            new_end = max(prev.onset + prev.duration, ev.onset + ev.duration)
            prev.duration = new_end - prev.onset
        else:
            merged.append(ev)

    return merged, sr_loaded


def _estimate_meta(path: str, sr: Optional[int] = None) -> Tuple[int, Optional[float], Optional[str]]:
    """Estimate tempo and key using librosa; returns (sample_rate, tempo_bpm, key_str)."""
    import numpy as np
    import librosa

    y, sr_loaded = librosa.load(path, sr=sr, mono=True)
    # Tempo via beat tracking
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr_loaded)

    # Key via chroma + Krumhansl-Schmuckler template matching
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr_loaded)
    chroma_mean = chroma.mean(axis=1)
    key = _estimate_key_from_chroma(chroma_mean)
    return sr_loaded, float(tempo) if tempo is not None else None, key


def _estimate_key_from_chroma(chroma_mean) -> Optional[str]:
    import numpy as np

    # Krumhansl major/minor profiles (normalized)
    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    major_profile /= major_profile.sum()
    minor_profile /= minor_profile.sum()

    # Rotate profiles for all 12 keys
    scores = []
    pitch_classes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    c = chroma_mean / (chroma_mean.sum() + 1e-8)
    for i in range(12):
        maj = np.roll(major_profile, i)
        minr = np.roll(minor_profile, i)
        scores.append((np.dot(c, maj), f"{pitch_classes[i]} major"))
        scores.append((np.dot(c, minr), f"{pitch_classes[i]} minor"))
    best = max(scores, key=lambda x: x[0])
    return best[1] if best else None
