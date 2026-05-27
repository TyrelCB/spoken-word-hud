"""Style variants for the HUD renderer."""
from __future__ import annotations
import math
from PIL import Image, ImageDraw
from renderer import HudRenderer, _load_font, _fmt_time, _confidence_color
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
    """Futuristic targeting HUD. Corner brackets, electric blue + amber, no full-width panels."""

    BLUE   = (0, 210, 255)    # electric cyan-blue
    AMBER  = (255, 170, 0)    # amber for hot / active
    DIM    = (0, 70, 110)     # inactive blue
    WHITE  = (210, 240, 255)  # cool white

    def _bracket_corners(self, draw, x1, y1, x2, y2, color, arm=22, thickness=3):
        """Draw 4 corner L-brackets around a rectangle."""
        a = arm
        c = (*color, 230)
        lw = thickness
        for (px, py, dx, dy) in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
            draw.line([(px, py), (px + dx*a, py)], fill=c, width=lw)
            draw.line([(px, py), (px, py + dy*a)], fill=c, width=lw)

    def _hline(self, draw, y, color, alpha=80, x1=None, x2=None):
        W = self.width
        draw.line([(x1 or 0, y), (x2 or W, y)], fill=(*color, alpha), width=1)

    def render_frame(self, t: float) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        W, H = self.width, self.height
        p = self.pad
        s = H / 1080  # scale factor

        active = self._active_word(t)
        clip = self.transcript.active_clip(t)
        clip_t = (t - clip.start) if clip else t
        clip_dur = clip.duration if clip else self.transcript.duration
        title = clip.title if clip else self.transcript.title
        progress = min(clip_t / clip_dur, 1.0) if clip_dur > 0 else 0.0
        conf = active.confidence if active else 0.0

        # ── Subtle accent lines ──
        self._hline(draw, int(H * 0.12), self.BLUE, 50)
        self._hline(draw, int(H * 0.88), self.BLUE, 50)

        # ── Top-left: [ TITLE ] ──
        tx, ty = p, int(p * 1.2)
        draw.text((tx, ty), f"[ {title.upper()} ]",
                  font=self.font_label, fill=(*self.BLUE, 220), anchor="lt")

        # ── Top-right: time ──
        draw.text((W - p, ty),
                  f"{_fmt_time(clip_t)}  /  {_fmt_time(clip_dur)}",
                  font=self.font_label, fill=(*self.DIM, 210), anchor="rt")

        # ── Screen corner brackets (edge decoration, not around the word) ──
        corner_pad = int(p * 0.7)
        self._bracket_corners(draw,
            corner_pad, corner_pad, W - corner_pad, H - corner_pad,
            self.BLUE, arm=int(30 * s), thickness=max(2, int(3 * s)))

        # ── Center word: black outline + glow ──
        word_y = int(H * 0.46)
        if active:
            dt = t - active.start
            word_text = _strip(active.word)
            scale = max(0.5, self._bounce_scale(dt))

            # Build on temp: outline first, then glow on top
            tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(tmp)
            outline_px = max(3, int(5 * s))
            for dx in range(-outline_px, outline_px + 1):
                for dy in range(-outline_px, outline_px + 1):
                    if dx != 0 or dy != 0:
                        d.text((W // 2 + dx, word_y + dy), word_text,
                               font=self.font_word, fill=(0, 0, 0, 220), anchor="mm")
            _glow(d, (W // 2, word_y), word_text, self.font_word, self.BLUE)

            bb = tmp.getbbox()
            if bb:
                pad = 14
                x1 = max(0, bb[0] - pad)
                y1 = max(0, bb[1] - pad)
                x2 = min(W, bb[2] + pad)
                y2 = min(H, bb[3] + pad)
                nw = max(1, int((x2 - x1) * scale))
                nh = max(1, int((y2 - y1) * scale))
                cropped = tmp.crop((x1, y1, x2, y2))
                scaled_word = cropped.resize((nw, nh), Image.LANCZOS)
                img.paste(scaled_word, (W // 2 - nw // 2, word_y - nh // 2), scaled_word)

        # ── Left edge: vertical confidence meter ──
        meter_x   = int(p * 0.55)
        meter_w   = max(4, int(8 * s))
        meter_top = int(H * 0.30)
        meter_bot = int(H * 0.70)
        meter_h   = meter_bot - meter_top
        fill_h    = int(meter_h * conf)

        # Track
        draw.rectangle([meter_x, meter_top, meter_x + meter_w, meter_bot],
                       fill=(*self.DIM, 60))
        # Fill from bottom
        if fill_h > 0:
            draw.rectangle([meter_x, meter_bot - fill_h, meter_x + meter_w, meter_bot],
                           fill=(*self.AMBER, 200))
            # Glow tip
            draw.rectangle([meter_x - 2, meter_bot - fill_h - 2,
                            meter_x + meter_w + 2, meter_bot - fill_h + 2],
                           fill=(*self.AMBER, 255))
        # Label
        draw.text((meter_x + meter_w // 2, meter_top - int(10 * s)),
                  f"{int(conf*100)}",
                  font=self.font_small, fill=(*self.AMBER, 200), anchor="mb")
        draw.text((meter_x + meter_w // 2, meter_bot + int(8 * s)),
                  "CF", font=self.font_small, fill=(*self.DIM, 180), anchor="mt")

        # ── Bottom: thin timeline with diamond position marker ──
        tl_y  = H - int(p * 1.1)
        tl_x1 = p
        tl_x2 = W - p
        tl_w  = tl_x2 - tl_x1
        pos_x = tl_x1 + int(tl_w * progress)

        draw.line([(tl_x1, tl_y), (tl_x2, tl_y)], fill=(*self.DIM, 100), width=max(1, int(2*s)))
        # Filled portion
        if pos_x > tl_x1:
            draw.line([(tl_x1, tl_y), (pos_x, tl_y)], fill=(*self.BLUE, 180), width=max(2, int(3*s)))
        # Diamond marker
        d_size = int(7 * s)
        draw.polygon([
            (pos_x, tl_y - d_size),
            (pos_x + d_size, tl_y),
            (pos_x, tl_y + d_size),
            (pos_x - d_size, tl_y),
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


# ── registry ──────────────────────────────────────────────────────────────────

STYLES: dict[str, type] = {
    "default":   HudRenderer,
    "minimal":   MinimalRenderer,
    "neon":      NeonRenderer,
    "subtitle":  SubtitleRenderer,
    "retro":     RetroRenderer,
}


def get_renderer(style: str, transcript: Transcript, **kwargs) -> HudRenderer:
    cls = STYLES.get(style.lower())
    if cls is None:
        raise ValueError(f"Unknown style '{style}'. Choose from: {', '.join(STYLES)}")
    return cls(transcript=transcript, **kwargs)
