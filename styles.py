"""Style variants for the HUD renderer."""
from __future__ import annotations
import math
from PIL import Image, ImageDraw
from renderer import HudRenderer, _load_font, _fmt_time, _confidence_color, _wpm_color
from schema import Transcript


# ── helpers ──────────────────────────────────────────────────────────────────

def _strip(word: str) -> str:
    return word.strip(".,!?;:\"'()-–—").upper()


def _glow(draw: ImageDraw.ImageDraw, pos, text, font, color, radii=(6, 4, 2)):
    """Approximate glow by layering semi-transparent halos."""
    r, g, b = color[:3]
    for radius, alpha in zip(radii, (40, 80, 140)):
        for dx in range(-radius, radius + 1, max(1, radius // 2)):
            for dy in range(-radius, radius + 1, max(1, radius // 2)):
                draw.text((pos[0] + dx, pos[1] + dy), text, font=font,
                          fill=(r, g, b, alpha), anchor="mm")
    draw.text(pos, text, font=font, fill=(*color[:3], 255), anchor="mm")


def _outline(draw, pos, text, font, color, size=4):
    for dx in range(-size, size + 1):
        for dy in range(-size, size + 1):
            if dx != 0 or dy != 0:
                draw.text((pos[0] + dx, pos[1] + dy), text, font=font,
                          fill=(0, 0, 0, 200), anchor="mm")
    draw.text(pos, text, font=font, fill=color, anchor="mm")


# ── Minimal ───────────────────────────────────────────────────────────────────

class MinimalRenderer(HudRenderer):
    """Word only. Confidence reflected in word color. Thin underline as gauge."""

    def render_frame(self, t: float) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        W, H = self.width, self.height

        active = self._active_word(t)
        if not active:
            return img

        dt = t - active.start
        conf = active.confidence
        # Word color shifts white → yellow → red with confidence
        r = 255
        g = int(min(255, conf * 2 * 255)) if conf < 0.5 else 255
        b = int(conf * 255)
        word_color = (r, g, b, 255)
        word_text = _strip(active.word)

        self._draw_word(img, word_text, word_color, dt)

        # Thin confidence underline
        draw2 = ImageDraw.Draw(img)
        bbox_tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bbox_tmp)
        bd.text((W // 2, int(H * 0.46)), word_text, font=self.font_word,
                fill=(255, 255, 255, 255), anchor="mm")
        bb = bbox_tmp.getbbox()
        if bb:
            scale = max(0.5, self._bounce_scale(dt))
            tw = int((bb[2] - bb[0]) * scale)
            ux = W // 2 - tw // 2
            uy = int(H * 0.46) + int((bb[3] - bb[1]) * scale * 0.55)
            uw = int(tw * conf)
            c = _confidence_color(conf)
            if uw > 0:
                draw2.rectangle([ux, uy + 6, ux + uw, uy + 10], fill=(*c, 220))
            draw2.rectangle([ux + uw, uy + 6, ux + tw, uy + 10], fill=(60, 60, 60, 120))

        return img


# ── Neon / Futuristic targeting HUD ──────────────────────────────────────────

class NeonRenderer(HudRenderer):
    """Futuristic HUD. Word lower-right with black outline + glow, confidence bar beneath."""

    BLUE   = (0, 210, 255)
    AMBER  = (255, 170, 0)
    DIM    = (0, 70, 110)

    def render_frame(self, t: float) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        W, H = self.width, self.height
        p = self.pad
        s = H / 1080

        active = self._active_word(t)
        clip = self.transcript.active_clip(t)
        clip_t = (t - clip.start) if clip else t
        clip_dur = clip.duration if clip else self.transcript.duration
        title = clip.title if clip else self.transcript.title
        progress = min(clip_t / clip_dur, 1.0) if clip_dur > 0 else 0.0
        conf = active.confidence if active else 0.0

        # ── Top-left: title ──
        draw.text((p, int(p * 1.2)), f"[ {title.upper()} ]",
                  font=self.font_label, fill=(*self.BLUE, 220), anchor="lt")

        # ── Top-right: time ──
        draw.text((W - p, int(p * 1.2)),
                  f"{_fmt_time(clip_t)}  /  {_fmt_time(clip_dur)}",
                  font=self.font_label, fill=(*self.DIM, 210), anchor="rt")

        # ── Lower-right word: right-aligned, black outline + glow ──
        word_cx = W // 2   # temp render anchor; we right-align on paste
        word_cy = int(H * 0.68)

        if active:
            dt = t - active.start
            word_text = _strip(active.word)
            scale = max(0.5, self._bounce_scale(dt))

            tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(tmp)
            outline_px = max(3, int(5 * s))
            for dx in range(-outline_px, outline_px + 1):
                for dy in range(-outline_px, outline_px + 1):
                    if dx != 0 or dy != 0:
                        d.text((word_cx + dx, word_cy + dy), word_text,
                               font=self.font_word, fill=(0, 0, 0, 230), anchor="mm")
            _glow(d, (word_cx, word_cy), word_text, self.font_word, self.BLUE)

            bb = tmp.getbbox()
            if bb:
                pad = 12
                x1 = max(0, bb[0] - pad); y1 = max(0, bb[1] - pad)
                x2 = min(W, bb[2] + pad); y2 = min(H, bb[3] + pad)
                nw = max(1, int((x2 - x1) * scale))
                nh = max(1, int((y2 - y1) * scale))
                scaled_word = tmp.crop((x1, y1, x2, y2)).resize((nw, nh), Image.LANCZOS)
                wx = W - p - nw          # right-align to edge
                wy = word_cy - nh // 2
                img.paste(scaled_word, (wx, wy), scaled_word)

                # ── Confidence bar directly below word ──
                bar_gap  = int(12 * s)
                bar_h    = max(6, int(10 * s))
                bar_w    = nw
                bar_x    = wx
                bar_y    = wy + nh + bar_gap

                draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
                               fill=(*self.DIM, 80))
                fw = int(bar_w * conf)
                if fw > 0:
                    draw.rectangle([bar_x, bar_y, bar_x + fw, bar_y + bar_h],
                                   fill=(*self.AMBER, 210))
                    draw.rectangle([bar_x + fw - 2, bar_y, bar_x + fw + 2, bar_y + bar_h],
                                   fill=(*self.AMBER, 255))
                draw.text((bar_x - int(8 * s), bar_y + bar_h // 2),
                          f"{int(conf * 100)}%",
                          font=self.font_small, fill=(*self.AMBER, 200), anchor="rm")

        # ── Bottom timeline with diamond marker ──
        tl_y  = H - int(p * 1.1)
        tl_x1 = p
        tl_x2 = W - p
        tl_w  = tl_x2 - tl_x1
        pos_x = tl_x1 + int(tl_w * progress)

        draw.line([(tl_x1, tl_y), (tl_x2, tl_y)], fill=(*self.DIM, 100), width=max(1, int(2*s)))
        if pos_x > tl_x1:
            draw.line([(tl_x1, tl_y), (pos_x, tl_y)],
                      fill=(*self.BLUE, 180), width=max(2, int(3*s)))
        d_size = int(7 * s)
        draw.polygon([
            (pos_x, tl_y - d_size), (pos_x + d_size, tl_y),
            (pos_x, tl_y + d_size), (pos_x - d_size, tl_y),
        ], fill=(*self.BLUE, 255))

        return img


# ── Subtitle ──────────────────────────────────────────────────────────────────

class SubtitleRenderer(HudRenderer):
    """Word at bottom in subtitle style. Confidence as colored border."""

    def render_frame(self, t: float) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        W, H = self.width, self.height
        p = self.pad

        active = self._active_word(t)
        clip = self.transcript.active_clip(t)
        title = clip.title if clip else self.transcript.title

        # Subtle title top-left
        draw.text((p, p), title, font=self.font_small, fill=(220, 220, 255, 160), anchor="lt")

        if not active:
            return img

        dt = t - active.start
        conf = active.confidence
        conf_color = _confidence_color(conf)
        word_text = _strip(active.word)
        scale = max(0.5, self._bounce_scale(dt))

        # Measure word at normal size
        tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(tmp)
        word_y = int(H * 0.82)
        _outline(d, (W // 2, word_y), word_text, self.font_word, (255, 255, 255, 255))
        bb = tmp.getbbox()
        if not bb:
            return img

        bpad = 24
        x1 = max(0, bb[0] - bpad)
        y1 = max(0, bb[1] - bpad)
        x2 = min(W, bb[2] + bpad)
        y2 = min(H, bb[3] + bpad)

        # Background bar behind word (full width)
        bar_top = y1 - 4
        bar_bot = y2 + 4
        draw.rectangle([0, bar_top, W, bar_bot], fill=(0, 0, 0, 180))

        # Confidence color border (bottom edge)
        border_h = 5
        fill_w = int(W * conf)
        draw.rectangle([0, bar_bot - border_h, fill_w, bar_bot], fill=(*conf_color, 220))
        draw.rectangle([fill_w, bar_bot - border_h, W, bar_bot], fill=(40, 40, 40, 120))

        # Render word with bounce
        nw = max(1, int((x2-x1)*scale))
        nh = max(1, int((y2-y1)*scale))
        cropped = tmp.crop((x1, y1, x2, y2))
        scaled = cropped.resize((nw, nh), Image.LANCZOS)
        img.paste(scaled, (W//2 - nw//2, word_y - nh//2), scaled)

        return img


# ── Retro Terminal ────────────────────────────────────────────────────────────

class RetroRenderer(HudRenderer):
    """Green-on-black terminal aesthetic. Word types in character by character."""

    GREEN      = (0, 255, 65)
    GREEN_DIM  = (0, 140, 35)
    GREEN_DARK = (0, 40, 10)
    SCAN_ALPHA = 35
    TYPE_SPEED = 18  # chars per second

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scale = self.height / 1080
        mono_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
        ]
        size = int(110 * scale)
        for path in mono_candidates:
            try:
                from PIL import ImageFont
                self.font_word = ImageFont.truetype(path, size)
                self.font_title = ImageFont.truetype(path, int(30 * scale))
                self.font_label = ImageFont.truetype(path, int(24 * scale))
                self.font_small = ImageFont.truetype(path, int(20 * scale))
                break
            except (IOError, OSError):
                continue

    def _scanlines(self, img: Image.Image):
        draw = ImageDraw.Draw(img)
        W, H = img.size
        for y in range(0, H, 3):
            draw.line([(0, y), (W, y)], fill=(0, 0, 0, self.SCAN_ALPHA))

    def render_frame(self, t: float) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        W, H = self.width, self.height
        p = self.pad

        active = self._active_word(t)
        clip = self.transcript.active_clip(t)
        clip_t = (t - clip.start) if clip else t
        clip_dur = clip.duration if clip else self.transcript.duration
        title = clip.title if clip else self.transcript.title
        progress = min(clip_t / clip_dur, 1.0) if clip_dur > 0 else 0.0

        # Top bar
        draw.rectangle([0, 0, W, self.bar_h], fill=(0, 10, 0, 220))
        draw.rectangle([0, self.bar_h - 2, W, self.bar_h], fill=(*self.GREEN, 180))
        draw.text((p, self.bar_h // 2), f"> {title.upper()}",
                  font=self.font_title, fill=(*self.GREEN, 230), anchor="lm")
        draw.text((W - p, self.bar_h // 2),
                  f"{_fmt_time(clip_t)} / {_fmt_time(clip_dur)}",
                  font=self.font_title, fill=(*self.GREEN_DIM, 200), anchor="rm")

        # Word — type-in effect
        if active:
            dt = t - active.start
            word_text = _strip(active.word)
            n_visible = min(len(word_text), max(1, int(dt * self.TYPE_SPEED) + 1))
            visible = word_text[:n_visible]
            cursor = "_" if n_visible < len(word_text) else ""

            word_y = int(H * 0.46)
            display = visible + cursor

            # Subtle green glow (dim layer behind)
            draw.text((W // 2 + 2, word_y + 2), display, font=self.font_word,
                      fill=(*self.GREEN_DARK, 180), anchor="mm")
            draw.text((W // 2, word_y), display, font=self.font_word,
                      fill=(*self.GREEN, 240), anchor="mm")

        # Confidence panel
        conf = active.confidence if active else 0.0
        cy_panel = int(H * 0.68)
        bar_x = p + int(160 * (H / 1080))
        pct_w = int(80 * (H / 1080))
        bar_w = W - bar_x - p - pct_w
        draw.rectangle([p-10, cy_panel-10, W-p+10, cy_panel+self.gauge_h+10],
                       fill=(0, 10, 0, 210))
        draw.rectangle([p-10, cy_panel-10, W-p+10, cy_panel-8],
                       fill=(*self.GREEN_DIM, 150))
        draw.text((p, cy_panel + self.gauge_h // 2), "> CONF",
                  font=self.font_label, fill=(*self.GREEN_DIM, 200), anchor="lm")
        draw.rectangle([bar_x, cy_panel, bar_x+bar_w, cy_panel+self.gauge_h],
                       fill=(0, 20, 0, 200))
        fw = int(bar_w * conf)
        if fw > 0:
            draw.rectangle([bar_x, cy_panel, bar_x+fw, cy_panel+self.gauge_h],
                           fill=(*self.GREEN, 180))
        draw.text((bar_x+bar_w+p//2, cy_panel+self.gauge_h//2),
                  f"{int(conf*100)}%", font=self.font_label,
                  fill=(*self.GREEN, 220), anchor="lm")

        # Timeline
        tl_y = H - p - self.timeline_h
        draw.rectangle([0, tl_y-16, W, H], fill=(0, 10, 0, 210))
        draw.rectangle([0, tl_y-16, W, tl_y-14], fill=(*self.GREEN_DIM, 150))
        draw.text((p, tl_y-12), "> TIMELINE", font=self.font_small,
                  fill=(*self.GREEN_DIM, 180), anchor="lb")
        draw.rectangle([p, tl_y, W-p, tl_y+self.timeline_h], fill=(0, 20, 0, 200))
        ftl = int((W-2*p) * progress)
        if ftl > 0:
            draw.rectangle([p, tl_y, p+ftl, tl_y+self.timeline_h],
                           fill=(*self.GREEN, 200))

        self._scanlines(img)
        return img


# ── Diagnostic ────────────────────────────────────────────────────────────────

class DiagnosticRenderer(HudRenderer):
    """Full quality dashboard: quality score, confidence, WPM bar, word duration, gap."""

    def render_frame(self, t: float) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        W, H = self.width, self.height
        p = self.pad
        s = H / 1080

        active = self._active_word(t)
        metrics = self._pacing_metrics(t)
        clip = self.transcript.active_clip(t)
        clip_t = (t - clip.start) if clip else t
        clip_dur = clip.duration if clip else self.transcript.duration
        title = clip.title if clip else self.transcript.title
        progress = min(clip_t / clip_dur, 1.0) if clip_dur > 0 else 0.0

        # --- Top bar ---
        draw.rectangle([0, 0, W, self.bar_h], fill=(10, 10, 20, self.bg_alpha))
        draw.text((p, self.bar_h // 2), title, font=self.font_title,
                  fill=(220, 220, 255, 255), anchor="lm")
        draw.text((W - p, self.bar_h // 2),
                  f"{_fmt_time(clip_t)} / {_fmt_time(clip_dur)}",
                  font=self.font_title, fill=(180, 180, 200, 255), anchor="rm")

        # --- Active word ---
        if active:
            self._draw_word(img, _strip(active.word), (255, 255, 255, 255),
                            t - active.start)

        # --- Metrics panel ---
        conf = active.confidence if active else 0.0
        wpm = metrics["wpm"]
        word_dur = metrics["word_duration"]
        word_gap = metrics["word_gap"]
        quality = metrics["quality_score"]

        row_gap = int(10 * s)
        row_stride = self.gauge_h + row_gap
        label_w = int(180 * s)
        pct_w = int(110 * s)
        bar_x = p + label_w
        bar_w = W - bar_x - p - pct_w

        panel_top = int(H * 0.56)
        panel_h = 3 * row_stride + 2 * (self.gauge_h + row_gap) + int(p * 0.6)
        draw.rectangle([p - 10, panel_top - 10, W - p + 10, panel_top + panel_h],
                       fill=(10, 10, 20, self.bg_alpha))

        def bar_row(y, label, fraction, text, color):
            draw.text((p, y + self.gauge_h // 2), label,
                      font=self.font_label, fill=(150, 150, 170, 255), anchor="lm")
            draw.rectangle([bar_x, y, bar_x + bar_w, y + self.gauge_h],
                           fill=(30, 30, 50, 220))
            fw = int(bar_w * max(0.0, min(1.0, fraction)))
            if fw > 0:
                draw.rectangle([bar_x, y, bar_x + fw, y + self.gauge_h],
                               fill=(*color, 230))
            draw.text((bar_x + bar_w + p // 2, y + self.gauge_h // 2),
                      text, font=self.font_label, fill=(200, 200, 220, 255), anchor="lm")

        def text_row(y, label, text):
            draw.text((p, y + self.gauge_h // 2), label,
                      font=self.font_label, fill=(150, 150, 170, 255), anchor="lm")
            draw.text((W - p, y + self.gauge_h // 2), text,
                      font=self.font_label, fill=(200, 200, 220, 255), anchor="rm")

        y = panel_top
        bar_row(y, "QUALITY", quality / 100, str(quality), _confidence_color(quality / 100))
        y += row_stride
        bar_row(y, "CONF", conf, f"{int(conf * 100)}%",
                _confidence_color(conf) if active else (60, 60, 80))
        y += row_stride
        bar_row(y, "WPM", min(wpm / 250, 1.0) if wpm > 0 else 0.0,
                f"{int(wpm)}", _wpm_color(wpm))
        y += row_stride
        text_row(y, "WORD DUR", f"{word_dur:.2f} s" if word_dur is not None else "—")
        y += row_stride
        text_row(y, "GAP", f"{word_gap:.2f} s" if word_gap is not None else "—")

        # --- Timeline ---
        tl_y = H - p - self.timeline_h
        tl_x = p
        tl_w = W - 2 * p
        draw.rectangle([0, tl_y - 16, W, H], fill=(10, 10, 20, self.bg_alpha))
        draw.text((tl_x, tl_y - 12), "TIMELINE", font=self.font_small,
                  fill=(120, 120, 140, 200), anchor="lb")
        draw.rectangle([tl_x, tl_y, tl_x + tl_w, tl_y + self.timeline_h],
                       fill=(30, 30, 50, 220))
        fill_tl = int(tl_w * progress)
        if fill_tl > 0:
            draw.rectangle([tl_x, tl_y, tl_x + fill_tl, tl_y + self.timeline_h],
                           fill=(100, 140, 220, 230))

        return img


# ── registry ──────────────────────────────────────────────────────────────────

STYLES: dict[str, type] = {
    "default":    HudRenderer,
    "minimal":    MinimalRenderer,
    "neon":       NeonRenderer,
    "subtitle":   SubtitleRenderer,
    "retro":      RetroRenderer,
    "diagnostic": DiagnosticRenderer,
}


def get_renderer(style: str, transcript: Transcript, **kwargs) -> HudRenderer:
    cls = STYLES.get(style.lower())
    if cls is None:
        raise ValueError(f"Unknown style '{style}'. Choose from: {', '.join(STYLES)}")
    return cls(transcript=transcript, **kwargs)
