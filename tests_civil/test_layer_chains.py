from __future__ import annotations

import math
import unittest

from screen2xyz_civil.layer_chains import chain_fragments, nearest_gap_stats


def dashes(x0, y, dash=10.0, gap=5.0, n=10, reverse_some=False):
    out = []
    for k in range(n):
        a = (x0 + k * (dash + gap), y)
        b = (a[0] + dash, y)
        out.append([b, a] if (reverse_some and k % 3 == 1) else [a, b])
    return out


def chords(cx, cy, r, start_deg, end_deg, n):
    out = []
    step = (end_deg - start_deg) / n
    for k in range(n):
        a0, a1 = math.radians(start_deg + k * step), math.radians(start_deg + (k + 1) * step)
        out.append([(cx + r * math.cos(a0), cy + r * math.sin(a0)),
                    (cx + r * math.cos(a1), cy + r * math.sin(a1))])
    return out


class StraightLineTests(unittest.TestCase):
    def test_dashes_become_one_line_whose_length_spans_the_gaps(self):
        r = chain_fragments(dashes(0, 0))
        self.assertEqual(len(r["chains"]), 1)
        c = r["chains"][0]
        self.assertAlmostEqual(c["length"], 10 * 10 + 9 * 5, places=6)
        self.assertEqual(sorted(c["members"]), list(range(10)))
        self.assertFalse(c["closed"])
        self.assertEqual(r["branches"], [])

    def test_reversed_fragments_are_oriented_into_the_chain(self):
        r = chain_fragments(dashes(0, 0, reverse_some=True))
        self.assertEqual(len(r["chains"]), 1)
        self.assertAlmostEqual(r["chains"][0]["length"], 145.0, places=6)

    def test_the_gap_tolerance_is_read_from_the_linetype(self):
        r = chain_fragments(dashes(0, 0, gap=5.0))
        self.assertAlmostEqual(r["gap_stats"]["p90"], 5.0, places=6)
        self.assertAlmostEqual(r["gap_tol"], 7.5, places=6)

    def test_a_real_break_is_not_jumped(self):
        # two runs of dashes on one line, 60 pt apart: the linetype gap is 5
        r = chain_fragments(dashes(0, 0) + dashes(145 + 60, 0))
        self.assertEqual(len(r["chains"]), 2)

    def test_an_explicit_tolerance_too_small_joins_nothing(self):
        r = chain_fragments(dashes(0, 0), gap_tol=1.0)
        self.assertEqual(len(r["chains"]), 10)

    def test_two_parallel_lines_stay_separate(self):
        r = chain_fragments(dashes(0, 0) + dashes(0, 100))
        self.assertEqual(len(r["chains"]), 2)
        self.assertEqual({round(c["points"][0][1]) for c in r["chains"]}, {0, 100})

    def test_a_parallel_line_inside_the_gap_tolerance_is_another_line_not_a_branch(self):
        # DEMO-001 sheet 04: the pavement edge and the back of the 0.30 m
        # gravel shoulder are dashed lines 3.4 pt apart on one layer, with
        # staggered dashes. Distance and heading cannot tell them apart;
        # the lateral offset from each dash's own axis can.
        a = dashes(0, 0)
        b = dashes(6, 3.4)  # staggered by 6 pt, offset 3.4 pt
        r = chain_fragments(a + b)
        self.assertEqual(len(r["chains"]), 2)
        for c in r["chains"]:
            ys = {round(p[1], 1) for p in c["points"]}
            self.assertEqual(len(ys), 1, "a chain crossed between the two lines")
        self.assertEqual(r["branches"], [])


class DoubleLineTests(unittest.TestCase):
    def test_a_pipe_drawn_as_a_double_dashed_line_chains_into_two_lines(self):
        # DEMO-001-11 D2-D3: two parallel dashed lines 3.66 pt apart, dash 17,
        # gap 8.5. Every dash's nearest endpoint is its twin, so a tolerance
        # read from nearest-anything (5.1) never reaches the next dash (8.5)
        # and the run stayed sixteen single dashes.
        left = [[(0, 400 + 25.5 * k), (0, 417 + 25.5 * k)] for k in range(8)]
        right = [[(3.66, 400 + 25.5 * k), (3.66, 417 + 25.5 * k)] for k in range(8)]
        r = chain_fragments(left + right)
        self.assertAlmostEqual(r["gap_stats"]["p90"], 8.5, places=6)
        self.assertEqual(len(r["chains"]), 2)
        for c in r["chains"]:
            self.assertEqual(len(c["members"]), 8)
            self.assertAlmostEqual(c["length"], 195.5, places=6)


class ArcTests(unittest.TestCase):
    def test_flattened_arc_chords_chain_into_one_curve(self):
        r = chain_fragments(chords(0, 0, 100, 0, 90, 24))
        self.assertEqual(len(r["chains"]), 1)
        c = r["chains"][0]
        self.assertEqual(len(c["points"]), 25)
        # chord sum is just under the arc length pi*50
        self.assertLess(c["length"], math.pi * 50)
        self.assertGreater(c["length"], math.pi * 50 * 0.995)

    def test_a_tangent_run_into_an_arc_chains_through(self):
        # straight dashes heading +x, then an arc turning up, with tiny gaps
        straight = dashes(-150, -100, dash=10, gap=2, n=10)  # ends at x=-32
        arc = chords(0, 0, 100, -90, 0, 30)  # starts at (0,-100)
        # bridge the 32 pt gap with two more dashes
        bridge = [[(-32 + 2, -100), (-32 + 12, -100)], [(-32 + 14, -100), (-32 + 24, -100)]]
        r = chain_fragments(straight + bridge + arc, gap_tol=9.0)
        self.assertEqual(len(r["chains"]), 1)

    def test_a_closed_loop_is_reported_closed(self):
        sq = (dashes(0, 0, dash=20, gap=5, n=4)  # bottom, ends x=95
              + [[(100, 0 + k * 25), (100, 20 + k * 25)] for k in range(4)]  # right
              + [[(100 - k * 25, 100), (80 - k * 25, 100)] for k in range(4)]  # top, leftward
              + [[(0, 100 - k * 25), (0, 80 - k * 25)] for k in range(4)])  # left, downward
        r = chain_fragments(sq, angle_tol_deg=95)
        self.assertEqual(len(r["chains"]), 1)
        self.assertTrue(r["chains"][0]["closed"])


class BranchTests(unittest.TestCase):
    def test_a_side_line_meeting_the_run_is_rejected_by_direction_not_by_distance(self):
        vertical = [[(72.5, 0), (72.5, 30)]]  # touches the gap after dash 4 at x=70..75
        r = chain_fragments(dashes(0, 0) + vertical)
        self.assertEqual(len(r["chains"]), 2)
        main = r["chains"][0]
        self.assertEqual(len(main["members"]), 10)

    def test_two_qualifying_continuations_are_reported_as_a_branch(self):
        # after the dashes end at x=145, two candidates within the gap and
        # angle: one straight on, one at 15 degrees
        straight_on = [[(150, 0), (160, 0)]]
        slanted = [[(150, 1.0), (160, 1.0 + 10 * math.tan(math.radians(15)))]]
        r = chain_fragments(dashes(0, 0) + straight_on + slanted)
        self.assertTrue(any(b["code"] == "CHAIN_BRANCH" for b in r["branches"]))
        b = r["branches"][0]
        self.assertAlmostEqual(b["at"][0], 145.0, places=6)
        self.assertFalse(b["blocking"])


class DuplicateTests(unittest.TestCase):
    def test_a_line_plotted_twice_chains_once(self):
        # the pavement edge on DEMO-001 sheet 04 arrives as two or three
        # coincident copies of every dash; each copy is the other's closest
        # partner, which defeats mutual-best linking unless they are dropped
        once = dashes(0, 0)
        twice = once + [list(reversed(d)) for d in once] + [[(x + 0.2, y) for x, y in d] for d in once]
        r = chain_fragments(twice)
        self.assertEqual(r["duplicates_removed"], 20)
        self.assertEqual(r["fragments_used"], 10)
        self.assertEqual(len(r["chains"]), 1)
        self.assertAlmostEqual(r["chains"][0]["length"], 145.0, places=6)
        self.assertEqual(r["branches"], [])

    def test_members_still_index_the_original_input_after_dedupe(self):
        once = dashes(0, 0)
        r = chain_fragments(once[:1] + once[:1] + once[1:])
        self.assertEqual(r["duplicates_removed"], 1)
        self.assertNotIn(1, r["chains"][0]["members"])
        self.assertIn(0, r["chains"][0]["members"])


class InputTests(unittest.TestCase):
    def test_objects_on_layer_dicts_are_accepted(self):
        objs = [{"points_raw": pts} for pts in dashes(0, 0)]
        r = chain_fragments(objs)
        self.assertEqual(len(r["chains"]), 1)

    def test_single_point_fragments_are_ignored_not_fatal(self):
        r = chain_fragments(dashes(0, 0) + [[(500, 500)], [(600, 600), (600, 600)]])
        self.assertEqual(r["fragments_in"], 12)
        self.assertEqual(r["fragments_used"], 10)
        self.assertEqual(len(r["chains"]), 1)

    def test_metres_are_reported_when_a_scale_is_given(self):
        r = chain_fragments(dashes(0, 0), metres_per_unit=0.5)
        self.assertAlmostEqual(r["chains"][0]["length_m"], 72.5, places=6)

    def test_empty_input(self):
        r = chain_fragments([])
        self.assertEqual(r["chains"], [])
        self.assertEqual(nearest_gap_stats([])["count"], 0)

    def test_chains_come_longest_first_and_members_index_the_input(self):
        short = [[(0, 300), (5, 300)]]
        r = chain_fragments(short + dashes(0, 0))
        self.assertEqual(sorted(r["chains"][0]["members"]), list(range(1, 11)))
        self.assertEqual(r["chains"][1]["members"], [0])


if __name__ == "__main__":
    unittest.main()
