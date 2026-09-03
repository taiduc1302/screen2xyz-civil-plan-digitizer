from __future__ import annotations

import unittest

from screen2xyz_civil.takeoff import (
    COUNT,
    LINE,
    POLYGON,
    RULES,
    TakeoffError,
    UNIT_EA,
    UNIT_M,
    UNIT_M2,
    takeoff_rule,
)


class RuleCatalogueTests(unittest.TestCase):
    def test_every_rule_id_matches_its_key(self):
        for key, rule in RULES.items():
            self.assertEqual(key, rule.rule_id)

    def test_every_rule_unit_matches_its_geometry_kind(self):
        expected = {LINE: UNIT_M, POLYGON: UNIT_M2, COUNT: UNIT_EA}
        for rule in RULES.values():
            self.assertEqual(rule.default_unit, expected[rule.geometry_kind], rule.rule_id)

    def test_every_rule_carries_guidance(self):
        # Guidance is what a fresh operator reads instead of guessing what a
        # rule covers; an empty one silently invites the wrong geometry.
        for rule in RULES.values():
            self.assertTrue(rule.guidance.strip(), f"{rule.rule_id} has no guidance")

    def test_unknown_rule_is_rejected(self):
        with self.assertRaises(TakeoffError):
            takeoff_rule("NO_SUCH_RULE")


class CountRulesExistTests(unittest.TestCase):
    def test_the_catalogue_can_express_a_counted_item(self):
        # Until 2026-09-03 the COUNT geometry kind existed with no rule using
        # it, so every "Each" pay item on the schedule - manholes, headwalls -
        # had nowhere to be recorded.
        count_rules = [r for r in RULES.values() if r.geometry_kind == COUNT]
        self.assertTrue(count_rules, "no COUNT rule exists; Each items cannot be recorded")

    def test_storm_structures_are_countable(self):
        rule = takeoff_rule("STORM_STRUCTURE_COUNT")
        self.assertEqual(rule.geometry_kind, COUNT)
        self.assertEqual(rule.default_unit, UNIT_EA)


class ScopeCoverageRulesTests(unittest.TestCase):
    # Each of these was drawn on Example Road Sheet 03, was paid for or bounded
    # paid work, and had no rule to be recorded under before 2026-09-03.
    REQUIRED = [
        "CONCRETE_CURB",
        "HANDRAIL",
        "SAWCUT",
        "WIRE_FENCE_RELOCATION",
        "CLEARING_LIMIT",
        "EARTHWORK_SLOPE_LIMIT",
        "HYDROSEEDING",
        "IMPORTED_TOPSOIL",
        "STORM_CULVERT",
        "STORM_MANHOLE_RISER",
        "STORM_STRUCTURE_COUNT",
        "UTILITY_PROTECTION_COUNT",
    ]

    def test_all_previously_unrecordable_scope_now_has_a_rule(self):
        for rule_id in self.REQUIRED:
            self.assertIn(rule_id, RULES, f"{rule_id} cannot be recorded")

    def test_reference_only_rules_are_not_summable(self):
        # An extent line and a protection count bound or explain paid work but
        # are not themselves quantities to add to a bid.
        for rule_id in ("CLEARING_LIMIT", "EARTHWORK_SLOPE_LIMIT", "UTILITY_PROTECTION_COUNT"):
            self.assertFalse(takeoff_rule(rule_id).summable, rule_id)

    def test_driveway_culvert_stays_separate_from_the_general_storm_culvert(self):
        # They are different pay items; merging them loses the distinction.
        self.assertIn("DRIVEWAY_CULVERT_300", RULES)
        self.assertIn("STORM_CULVERT", RULES)
        self.assertNotEqual(
            takeoff_rule("DRIVEWAY_CULVERT_300").display_name,
            takeoff_rule("STORM_CULVERT").display_name,
        )


if __name__ == "__main__":
    unittest.main()
