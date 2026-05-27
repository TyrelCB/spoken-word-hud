from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class WordEntry:
    word: str
    start: float
    end: float
    confidence: float


@dataclass
class Clip:
    id: int
    title: str
    start: float
    duration: float


@dataclass
class Transcript:
    title: str
    words: List[WordEntry]
    duration: float
    clips: List[Clip] = field(default_factory=list)

    def active_clip(self, t: float) -> Optional[Clip]:
        for clip in reversed(self.clips):
            if t >= clip.start:
                return clip
        return self.clips[0] if self.clips else None


def load_transcript(path: str | Path) -> Transcript:
    raw = json.loads(Path(path).read_text())

    if "title" not in raw:
        raise ValueError("JSON missing required field: 'title'")
    if "words" not in raw or not isinstance(raw["words"], list):
        raise ValueError("JSON missing required field: 'words' (must be a list)")
    if not raw["words"]:
        raise ValueError("'words' list is empty")

    words: List[WordEntry] = []
    for i, w in enumerate(raw["words"]):
        for f in ("word", "start", "end", "confidence"):
            if f not in w:
                raise ValueError(f"Word entry {i} missing field '{f}'")
        words.append(WordEntry(
            word=str(w["word"]),
            start=float(w["start"]),
            end=float(w["end"]),
            confidence=float(w["confidence"]),
        ))

    duration = float(raw.get("duration", raw.get("audio_duration", words[-1].end)))

    clips: List[Clip] = []
    for c in raw.get("clips", []):
        clips.append(Clip(
            id=int(c["id"]),
            title=str(c["title"]),
            start=float(c["start"]),
            duration=float(c["duration"]),
        ))

    return Transcript(title=str(raw["title"]), words=words, duration=duration, clips=clips)
