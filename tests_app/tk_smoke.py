"""Scripted Windows Tk launch smoke and screenshot producer."""

from __future__ import annotations

import argparse
import os
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

    os.environ["SCREEN2XYZ_SKIP_FIRST_RUN"] = "1"
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
        overlay_actions = []
        overlay = CaptureOverlay(
            root,
            on_pause=lambda: overlay_actions.append("pause"),
            on_stop=lambda: overlay_actions.append("stop"),
            on_repick=lambda: overlay_actions.append("repick"),
        )
        overlay.show_health(ZoneHealthSnapshot(
            True, False, "Zones are reading normally.", 0,
            {"x": "432,100.25", "y": "5,456,789.75", "z": "49.78"},
        ))
        overlay.show_point(CapturedPoint(
            values={"x": 432100.25, "y": 5456789.75, "z": 49.78},
            source_methods={}, raw_texts={}, confidences={},
        ), 18)
        overlay.pause_button.invoke()
        overlay.repick_button.invoke()
        overlay.stop_button.invoke()
        if overlay_actions != ["pause", "repick", "stop"]:
            raise RuntimeError("overlay controls did not dispatch")
        capture_window(overlay, output_dir / "capture-overlay.png")
        overlay.destroy()

        class ReviewStub:
            @staticmethod
            def points():
                return [
                    {
                        "id": 1, "point_number": "TP-20", "x": 432100.25,
                        "y": 5456789.75, "z": 49.78, "description": "Existing",
                        "created_utc": "2026-08-02T09:30:00Z",
                    },
                    {
                        "id": 2, "point_number": "TP-21", "x": 432101.42,
                        "y": 5456788.84, "z": 49.92, "description": "Design",
                        "created_utc": "2026-08-02T09:30:01Z",
                    },
                    {
                        "id": 3, "point_number": "TP-22", "x": 432102.59,
                        "y": 5456787.93, "z": 50.11, "description": "Review",
                        "created_utc": "2026-08-02T09:30:02Z",
                    },
                ]

        export_actions = []
        review = SessionReview(
            root,
            ReviewStub(),
            export_xlsx=lambda: export_actions.append("xlsx"),
            export_csv=lambda: export_actions.append("csv"),
        )
        review.filter_text.set("Design")
        review.refresh()
        if len(review.tree.get_children()) != 1:
            raise RuntimeError("review filter smoke failed")
        review.filter_text.set("")
        review.sort("z")
        review.export_xlsx_button.invoke()
        review.export_csv_button.invoke()
        if export_actions != ["xlsx", "csv"]:
            raise RuntimeError("review re-export controls did not dispatch")
        capture_window(review, output_dir / "session-review.png")
        review.destroy()
        app.show_wizard("Load image")
        capture_window(root, output_dir / "plan-capture-wizard.png")
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
