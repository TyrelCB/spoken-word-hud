# spoken-word-hud

Renders a real-time HUD overlay onto video using word-level speech transcript data. Each frame shows the active spoken word with a bounce animation, a color-coded confidence gauge, a clip-scoped timeline, and a per-clip title bar.

![HUD preview](https://github.com/TyrelCB/spoken-word-hud/raw/master/preview.png)

## Requirements

- Python 3.10+
- [Pillow](https://pillow.readthedocs.io/) (`pip install Pillow`)
- [FFmpeg](https://ffmpeg.org/) (must be on PATH)

```bash
pip install -r requirements.txt
```

## Input format

A JSON file with a `title`, a `words` array, and optionally a `clips` array (added automatically by `combine_transcripts.py`):

```json
{
  "title": "The shutdown",
  "words": [
    { "word": "At",       "start": 0.0,  "end": 0.46, "confidence": 0.93 },
    { "word": "two",      "start": 0.46, "end": 0.72, "confidence": 0.06 },
    { "word": "thirteen", "start": 0.72, "end": 1.10, "confidence": 0.35 }
  ]
}
```

| Field        | Type   | Description                              |
|--------------|--------|------------------------------------------|
| `title`      | string | Displayed in the top-left bar            |
| `word`       | string | The spoken word (punctuation is stripped)|
| `start`      | float  | Word start time in seconds               |
| `end`        | float  | Word end time in seconds                 |
| `confidence` | float  | ASR confidence 0–1 (drives gauge color)  |

`audio_duration` at the top level is accepted as an alias for `duration`.

## Single-clip usage

```bash
python3 main.py --input clip.json --output hud.mp4
```

Overlay on an existing video:

```bash
python3 main.py --input clip.json --overlay background.mp4 --output final.mp4
```

### Options

| Flag            | Default    | Description                                          |
|-----------------|------------|------------------------------------------------------|
| `--input`       | required   | Path to transcript JSON                              |
| `--output`      | required   | Output video path (.mp4)                             |
| `--overlay`     | —          | Source video to alpha-composite the HUD onto         |
| `--fps`         | `30`       | Output frame rate                                    |
| `--size`        | `1920x1080`| Output resolution as `WxH`                           |
| `--bg-alpha`    | `200`      | HUD panel background opacity (0 = transparent, 255 = opaque) |

## Multi-clip usage

For a project with multiple clips, use `combine_transcripts.py` to merge per-clip JSONs into a single timeline-aligned transcript. It auto-detects scene cuts in the source video to correct timing drift between audio duration and actual video clip length, and generates silence-padded audio so narration stays in sync.

### Step 1 — combine transcripts and build padded audio

```bash
python3 combine_transcripts.py word_timing/ combined.json \
  --video background.mp4 \
  --audio-output audio.aac \
  --wav-pattern "/path/to/clip{nn}_voice_seed-{seed}.wav"
```

| Argument          | Description                                                         |
|-------------------|---------------------------------------------------------------------|
| `timing_dir`      | Directory containing `clip*_word_timing.json` files                 |
| `output`          | Path for the combined transcript JSON                               |
| `--video`         | Source video — used to detect actual clip start times via scene cuts|
| `--audio-output`  | Output path for the concatenated, silence-padded AAC audio          |
| `--wav-pattern`   | WAV filename pattern; supports `{n}` (1–20), `{nn}` (01–20), `{seed}` |

WAV pattern example: `"/data/clip{nn}_voice_seed-{seed}.wav"` expands to `clip01_voice_seed-5252001.wav` etc.

### Step 2 — render and composite

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

## HUD layout

```
┌──────────────────────────────────────────────┐
│  Clip title                      00:03 / 00:05│  ← top bar (per-clip)
│──────────────────────────────────────────────│
│                                              │
│               MORNING                        │  ← active word, bounce animation
│                                              │
│  CONFIDENCE  [████████░░]  84%               │  ← green >85%, yellow 60–85%, red <60%
│                                              │
│  TIMELINE  ███████░░░░░░░░░░░░               │  ← clip-scoped progress
└──────────────────────────────────────────────┘
```

- **Title and timer** reset to the current clip on each scene cut
- **Active word** pops in with a damped spring bounce (1.4× → 1.0×) and has a black outline for legibility over busy backgrounds
- **Confidence gauge** reflects ASR certainty — useful for spotting words that may have been misheard
- **Timeline** shows progress through the current clip, not the full video
