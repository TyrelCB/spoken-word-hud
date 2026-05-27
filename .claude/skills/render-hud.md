# spoken-word-hud skill

Renders a word-by-word HUD overlay onto video from a speech transcript JSON. All scripts run from the project root (`/home/tyrel/projects/spoken-word-hud/`). Requires Python 3.10+ with Pillow and FFmpeg on PATH.

## Input JSON format

Every workflow starts with a transcript JSON:

```json
{
  "title": "My Clip",
  "words": [
    { "word": "Hello", "start": 0.0, "end": 0.4, "confidence": 0.95 },
    { "word": "world", "start": 0.4, "end": 0.9, "confidence": 0.82 }
  ]
}
```

Required word fields: `word`, `start`, `end`, `confidence` (0–1). Top-level `audio_duration` is accepted as an alias for `duration`.

## Workflow A — single clip

```bash
# HUD only (black background)
python3 main.py --input clip.json --output hud.mp4

# Composited over a video
python3 main.py --input clip.json --overlay background.mp4 --output final.mp4
```

### All flags for main.py

| Flag | Default | Description |
|------|---------|-------------|
| `--input` / `-i` | required | Transcript JSON path |
| `--output` / `-o` | required | Output `.mp4` path |
| `--overlay` | — | Video to composite HUD onto |
| `--fps` | `30` | Frame rate |
| `--size` | `1920x1080` | Resolution as `WxH` |
| `--bg-alpha` | `200` | HUD panel opacity (0–255) |
| `--style` | `default` | Visual style (see below) |

### Available styles

- `default` — full HUD panel with confidence bar and timeline
- `minimal` — word only, no panel
- `subtitle` — bottom-of-frame subtitle strip
- `retro` — scanline/CRT aesthetic
- `neon` — futuristic targeting HUD, word lower-right, corner brackets

## Workflow B — multi-clip (three steps)

### Step 1 — combine transcripts + build padded audio

```bash
python3 combine_transcripts.py word_timing/ combined.json \
  --video background.mp4 \
  --audio-output audio.aac \
  --wav-pattern "/path/to/clip{nn}_voice_seed-{seed}.wav"
```

- `word_timing/` — directory of `clip*_word_timing.json` files (named exactly that pattern)
- `combined.json` — output path for merged transcript
- `--video` — auto-detects scene cuts to align clip timing with actual video cuts
- `--audio-output` — concatenated AAC with silence padding so audio stays in sync
- `--wav-pattern` — template expanded per clip: `{n}` = 1-based, `{nn}` = zero-padded, `{seed}` = 5252001, 5252002, …

### Step 2 — render HUD

```bash
python3 main.py \
  --input combined.json \
  --overlay background.mp4 \
  --output hud_no_audio.mp4 \
  --size 1024x1024 --fps 24
```

### Step 3 — mux padded audio

```bash
ffmpeg -i hud_no_audio.mp4 -i audio.aac -c:v copy -c:a copy -shortest final.mp4
```

## HUD layout (default style)

```
┌──────────────────────────────────────┐
│  Clip title            00:03 / 00:05 │  ← per-clip title + timer
│  ────────────────────────────────    │
│                                      │
│            MORNING                   │  ← active word, spring bounce
│                                      │
│  CONFIDENCE  [████████░░]  84%       │  ← green >85%, yellow 60–85%, red <60%
│                                      │
│  TIMELINE  ███████░░░░░░░░           │  ← progress through current clip
└──────────────────────────────────────┘
```

## Common tasks

**Change style:** add `--style neon` (or `minimal`, `retro`, `subtitle`) to `main.py`

**Make HUD transparent over video:** lower `--bg-alpha` (e.g. `--bg-alpha 120`)

**Different resolution:** `--size 1024x1024` or `--size 1280x720`

**Higher frame rate:** `--fps 60`

**Check available styles in code:** `from styles import STYLES; print(list(STYLES.keys()))`
