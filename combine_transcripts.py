"""Combine per-clip word_timing JSONs into a single timeline-adjusted transcript.

When --video is provided, scene cuts are auto-detected to use the actual clip
start times from the video, fixing timing drift. Also generates a padded audio
file where each WAV is extended with silence to match its video clip duration.
"""
import json
import re
import subprocess
import sys
from pathlib import Path


def _detect_scene_cuts(video_path: str) -> list[float]:
    result = subprocess.run(
        ["ffmpeg", "-i", video_path,
         "-vf", "select=gt(scene\\,0.3),showinfo", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    cuts = []
    for line in result.stderr.splitlines():
        if "pts_time:" in line:
            m = re.search(r"pts_time:([0-9.]+)", line)
            if m:
                cuts.append(float(m.group(1)))
    return sorted(set(cuts))


def _video_duration(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1", video_path],
        capture_output=True, text=True,
    )
    return float(result.stdout.split("=")[1].strip())


def _build_padded_audio(clip_files: list[tuple[str, float, float]], output_path: str):
    """Concatenate WAVs, each padded with silence to match its video clip duration."""
    tmp_parts = []
    for i, (wav, audio_dur, video_dur) in enumerate(clip_files):
        pad = max(0.0, video_dur - audio_dur)
        part = f"/tmp/_padded_clip_{i:02d}.aac"
        subprocess.run(
            ["ffmpeg", "-y", "-i", wav,
             "-af", f"apad=pad_dur={pad:.4f}",
             "-t", str(video_dur),
             "-c:a", "aac", part],
            capture_output=True,
        )
        tmp_parts.append(part)

    concat_list = "/tmp/_padded_concat.txt"
    Path(concat_list).write_text("\n".join(f"file '{p}'" for p in tmp_parts))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", concat_list, "-c", "copy", output_path],
        capture_output=True,
    )
    print(f"Padded audio → {output_path}")


def combine(
    timing_dir: Path,
    output_path: Path,
    video_path: str | None = None,
    audio_output: str | None = None,
    wav_pattern: str | None = None,
):
    clip_jsons = sorted(timing_dir.glob("clip*_word_timing.json"))
    if not clip_jsons:
        sys.exit(f"No clip*_word_timing.json files found in {timing_dir}")

    # Detect video clip boundaries
    if video_path:
        cuts = _detect_scene_cuts(video_path)
        vid_dur = _video_duration(video_path)
        clip_starts = [0.0] + cuts
        clip_ends = cuts + [vid_dur]
        print(f"Detected {len(cuts)} scene cuts in video ({vid_dur:.2f}s total)")
    else:
        clip_starts = None
        clip_ends = None

    combined_words = []
    clip_metadata = []
    audio_offset = 0.0
    audio_parts = []  # (wav_path, audio_dur, video_dur)

    for i, clip_path in enumerate(clip_jsons):
        data = json.loads(clip_path.read_text())
        title = data.get("title", f"Clip {i + 1}")
        audio_dur = float(data.get("audio_duration", data.get("duration", 0)))

        if clip_starts:
            v_start = clip_starts[i]
            v_dur = clip_ends[i] - clip_starts[i]
        else:
            v_start = audio_offset
            v_dur = audio_dur

        clip_metadata.append({
            "id": i + 1,
            "title": title,
            "start": round(v_start, 4),
            "duration": round(v_dur, 4),
        })

        for w in data["words"]:
            combined_words.append({
                "word": w["word"],
                "start": round(w["start"] + v_start, 4),
                "end":   round(w["end"]   + v_start, 4),
                "confidence": w["confidence"],
            })

        if wav_pattern:
            n = i + 1
            wav = wav_pattern.format(n=n, nn=f"{n:02d}", seed=5252000 + n)
            audio_parts.append((wav, audio_dur, v_dur))

        audio_offset += audio_dur

    total_dur = clip_ends[-1] if clip_ends else audio_offset

    out = {
        "title": clip_metadata[0]["title"] if clip_metadata else "Combined",
        "duration": round(total_dur, 4),
        "clips": clip_metadata,
        "words": combined_words,
    }
    output_path.write_text(json.dumps(out, indent=2))
    print(f"Combined {len(clip_jsons)} clips, {len(combined_words)} words, {total_dur:.2f}s → {output_path}")

    if audio_output and audio_parts:
        _build_padded_audio(audio_parts, audio_output)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("timing_dir", help="Directory containing clip*_word_timing.json files")
    p.add_argument("output", help="Output combined JSON path")
    p.add_argument("--video", default=None, help="Source video for scene-cut detection")
    p.add_argument("--audio-output", default=None, help="Output path for padded audio")
    p.add_argument("--wav-pattern", default=None,
                   help="WAV filename pattern, e.g. '/path/clip{nn}_voice_seed-{seed}.wav'")
    args = p.parse_args()
    combine(
        Path(args.timing_dir), Path(args.output),
        video_path=args.video,
        audio_output=args.audio_output,
        wav_pattern=args.wav_pattern,
    )
