"""Exercise every real Manosaba business fixture and audit its native geometry.

No rendered card is substituted in the delivered gallery: temporary blank
rasters only let the fixture census finish quickly, while every native page
is fully composed and its text extents, coverage and overlap are checked.
"""

import json
import argparse
import tempfile
from pathlib import Path

from PIL import Image
from preview_kasumi_surfaces import _render_gallery

from plugins.render import RenderContext
from plugins.render.kits.manosaba import ManosabaKit
from plugins.render.kits.manosaba.layouts import ROUTES
from plugins.render.kits.manosaba.layouts.folio import FolioPage


def audit():
    reports = []
    original = FolioPage.render

    def checked(page, ctx=None):
        sheet = page.compose(RenderContext(pixel_ratio=1))
        boxes = sheet.glyph_boxes()
        errors = []
        errors.extend(sheet.gutter_conflicts())
        for text, rect in boxes:
            if (
                rect.x < 18
                or rect.right > sheet.width - 18
                or rect.y < 18
                or rect.bottom > sheet.height
            ):
                errors.append(f"out of bounds: {text!r} / {rect}")
        for index, (text, rect) in enumerate(boxes):
            for other, other_rect in boxes[index + 1 :]:
                dx = min(rect.right, other_rect.right) - max(rect.x, other_rect.x)
                dy = min(rect.bottom, other_rect.bottom) - max(rect.y, other_rect.y)
                if dx > 1 and dy > 1:
                    errors.append(f"overlap: {text!r} / {other!r}")
        route = (
            page.surface.draw.__module__.rsplit(".", 1)[-1]
            + "."
            + page.surface.draw.__name__
        )
        reports.append(
            {
                "layout": route,
                "width": sheet.width,
                "height": sheet.height + 24,
                "text_runs": len(sheet.texts),
                "gutters": len(sheet.gutters),
                "book_spine": sheet.book_spine if sheet.book else None,
                "errors": errors,
            }
        )
        return Image.new("RGBA", (sheet.width, sheet.height + 24))

    FolioPage.render = checked
    try:
        with tempfile.TemporaryDirectory(prefix="manosaba-layout-audit-") as folder:
            _, failures = _render_gallery(Path(folder), "manosaba")
            from plugins.tour.render.leaderboard import render_leaderboard

            render_leaderboard(
                {
                    "初级": [("樱羽艾玛", 42.13), ("二阶堂希罗", 46.8)],
                    "中级": [("新玩家", 123.45)],
                },
                ManosabaKit(),
            )
    finally:
        FolioPage.render = original
    missing = sorted(set(ROUTES.values()) - {r["layout"] for r in reports})
    return {"pages": reports, "failures": failures, "missing": missing}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path(".cache/manosaba-layout-audit.json")
    )
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    errors = (
        report["failures"]
        + report["missing"]
        + [e for p in report["pages"] for e in p["errors"]]
    )
    print(
        f"Audited {len(report['pages'])} pages / {len(ROUTES)} layouts; {len(errors)} errors"
    )
    for error in errors:
        print(error)
    raise SystemExit(bool(errors))
