from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class WordEntry:
    word: str
    start: float
    end: float
    confidence: float


@dataclass
class Transcript:
    title: str
    words: List[WordEntry]
    duration: float


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
        for field in ("word", "start", "end", "confidence"):
            if field not in w:
                raise ValueError(f"Word entry {i} missing field '{field}'")
        words.append(WordEntry(
            word=str(w["word"]),
            start=float(w["start"]),
            end=float(w["end"]),
            confidence=float(w["confidence"]),
        ))

    duration = float(raw.get("duration", raw.get("audio_duration", words[-1].end)))
    return Transcript(title=str(raw["title"]), words=words, duration=duration)
