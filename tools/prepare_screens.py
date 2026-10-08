#!/usr/bin/env python3
"""Build Blur Image Online welcome screenshots from JSON Checker's Chrome captures.

1. Rebrand icon + name to Blur Image Online
2. Clean chrome chrome (same as JSON Checker)
3. Save full-window sources under assets/img/source/
4. Crop the top-right corner so puzzle / pin / toolbar icon read clearly
5. Write 1x and 2x WebP into assets/img/
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BOOT = Path(__file__).resolve().parents[3]
JSON_ROOT = BOOT / "JsonChecker"
BLUR_EXT = BOOT / "BlurImageOnline" / "extension"
SITE = Path(__file__).resolve().parents[1]
OUT = SITE / "assets" / "img"
SOURCE = OUT / "source"
ICON = BLUR_EXT / "icons" / "icon128.png"

SHOTS = {
    "step-pin": {"dark": "7.png", "light": "9.png", "popup": True},
    "step-open": {"dark": "8.png", "light": "10.png", "popup": False},
}

# Full-window height after dropping empty page bottom (same as JSON Checker).
FULL_HEIGHT = 1700

# Top-right crops in full-window coordinates (3420 × FULL_HEIGHT).
# Chosen so puzzle, extensions menu, pin, and room for SVG badges stay in frame.
CROPS = {
    # Leave room on the left for SVG badges 1 / 3.
    "step-pin": (2150, 0, 3420, 900),   # 1270 × 900
    "step-open": (2300, 0, 3420, 400),  # 1120 × 400
}

WIDTHS = {"": 1000, "@2x": 2000}

TRAFFIC_LIGHTS = (0, 0, 168, 84)
SHORTCUT_TILES = (1520, 864, 1915, 1050)
PROMO_CARD = (1128, 1136, 2275, 1311)
GOOGLE_LINKS_BAND = (214, 266)
GOOGLE_LINKS_DONOR_ROW = 300
POPUP_EDGE = 3218
PAGE_LEFT = 3090
PAGE_RIGHT = 3378

# Chrome NTP "AI Mode" floating chip (visible in the pin crop).
AI_MODE_BAR = (940, 685, 2480, 830)

MENU_ICON = (2642, 424, 2670, 452)
TOOLBAR_ICON = (3107, 113, 3136, 142)
NAME_BOX = (2700, 420, 3030, 456)
NAME = "Blur Image Online"


def rounded_icon(src: Image.Image, size: int, radius: int) -> Image.Image:
    icon = src.convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=255
    )
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(icon, (0, 0), mask)
    return out


def fill_rect(
    im: Image.Image, box: tuple[int, int, int, int], color: tuple[int, int, int]
) -> None:
    ImageDraw.Draw(im).rectangle(box, fill=color)


def paste_icon(
    im: Image.Image, box: tuple[int, int, int, int], icon: Image.Image
) -> None:
    x0, y0, x1, y1 = box
    size = max(x1 - x0 + 1, y1 - y0 + 1)
    tile = rounded_icon(icon, size, radius=max(4, size // 5))
    px = x0 + ((x1 - x0 + 1) - size) // 2
    py = y0 + ((y1 - y0 + 1) - size) // 2
    bg = im.getpixel((x0 - 4, y0 + size // 2))
    fill_rect(im, (x0 - 1, y0 - 1, x1 + 1, y1 + 1), bg)
    im.paste(tile, (px, py), tile)


def draw_name(im: Image.Image, theme: str) -> None:
    x0, y0, x1, y1 = NAME_BOX
    bg = im.getpixel((x0 - 8, (y0 + y1) // 2))
    fill_rect(im, NAME_BOX, bg)
    color = (232, 234, 237) if theme == "dark" else (32, 33, 36)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", 26)
    except OSError:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial.ttf", 26
        )
    draw = ImageDraw.Draw(im)
    bbox = draw.textbbox((0, 0), NAME, font=font)
    th = bbox[3] - bbox[1]
    tx = 2709
    ty = y0 + (y1 - y0 - th) // 2 - bbox[1]
    draw.text((tx, ty), NAME, font=font, fill=color)


def rebrand(im: Image.Image, kind: str, theme: str, icon: Image.Image) -> Image.Image:
    im = im.convert("RGB")
    if kind == "step-pin":
        paste_icon(im, MENU_ICON, icon)
        draw_name(im, theme)
    else:
        paste_icon(im, TOOLBAR_ICON, icon)
    return im


def clear_google_links(im: Image.Image, beside_popup: bool) -> None:
    left = POPUP_EDGE if beside_popup else PAGE_LEFT
    top, bottom = GOOGLE_LINKS_BAND
    donor = im.crop(
        (left, GOOGLE_LINKS_DONOR_ROW, PAGE_RIGHT, GOOGLE_LINKS_DONOR_ROW + 1)
    )
    im.paste(donor.resize((PAGE_RIGHT - left, bottom - top)), (left, top))


def clear_ai_mode_bar(im: Image.Image, page: tuple[int, int, int]) -> None:
    """Paint out the NTP AI Mode chip so it does not distract from the pin."""
    im.paste(page, AI_MODE_BAR)


def prepare(name: str, spec: dict, icon: Image.Image) -> None:
    left, top, right, bottom = CROPS[name]
    for theme in ("dark", "light"):
        src = JSON_ROOT / spec[theme]
        im = rebrand(Image.open(src), name, theme, icon)
        px = im.load()
        strip = px[2, 2]
        page = px[100, 1500]

        im.paste(page, SHORTCUT_TILES)
        im.paste(page, PROMO_CARD)
        clear_google_links(im, spec["popup"])
        im.paste(strip, TRAFFIC_LIGHTS)
        clear_ai_mode_bar(im, page)

        full = im.crop((0, 0, im.width, FULL_HEIGHT))

        # Keep a reusable full-window original (branded + cleaned).
        source_path = SOURCE / f"{name}-{theme}.png"
        full.save(source_path, "PNG")
        print(f"  source {source_path.relative_to(SITE)}")

        cropped = full.crop((left, top, right, bottom))

        for suffix, width in WIDTHS.items():
            height = round(cropped.height * width / cropped.width)
            out = OUT / f"{name}-{theme}{suffix}.webp"
            cropped.resize((width, height), Image.LANCZOS).save(
                out, "WEBP", quality=86, method=6
            )
            print(
                f"  {src.name} -> {out.relative_to(SITE)} "
                f"({width}x{height}, crop {cropped.size[0]}x{cropped.size[1]})"
            )


def main() -> int:
    if not ICON.is_file():
        raise SystemExit(f"Missing icon: {ICON}")
    for fname in ("7.png", "8.png", "9.png", "10.png"):
        if not (JSON_ROOT / fname).is_file():
            raise SystemExit(f"Missing JSON Checker capture: {JSON_ROOT / fname}")

    OUT.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    icon = Image.open(ICON)
    for name, spec in SHOTS.items():
        print(name)
        prepare(name, spec, icon)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
