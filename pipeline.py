from __future__ import annotations
import math
import subprocess
import sys
from pathlib import Path
from renderer import HudRenderer
from schema import Transcript


def render_video(
    renderer: HudRenderer,
    transcript: Transcript,
    output_path: str,
    overlay_path: str | None = None,
    fps: float = 30.0,
) -> None:
    W, H = renderer.width, renderer.height
    total_frames = math.ceil(transcript.duration * fps)
    size_str = f"{W}x{H}"

    if overlay_path:
        cmd = [
            "ffmpeg", "-y",
            "-i", overlay_path,
            "-f", "rawvideo", "-pixel_format", "rgba",
            "-video_size", size_str, "-framerate", str(fps),
            "-i", "pipe:0",
            "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-pixel_format", "rgba",
            "-video_size", size_str, "-framerate", str(fps),
            "-i", "pipe:0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        for frame_idx in range(total_frames):
            t = frame_idx / fps
            img = renderer.render_frame(t)
            proc.stdin.write(img.tobytes())

            if frame_idx % int(fps * 5) == 0:
                pct = int(100 * frame_idx / total_frames)
                print(f"\r  Rendering... {pct}% ({frame_idx}/{total_frames} frames)", end="", flush=True)

        proc.stdin.close()
    except BrokenPipeError:
        stderr = proc.stderr.read()
        proc.wait()
        print(f"\nFFmpeg error:\n{stderr.decode()}", file=sys.stderr)
        sys.exit(1)

    stderr = proc.stderr.read()
    proc.wait()
    if proc.returncode != 0:
        print(f"\nFFmpeg failed:\n{stderr.decode()}", file=sys.stderr)
        sys.exit(1)

    print(f"\r  Rendering... 100% ({total_frames}/{total_frames} frames) — done.")
