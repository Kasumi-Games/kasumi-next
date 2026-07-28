"""Generate the Kasumi avatar frame asset.

Design: Kasumi's hair accessory — two red five-pointed star clips at the
top-left of a coral ring, with champagne-gold glints for balance. Follows
``docs/design/avatar-frame-spec.md``: 512x512 RGBA, avatar circle Ø416
centered and transparent, bold strokes that survive 56-120px rendering.

The five-pointed stars are deliberate: the kit BACKGROUND avoids literal
stars (artistic four-point glints instead), but the hairpin IS a literal red
star — that contrast is the point.

Usage:
    uv run python scripts/draw_kasumi_frame.py
    # writes the frame_kasumi_starbeat inventory-item asset
"""

import sys
import math
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT = (
    ROOT
    / "plugins/inventory/resources/items/avatar_frames/frame_kasumi_starbeat.png"
)

#: Spec geometry (docs/design/avatar-frame-spec.md).
CANVAS = 512
AVATAR_DIAMETER = 416

#: Supersampling factor; everything below is authored at CANVAS * SS.
SS = 4

# Palette — matches the KasumiKit constants.
CORAL = (255, 118, 98, 255)
CORAL_LIGHT = (255, 156, 136, 255)
GOLD = (255, 209, 128, 255)
STAR_RED = (235, 52, 60, 255)
STAR_RED_DEEP = (198, 34, 48, 255)
WHITE = (255, 255, 255, 255)


def star_points(cx: float, cy: float, outer: float, *, rotation_deg: float = 0.0):
    """Vertices of a five-pointed star centered at (cx, cy)."""

    inner = outer * 0.42  # slightly chunkier than a strict pentagram (0.382)
    points = []
    rotation = math.radians(rotation_deg) - math.pi / 2
    for index in range(10):
        radius = outer if index % 2 == 0 else inner
        angle = rotation + index * math.pi / 5
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def draw_star(draw: ImageDraw.ImageDraw, cx, cy, outer, *, rotation=0.0):
    """One hairpin star: white sticker stroke, deep-red edge, red body, glint."""

    # Sticker-style white stroke underneath, like the in-game sticker art.
    draw.polygon(star_points(cx, cy, outer * 1.16, rotation_deg=rotation), fill=WHITE)
    draw.polygon(
        star_points(cx, cy, outer * 1.05, rotation_deg=rotation), fill=STAR_RED_DEEP
    )
    draw.polygon(star_points(cx, cy, outer, rotation_deg=rotation), fill=STAR_RED)
    # A small white four-point glint on the body reads as gloss at every size.
    hl_angle = math.radians(rotation - 115)
    hlx = cx + outer * 0.34 * math.cos(hl_angle)
    hly = cy + outer * 0.34 * math.sin(hl_angle)
    glint_points = []
    glint_size = outer * 0.22
    for index in range(8):
        radius = glint_size if index % 2 == 0 else glint_size * 0.22
        angle = -math.pi / 2 + index * math.pi / 4
        glint_points.append(
            (hlx + radius * math.cos(angle), hly + radius * math.sin(angle))
        )
    draw.polygon(glint_points, fill=(255, 226, 226, 240))


def draw_glint(image: Image.Image, cx, cy, size, color=GOLD):
    """A four-point glint — the kit background's light language, for balance."""

    points = []
    inner = size * 0.18
    for index in range(8):
        radius = size if index % 2 == 0 else inner
        angle = -math.pi / 2 + index * math.pi / 4
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    ImageDraw.Draw(image).polygon(points, fill=color)


def main() -> None:
    big = CANVAS * SS
    center = big / 2
    avatar_radius = AVATAR_DIAMETER * SS / 2   # 832

    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # --- rings -----------------------------------------------------------
    ring_width = 17 * SS                      # 17px @512 — bold at 64px render
    gold_gap = 4 * SS
    gold_width = 5 * SS

    gold_outer = avatar_radius + ring_width + gold_gap + gold_width
    draw.ellipse(
        (center - gold_outer, center - gold_outer,
         center + gold_outer, center + gold_outer),
        outline=GOLD, width=gold_width,
    )
    ring_outer = avatar_radius + ring_width
    draw.ellipse(
        (center - ring_outer, center - ring_outer,
         center + ring_outer, center + ring_outer),
        outline=CORAL, width=ring_width,
    )
    # Inner highlight rim: a light edge where the ring meets the avatar, so
    # the frame separates from dark avatars and dark themes alike.
    draw.ellipse(
        (center - avatar_radius - 3 * SS, center - avatar_radius - 3 * SS,
         center + avatar_radius + 3 * SS, center + avatar_radius + 3 * SS),
        outline=CORAL_LIGHT, width=3 * SS,
    )

    # --- gold glints, lower-right arc (balances the stars) ---------------
    # White-cored gold so they stay visible against the coral band.
    for angle_deg, size_px in ((38, 16), (12, 11), (61, 10)):
        angle = math.radians(angle_deg)
        radius = avatar_radius + ring_width * 0.55
        gx = center + radius * math.cos(angle)
        gy = center + radius * math.sin(angle)
        draw_glint(image, gx, gy, size_px * SS, color=GOLD)
        draw_glint(image, gx, gy, size_px * SS * 0.45, color=WHITE)

    # --- punch the avatar window through the ring layer ------------------
    # The base layer (rings + glints) must never cover the avatar at all.
    # The hairpin stars are composited AFTER this punch so they may overlap
    # the rim like a real clip; their own intrusion is bounded by placement
    # (asserted below), not by clipping — clipping is what mangled v1.
    window = Image.new("L", (big, big), 255)
    ImageDraw.Draw(window).ellipse(
        (center - avatar_radius, center - avatar_radius,
         center + avatar_radius, center + avatar_radius),
        fill=0,
    )
    from PIL import ImageChops

    image.putalpha(ImageChops.multiply(image.getchannel("A"), window))
    # Re-draw the inner highlight rim the punch just removed (it sits half
    # inside the circle by design).
    draw = ImageDraw.Draw(image)
    draw.ellipse(
        (center - avatar_radius - 3 * SS, center - avatar_radius - 3 * SS,
         center + avatar_radius + 3 * SS, center + avatar_radius + 3 * SS),
        outline=CORAL_LIGHT, width=3 * SS,
    )

    # --- the hairpin: two red stars, top-left ----------------------------
    # Centers sit on the ring band; the arms overlap both outward and a
    # little inward — the clipped-on look. Max intrusion is asserted.
    stars = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    star_draw = ImageDraw.Draw(stars)

    big_outer = 48 * SS
    big_angle = math.radians(218)  # screen: up-left of center
    big_dist = avatar_radius + ring_width * 0.55
    bx = center + big_dist * math.cos(big_angle)
    by = center + big_dist * math.sin(big_angle)
    draw_star(star_draw, bx, by, big_outer, rotation=-16)

    small_outer = 31 * SS
    small_angle = math.radians(194)
    small_dist = avatar_radius + ring_width * 0.75
    sx = center + small_dist * math.cos(small_angle)
    sy = center + small_dist * math.sin(small_angle)
    draw_star(star_draw, sx, sy, small_outer, rotation=14)

    # Placement guard: the deepest star reach into the avatar circle stays
    # within the spec's 48px (@512) decoration allowance.
    for dist, outer in ((big_dist, big_outer), (small_dist, small_outer)):
        intrusion = (avatar_radius - (dist - outer * 1.16)) / SS
        assert intrusion <= 48, f"star intrudes {intrusion:.0f}px > 48px"

    # Soft drop shadow under the stars so they sit ON the ring.
    shadow = stars.getchannel("A").point(lambda a: a * 88 // 255)
    shadow_layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    shadow_layer.putalpha(shadow)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(4 * SS))
    image.alpha_composite(shadow_layer, (2 * SS, 3 * SS))
    image.alpha_composite(stars)

    # A tiny white companion star above the pins, like a caught sparkle.
    mini = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    mini_draw = ImageDraw.Draw(mini)
    mini_draw.polygon(
        star_points(center + (avatar_radius + ring_width * 0.9) * math.cos(math.radians(242)),
                    center + (avatar_radius + ring_width * 0.9) * math.sin(math.radians(242)),
                    12 * SS, rotation_deg=24),
        fill=WHITE,
    )
    image.alpha_composite(mini)

    result = image.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.save(OUTPUT)
    print(f"wrote {OUTPUT} ({result.size[0]}x{result.size[1]})")


if __name__ == "__main__":
    main()
