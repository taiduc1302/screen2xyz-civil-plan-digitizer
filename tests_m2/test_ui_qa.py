"""UI regression tests for the autonomous-QA fixes that need a real Tk root
(Esc-only-while-recording, confirmed-region gating, non-blocking Draw-region
countdown, recovery bar, finalized-outcome header). Skips cleanly where a Tk
display cannot be created."""

from __future__ import annotations

import unittest

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.withdraw()
    _HAS_TK = True
    # See test_guided_workflow: retain the display probe for this module so
    # ttk has no destroyed root in a deferred ThemeChanged dispatch.
except Exception:  # pragma: no cover - headless CI without a display
    _HAS_TK = False


def _make_app():
    from screen2xyz_m2.ui.app import M2App
    M2App._welcome_shown_this_process = True
    app = M2App()
    return app


@unittest.skipUnless(_HAS_TK, "no Tk display")
class EscEmergencyStopGuardTests(unittest.TestCase):
    """§2: Esc = emergency stop must NOT fire on the setup screen after a
    Test capture created a controller - only while actually recording."""

    def test_emergency_stop_is_noop_without_a_scheduler(self):
        app = _make_app()
        try:
            self.assertIsNone(app.scheduler)
            # Simulate a controller existing (as after Test capture) but no
            # recording in progress.
            class _FakeController:
                class machine:
                    state = "REGIONS_CONFIGURED"
            app.controller = _FakeController()
            # Must be a no-op: no exception, no screen teardown attempt.
            app._emergency_stop()
            # The setup table still exists (screen was not replaced).
            self.assertTrue(hasattr(app, "table"))
            self.assertTrue(app.table.winfo_exists())
        finally:
            app.root.destroy()


@unittest.skipUnless(_HAS_TK, "no Tk display")
class ConfirmedRegionGatingTests(unittest.TestCase):
    """§3: a newly added field carries a placeholder rect but must show
    'no region drawn' and block Preview until a region is confirmed."""

    def test_new_field_is_not_confirmed_and_shows_no_region(self):
        from screen2xyz_m2.models import SourceConfig, new_source_id
        app = _make_app()
        try:
            app.scope = {"type": "window", "hwnd": 1, "pid": 1,
                        "client_w": 900, "client_h": 320}
            app._add_source()
            self.assertEqual(len(app.sources), 1)
            self.assertNotIn(app.sources[0].source_id,
                             app._confirmed_regions)
            row = app.table.item(app.table.get_children()[0], "values")
            self.assertIn("no region drawn", row)
            # Preview must be blocked with a clear message.
            app._preview()
            self.assertIn("Draw a region", app.status.get())
        finally:
            app.root.destroy()

    def test_manual_rect_edit_confirms_the_region(self):
        app = _make_app()
        try:
            app.scope = {"type": "window", "hwnd": 1, "pid": 1,
                        "client_w": 900, "client_h": 320}
            app._add_source()
            sid = app.sources[0].source_id
            app._confirmed_regions.add(sid)  # emulate the edit-apply path
            app._refresh_table()
            row = app.table.item(app.table.get_children()[0], "values")
            self.assertIn("region set", row)
        finally:
            app.root.destroy()


@unittest.skipUnless(_HAS_TK, "no Tk display")
class DrawRegionCountdownTests(unittest.TestCase):
    """§4: Draw region must not block the main thread with time.sleep."""

    def test_draw_region_uses_non_blocking_countdown(self):
        import inspect
        from screen2xyz_m2.ui.app import M2App
        src = inspect.getsource(M2App._draw_region)
        self.assertNotIn("time.sleep", src)
        self.assertIn("after(", src)


@unittest.skipUnless(_HAS_TK, "no Tk display")
class DrawRegionBlockedWorkerTests(unittest.TestCase):
    """region_snapshot() is worker-dependent (statemachine._WORKER_DEPENDENT)
    exactly like Test capture/Retest - after three consecutive real-worker
    setup failures it latches setup_worker_blocked and any further
    region_snapshot() call raises IllegalAction, not WorkerError. Draw
    region's countdown previously caught only WorkerError, so a blocked
    worker fell through to the generic top-level callback-exception handler
    with no mention of Retry, and the button itself stayed clickable -
    a real dead end reproduced on an owner's real-target G-E-REAL run."""

    def test_draw_region_uses_illegal_action_and_blocked_state(self):
        import inspect
        from screen2xyz_m2.ui.app import M2App
        src = inspect.getsource(M2App._draw_region)
        self.assertIn("except IllegalAction", src)
        self.assertIn("setup_worker_blocked", src)
        self.assertIn("Retry", src)

    def test_draw_region_button_disabled_when_worker_blocked(self):
        app = _make_app()
        try:
            class _FakeMachine:
                state = "REGIONS_CONFIGURED"
                setup_worker_blocked = True
                preview_confirmed_revision = None
                configuration_revision = 0

            class _FakeController:
                machine = _FakeMachine()

            app.controller = _FakeController()
            app._refresh_next_step()
            self.assertEqual(str(app.draw_region_btn["state"]), "disabled")

            app.controller.machine.setup_worker_blocked = False
            app._refresh_next_step()
            self.assertEqual(str(app.draw_region_btn["state"]), "normal")
        finally:
            app.root.destroy()


@unittest.skipUnless(_HAS_TK, "no Tk display")
class FinalizedOutcomeHeaderTests(unittest.TestCase):
    """§16: the finalized screen must not claim 'Final CSV finalized' when
    the summary is empty (e.g. an emergency stop that never finalized)."""

    def test_empty_summary_shows_stopped_not_finalized(self):
        app = _make_app()
        try:
            app._build_finalized({})
            texts = _all_label_texts(app.root)
            self.assertTrue(any("Stopped" in t for t in texts))
            self.assertFalse(any("Final CSV finalized" in t for t in texts))
            # Usability MAJOR: a non-developer must not be told to run a
            # terminal command. The screen now reassures the data is safe and
            # points at an in-app rebuild (the "python -m ... recover" CLI
            # hint is gone).
            self.assertTrue(any("safe" in t.lower() for t in texts))
            self.assertTrue(any("rebuild" in t.lower() for t in texts))
            self.assertFalse(any("python -m" in t for t in texts))
        finally:
            app.root.destroy()

    def test_real_summary_shows_finalized(self):
        app = _make_app()
        try:
            app._build_finalized({
                "event_count": 3, "final_csv_row_count": 3,
                "final_csv_row_count_verified": True,
                "live_csv_snapshot_row_count": 3, "warnings": []})
            texts = _all_label_texts(app.root)
            self.assertTrue(any("Final CSV finalized" in t for t in texts))
        finally:
            app.root.destroy()

    def test_unverified_summary_does_not_claim_finalized_success(self):
        """Usability MAJOR: when the on-disk final CSV does not match the
        journal (rows missing), the bold header used to still read 'Final
        CSV finalized' in black, reassuring the owner at the exact moment
        real data was lost. The headline must agree with the red detail
        line."""
        app = _make_app()
        try:
            app._build_finalized({
                "event_count": 42, "final_csv_row_count": 30,
                "final_csv_row_count_verified": False,
                "live_csv_snapshot_row_count": 42,
                "warnings": ["FINAL_CSV_ROW_COUNT_MISMATCH: 30 vs 42"]})
            texts = _all_label_texts(app.root)
            self.assertFalse(any("Final CSV finalized" in t for t in texts))
            self.assertTrue(any("could NOT be verified" in t for t in texts))
            # The raw warning code is humanized, not shown verbatim.
            self.assertTrue(any("missing from the final CSV" in t
                                for t in texts))
        finally:
            app.root.destroy()

    def test_xyz_outcome_line_is_shown_when_summary_has_xyz(self):
        app = _make_app()
        try:
            app._build_finalized({
                "event_count": 5, "final_csv_row_count": 5,
                "final_csv_row_count_verified": True,
                "live_csv_snapshot_row_count": 5, "warnings": [],
                "xyz": {"written": True, "row_count": 5,
                        "excluded_event_count": 0, "eligible": True,
                        "reason": ""}})
            texts = _all_label_texts(app.root)
            self.assertTrue(any("XYZ export: WRITTEN" in t for t in texts))
        finally:
            app.root.destroy()


def _all_label_texts(widget):
    import tkinter.ttk as ttk
    out = []
    for child in widget.winfo_children():
        for cls in (ttk.Label,):
            if isinstance(child, cls):
                try:
                    out.append(str(child.cget("text")))
                except Exception:
                    pass
        out.extend(_all_label_texts(child))
    return out


if __name__ == "__main__":
    unittest.main()
