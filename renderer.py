from __future__ import annotations
import math
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
from schema import Transcript, WordEntry, Clip


def _fmt_time(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


def _confidence_color(confidence: float) -> Tuple[int, int, int]:
    if confidence >= 0.85:
        return (80, 220, 100)   # green
    if confidence >= 0.60:
        return (240, 200, 60)   # yellow
    return (220, 80, 80)        # red


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


class HudRenderer:
    def __init__(
        self,
        transcript: Transcript,
        width: int = 1920,
        height: int = 1080,
        fps: float = 30.0,
        bg_alpha: int = 200,
    ):
        self.transcript = transcript
        self.width = width
        self.height = height
        self.fps = fps
        self.bg_alpha = bg_alpha

        # Layout constants (scale with height)
        scale = height / 1080
        self.pad = int(40 * scale)
        self.bar_h = int(70 * scale)
        self.gauge_h = int(32 * scale)
        self.timeline_h = int(20 * scale)

        self.font_title = _load_font(int(36 * scale))
        self.font_word = _load_font(int(120 * scale))
        self.font_label = _load_font(int(28 * scale))
        self.font_small = _load_font(int(24 * scale))

        self._flash_duration = 2.0 / fps  # seconds

    def _bounce_scale(self, dt: float) -> float:
        """Damped spring: pops in large, bounces down to 1.0."""
        return 1.0 + 0.40 * math.exp(-10 * dt) * math.cos(20 * dt)

    def _draw_word(self, img: Image.Image, word_text: str, color: tuple, dt: float):
        """Render word centered with bounce scale and black outline."""
        W, H = self.width, self.height
        cx, cy = W // 2, int(H * 0.46)
        scale = max(0.5, self._bounce_scale(dt))

        # Draw onto temp canvas at normal size, then scale the result
        tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(tmp)
        outline = 4
        for dx in range(-outline, outline + 1):
            for dy in range(-outline, outline + 1):
                if dx != 0 or dy != 0:
                    d.text((cx + dx, cy + dy), word_text, font=self.font_word,
                           fill=(0, 0, 0, 220), anchor="mm")
        d.text((cx, cy), word_text, font=self.font_word, fill=color, anchor="mm")

        bbox = tmp.getbbox()
        if not bbox:
            return
        pad = 8
        x1 = max(0, bbox[0] - pad)
        y1 = max(0, bbox[1] - pad)
        x2 = min(W, bbox[2] + pad)
        y2 = min(H, bbox[3] + pad)
        cropped = tmp.crop((x1, y1, x2, y2))

        new_w = max(1, int((x2 - x1) * scale))
        new_h = max(1, int((y2 - y1) * scale))
        scaled = cropped.resize((new_w, new_h), Image.LANCZOS)

        img.paste(scaled, (cx - new_w // 2, cy - new_h // 2), scaled)

    def _active_word(self, t: float) -> Optional[WordEntry]:
        for w in self.transcript.words:
            if w.start <= t <= w.end:
                return w
        return None

    def render_frame(self, t: float) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        W, H = self.width, self.height
        p = self.pad

        active = self._active_word(t)
        clip = self.transcript.active_clip(t)

        # Clip-relative progress and time
        if clip:
            clip_t = t - clip.start
            clip_dur = clip.duration
            title = clip.title
        else:
            clip_t = t
            clip_dur = self.transcript.duration
            title = self.transcript.title
        progress = min(clip_t / clip_dur, 1.0) if clip_dur > 0 else 0.0

        # --- Top bar background ---
        draw.rectangle([0, 0, W, self.bar_h], fill=(10, 10, 20, self.bg_alpha))

        # Title (left)
        draw.text((p, self.bar_h // 2), title, font=self.font_title,
                  fill=(220, 220, 255, 255), anchor="lm")

        # Clip-relative time (right)
        time_str = f"{_fmt_time(clip_t)} / {_fmt_time(clip_dur)}"
        draw.text((W - p, self.bar_h // 2), time_str, font=self.font_title,
                  fill=(180, 180, 200, 255), anchor="rm")

        # --- Active word (center, bounced) ---
        if active:
            dt = t - active.start
            word_color = (255, 255, 255, 255)
            word_text = active.word.strip(".,!?;:\"'()-–—").upper()
            self._draw_word(img, word_text, word_color, dt)

        # --- Confidence gauge ---
        conf_panel_y = int(H * 0.68)
        conf_bar_x = p + int(200 * (H / 1080))
        pct_label_w = int(80 * (H / 1080))
        conf_bar_w = W - conf_bar_x - p - pct_label_w

        conf = active.confidence if active else 0.0
        conf_color = _confidence_color(conf) if active else (60, 60, 80)

        # Panel background
        draw.rectangle(
            [p - 10, conf_panel_y - 10, W - p + 10, conf_panel_y + self.gauge_h + 10],
            fill=(10, 10, 20, self.bg_alpha),
        )
        draw.text((p, conf_panel_y + self.gauge_h // 2), "CONFIDENCE",
                  font=self.font_label, fill=(150, 150, 170, 255), anchor="lm")

        # Bar track
        draw.rectangle([conf_bar_x, conf_panel_y, conf_bar_x + conf_bar_w,
                        conf_panel_y + self.gauge_h], fill=(30, 30, 50, 220))
        # Bar fill
        fill_w = int(conf_bar_w * conf)
        if fill_w > 0:
            draw.rectangle([conf_bar_x, conf_panel_y, conf_bar_x + fill_w,
                            conf_panel_y + self.gauge_h], fill=(*conf_color, 230))

        # Percentage label
        pct_text = f"{int(conf * 100)}%"
        draw.text((conf_bar_x + conf_bar_w + p // 2, conf_panel_y + self.gauge_h // 2),
                  pct_text, font=self.font_label, fill=(200, 200, 220, 255), anchor="lm")

        # --- Timeline bar ---
        tl_y = H - p - self.timeline_h
        tl_x = p
        tl_w = W - 2 * p

        # Panel background
        draw.rectangle([0, tl_y - 16, W, H], fill=(10, 10, 20, self.bg_alpha))

        draw.text((tl_x, tl_y - 12), "TIMELINE", font=self.font_small,
                  fill=(120, 120, 140, 200), anchor="lb")

        # Track
        draw.rectangle([tl_x, tl_y, tl_x + tl_w, tl_y + self.timeline_h],
                       fill=(30, 30, 50, 220))
        # Fill
        fill_tl = int(tl_w * progress)
        if fill_tl > 0:
            draw.rectangle([tl_x, tl_y, tl_x + fill_tl, tl_y + self.timeline_h],
                           fill=(100, 140, 220, 230))

        return img
