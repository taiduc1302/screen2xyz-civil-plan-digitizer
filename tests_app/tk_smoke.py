"""Scripted Windows Tk launch smoke and screenshot producer."""

from __future__ import annotations

import argparse
from pathlib import Path


def capture_window(root, output_path: Path) -> None:
    from PIL import ImageGrab

    root.update_idletasks()
    root.update()
    left, top = root.winfo_rootx(), root.winfo_rooty()
    width, height = root.winfo_width(), root.winfo_height()
    ImageGrab.grab(bbox=(left, top, left + width, top + height)).save(output_path)


def run(output_dir: Path) -> None:
    import tkinter as tk

    from screen2xyz_app.ui.app import Screen2XYZApp
    from screen2xyz_app.capture import CapturedPoint
    from screen2xyz_app.ui.layout import APP_TITLE
    from screen2xyz_app.operations import ZoneHealthSnapshot
    from screen2xyz_app.ui.overlay import CaptureOverlay
    from screen2xyz_app.ui.review import SessionReview

    output_dir.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("1080x760+40+40")
    app = Screen2XYZApp(root)
    try:
        capture_window(root, output_dir / "home.png")
        app.show_wizard("Live screen capture")
        capture_window(root, output_dir / "live-capture-wizard.png")
        overlay = CaptureOverlay(
            root, on_pause=lambda: None, on_stop=lambda: None, on_repick=lambda: None
        )
        overlay.show_health(ZoneHealthSnapshot(
            True, False, "Zones are reading normally.", 0,
            {"x": "432,100.25", "y": "5,456,789.75", "z": "49.78"},
        ))
        overlay.show_point(CapturedPoint(
            values={"x": 432100.25, "y": 5456789.75, "z": 49.78},
            source_methods={}, raw_texts={}, confidences={},
        ), 18)
        capture_window(overlay, output_dir / "capture-overlay.png")
        overlay.destroy()

        class ReviewStub:
            @staticmethod
            def points():
                return []

        review = SessionReview(
            root, ReviewStub(), export_xlsx=lambda: None, export_csv=lambda: None
        )
        capture_window(review, output_dir / "session-review.png")
        review.destroy()
        if not app.winfo_exists() or len(app.winfo_children()) == 0:
            raise RuntimeError("Tk workflow did not render")
    finally:
        app.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".tk-smoke"))
    args = parser.parse_args()
    run(args.output)
    print(f"Tk smoke screenshots written to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
