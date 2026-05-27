"""Combine per-clip word_timing JSONs into a single timeline-adjusted transcript."""
import json
import sys
from pathlib import Path


def combine(timing_dir: Path, output_path: Path):
    clips = sorted(timing_dir.glob("clip*_word_timing.json"))
    if not clips:
        sys.exit(f"No clip*_word_timing.json files found in {timing_dir}")

    combined_words = []
    offset = 0.0
    titles = []

    for clip_path in clips:
        data = json.loads(clip_path.read_text())
        titles.append(data.get("title", ""))
        duration = float(data.get("audio_duration", data.get("duration", 0)))
        for w in data["words"]:
            combined_words.append({
                "word": w["word"],
                "start": round(w["start"] + offset, 4),
                "end":   round(w["end"]   + offset, 4),
                "confidence": w["confidence"],
            })
        offset += duration

    out = {
        "title": titles[0] if titles else "Combined",
        "duration": round(offset, 4),
        "words": combined_words,
    }
    output_path.write_text(json.dumps(out, indent=2))
    print(f"Combined {len(clips)} clips, {len(combined_words)} words, {offset:.2f}s → {output_path}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("timing_dir", help="Directory containing clip*_word_timing.json files")
    p.add_argument("output", help="Output combined JSON path")
    args = p.parse_args()
    combine(Path(args.timing_dir), Path(args.output))
