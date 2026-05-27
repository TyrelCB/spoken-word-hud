#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from schema import load_transcript
from styles import get_renderer, STYLES
from pipeline import render_video


def parse_size(s: str):
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception:
        raise argparse.ArgumentTypeError(f"Size must be WxH (e.g. 1920x1080), got: {s!r}")


def main():
    parser = argparse.ArgumentParser(
        description="Burn a hyperframes HUD overlay onto a video using a speech transcript JSON."
    )
    parser.add_argument("--input", "-i", required=True, help="Path to transcript JSON")
    parser.add_argument("--output", "-o", required=True, help="Output video path (mp4)")
    parser.add_argument("--overlay", default=None, help="Source video to composite the HUD onto")
    parser.add_argument("--fps", type=float, default=30.0, help="Output frame rate (default: 30)")
    parser.add_argument("--size", type=parse_size, default=(1920, 1080),
                        metavar="WxH", help="Output resolution (default: 1920x1080)")
    parser.add_argument("--bg-alpha", type=int, default=200, metavar="0-255",
                        help="HUD panel background opacity (default: 200)")
    parser.add_argument("--style", default="default",
                        choices=list(STYLES.keys()),
                        help="Visual style (default: default)")
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if args.overlay and not Path(args.overlay).exists():
        print(f"Error: overlay video not found: {args.overlay}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading transcript: {args.input}")
    transcript = load_transcript(args.input)
    print(f"  Title   : {transcript.title}")
    print(f"  Words   : {len(transcript.words)}")
    print(f"  Duration: {transcript.duration:.2f}s")

    w, h = args.size
    renderer = get_renderer(
        args.style,
        transcript=transcript,
        width=w,
        height=h,
        fps=args.fps,
        bg_alpha=args.bg_alpha,
    )

    print(f"Rendering {w}x{h} @ {args.fps}fps → {args.output}")
    if args.overlay:
        print(f"  Compositing over: {args.overlay}")

    render_video(
        renderer=renderer,
        transcript=transcript,
        output_path=args.output,
        overlay_path=args.overlay,
        fps=args.fps,
    )
    print(f"Done: {args.output}")


if __name__ == "__main__":
    main()
