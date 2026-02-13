"""
Lucide-style menu bar icons for OptiMac.

Draws crisp 16×16 template icons using Pillow. Template images are black
silhouettes with alpha — macOS automatically renders them white on dark
menu bars and black on light menu bars.

Icons are cached to ~/Library/Application Support/GerdsenAI/icons/.
"""

import math
from pathlib import Path

# Cache directory
_CACHE_DIR = Path.home() / "Library" / "Application Support" / "GerdsenAI" / "icons"


def _ensure_cache():
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_icon(name: str, size: int = 16) -> str:
    """
    Return path to a cached template icon PNG.
    Creates it on first call. Returns empty string on failure.

    Supported names:
        brain, settings, bar_chart, globe, shield, wrench, radio,
        terminal, monitor, zap
    """
    _ensure_cache()
    path = _CACHE_DIR / f"{name}_{size}.png"
    if path.exists():
        return str(path)

    drawer = _DRAWERS.get(name)
    if not drawer:
        return ""

    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        drawer(draw, size)
        img.save(str(path))
        return str(path)
    except ImportError:
        return ""
    except Exception:
        return ""


# ── Icon Drawing Functions ───────────────────────────────────────────
# Each takes (draw, size) and draws black-on-transparent shapes.
# Line widths are tuned for 16px; scale accordingly.


def _draw_brain(draw, s):
    """Brain icon — circle with neural pathways."""
    c = s / 2
    r = s * 0.38
    lw = max(1, round(s / 12))
    fill = (0, 0, 0, 220)

    # Outer skull
    draw.ellipse(
        [c - r, c - r + 1, c + r, c + r + 1],
        outline=fill,
        width=lw,
    )
    # Midline
    draw.line([(c, c - r + 2), (c, c + r - 1)], fill=fill, width=lw)
    # Left hemisphere curves
    draw.arc(
        [c - r + 1, c - r * 0.5, c + 1, c + r * 0.6],
        start=180,
        end=0,
        fill=fill,
        width=lw,
    )
    # Right hemisphere curves
    draw.arc(
        [c - 1, c - r * 0.5, c + r - 1, c + r * 0.6],
        start=180,
        end=0,
        fill=fill,
        width=lw,
    )


def _draw_settings(draw, s):
    """Gear/cog icon."""
    c = s / 2
    lw = max(1, round(s / 12))
    fill = (0, 0, 0, 220)

    # Inner circle
    ir = s * 0.15
    draw.ellipse(
        [c - ir, c - ir, c + ir, c + ir],
        outline=fill,
        width=lw,
    )
    # Outer ring
    ore = s * 0.32
    draw.ellipse(
        [c - ore, c - ore, c + ore, c + ore],
        outline=fill,
        width=lw,
    )
    # Gear teeth (6 teeth)
    tr = s * 0.42
    for i in range(6):
        angle = math.radians(i * 60)
        x1 = c + ore * math.cos(angle)
        y1 = c + ore * math.sin(angle)
        x2 = c + tr * math.cos(angle)
        y2 = c + tr * math.sin(angle)
        draw.line([(x1, y1), (x2, y2)], fill=fill, width=lw + 1)


def _draw_bar_chart(draw, s):
    """Bar chart icon — three vertical bars."""
    lw = max(2, round(s / 6))
    fill = (0, 0, 0, 220)
    pad = round(s * 0.15)
    bottom = s - pad

    # Three bars of different heights
    bars = [
        (s * 0.2, s * 0.55),  # short
        (s * 0.45, s * 0.2),  # tall
        (s * 0.7, s * 0.38),  # medium
    ]
    for x, top in bars:
        draw.line([(x, top), (x, bottom)], fill=fill, width=lw)

    # Baseline
    draw.line([(pad, bottom), (s - pad, bottom)], fill=fill, width=max(1, lw - 1))


def _draw_globe(draw, s):
    """Globe icon — circle with latitude/longitude lines."""
    c = s / 2
    r = s * 0.4
    lw = max(1, round(s / 12))
    fill = (0, 0, 0, 220)

    # Outer circle
    draw.ellipse(
        [c - r, c - r, c + r, c + r],
        outline=fill,
        width=lw,
    )
    # Vertical meridian (ellipse)
    mr = r * 0.45
    draw.ellipse(
        [c - mr, c - r, c + mr, c + r],
        outline=fill,
        width=lw,
    )
    # Horizontal equator
    draw.line([(c - r, c), (c + r, c)], fill=fill, width=lw)


def _draw_shield(draw, s):
    """Shield icon."""
    lw = max(1, round(s / 12))
    fill = (0, 0, 0, 220)
    pad = round(s * 0.15)
    mid = s / 2

    # Shield outline via polygon
    points = [
        (mid, pad),  # top center
        (s - pad, pad + s * 0.08),  # top right
        (s - pad, s * 0.5),  # mid right
        (mid, s - pad),  # bottom point
        (pad, s * 0.5),  # mid left
        (pad, pad + s * 0.08),  # top left
    ]
    draw.polygon(points, outline=fill)
    # Thicken with line
    for i in range(len(points)):
        draw.line(
            [points[i], points[(i + 1) % len(points)]],
            fill=fill,
            width=lw,
        )


def _draw_wrench(draw, s):
    """Wrench icon."""
    lw = max(1, round(s / 10))
    fill = (0, 0, 0, 220)

    # Handle (diagonal line)
    draw.line(
        [(s * 0.25, s * 0.75), (s * 0.65, s * 0.35)],
        fill=fill,
        width=lw + 1,
    )
    # Head (arc at top-right)
    hr = s * 0.22
    cx, cy = s * 0.7, s * 0.3
    draw.arc(
        [cx - hr, cy - hr, cx + hr, cy + hr],
        start=200,
        end=80,
        fill=fill,
        width=lw,
    )
    # Handle end (small rounded rect at bottom-left)
    draw.ellipse(
        [s * 0.18, s * 0.68, s * 0.32, s * 0.82],
        outline=fill,
        width=lw,
    )


def _draw_radio(draw, s):
    """Radio/signal icon — broadcasting waves."""
    c = s / 2
    lw = max(1, round(s / 12))
    fill = (0, 0, 0, 220)

    # Center dot
    dr = s * 0.08
    draw.ellipse(
        [c - dr, c - dr + 2, c + dr, c + dr + 2],
        fill=fill,
    )
    # Signal arcs (three concentric)
    for i, radius in enumerate([s * 0.2, s * 0.32, s * 0.44]):
        draw.arc(
            [c - radius, c - radius + 2, c + radius, c + radius + 2],
            start=225,
            end=315,
            fill=fill,
            width=lw,
        )


def _draw_terminal(draw, s):
    """Terminal/console icon — >_ prompt."""
    lw = max(1, round(s / 10))
    fill = (0, 0, 0, 220)
    pad = round(s * 0.15)

    # Outer rounded rectangle
    draw.rounded_rectangle(
        [pad, pad, s - pad, s - pad],
        radius=2,
        outline=fill,
        width=lw,
    )
    # Prompt chevron >
    draw.line(
        [(s * 0.25, s * 0.35), (s * 0.42, s * 0.5), (s * 0.25, s * 0.65)],
        fill=fill,
        width=lw,
    )
    # Underscore cursor _
    draw.line(
        [(s * 0.5, s * 0.65), (s * 0.7, s * 0.65)],
        fill=fill,
        width=lw,
    )


def _draw_monitor(draw, s):
    """Monitor/display icon."""
    lw = max(1, round(s / 12))
    fill = (0, 0, 0, 220)
    pad = round(s * 0.1)

    # Screen
    draw.rounded_rectangle(
        [pad, pad, s - pad, s * 0.68],
        radius=1,
        outline=fill,
        width=lw,
    )
    # Stand
    mid = s / 2
    draw.line([(mid, s * 0.68), (mid, s * 0.82)], fill=fill, width=lw)
    # Base
    draw.line(
        [(s * 0.3, s * 0.82), (s * 0.7, s * 0.82)],
        fill=fill,
        width=lw,
    )


def _draw_zap(draw, s):
    """Lightning bolt / zap icon."""
    fill = (0, 0, 0, 220)

    # Lightning bolt polygon
    points = [
        (s * 0.55, s * 0.1),
        (s * 0.3, s * 0.5),
        (s * 0.5, s * 0.5),
        (s * 0.4, s * 0.9),
        (s * 0.7, s * 0.45),
        (s * 0.5, s * 0.45),
    ]
    draw.polygon(points, fill=fill)


# ── Registry ─────────────────────────────────────────────────────────

_DRAWERS = {
    "brain": _draw_brain,
    "settings": _draw_settings,
    "bar_chart": _draw_bar_chart,
    "globe": _draw_globe,
    "shield": _draw_shield,
    "wrench": _draw_wrench,
    "radio": _draw_radio,
    "terminal": _draw_terminal,
    "monitor": _draw_monitor,
    "zap": _draw_zap,
}


def clear_cache():
    """Remove all cached icon files (e.g. after size change)."""
    if _CACHE_DIR.exists():
        for f in _CACHE_DIR.glob("*.png"):
            f.unlink()
