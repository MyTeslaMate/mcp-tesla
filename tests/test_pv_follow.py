"""Unit tests for PV-follow pure helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tesla_mcp.modules.pv_follow import (  # noqa: E402
    compute_surplus_w,
    compute_target_amps,
    decide_action,
)


class ComputeSurplusTests(unittest.TestCase):
    def test_export_yields_positive_surplus(self):
        self.assertEqual(compute_surplus_w(-3000), 3000)

    def test_zero_grid_yields_zero(self):
        self.assertEqual(compute_surplus_w(0), 0)

    def test_import_yields_zero(self):
        self.assertEqual(compute_surplus_w(500), 0)

    def test_float_input(self):
        self.assertEqual(compute_surplus_w(-2500.7), 2500)


class ComputeTargetAmpsTests(unittest.TestCase):
    def test_single_phase_230v(self):
        self.assertEqual(
            compute_target_amps(3000, 230, 1, min_amps=5, max_amps=16), 13
        )

    def test_three_phase_400v(self):
        # 3 * 230V * 5A = 3450W minimum to reach min_amps
        self.assertEqual(
            compute_target_amps(4500, 230, 3, min_amps=5, max_amps=16), 6
        )

    def test_under_min_returns_zero(self):
        # 800W / 230V = 3A < 5A min
        self.assertEqual(
            compute_target_amps(800, 230, 1, min_amps=5, max_amps=16), 0
        )

    def test_over_max_clamps(self):
        # 10kW / 230V = 43A, clamped to 16
        self.assertEqual(
            compute_target_amps(10000, 230, 1, min_amps=5, max_amps=16), 16
        )

    def test_zero_voltage_safe(self):
        self.assertEqual(
            compute_target_amps(3000, 0, 1, min_amps=5, max_amps=16), 0
        )

    def test_zero_phases_safe(self):
        self.assertEqual(
            compute_target_amps(3000, 230, 0, min_amps=5, max_amps=16), 0
        )

    def test_negative_surplus_safe(self):
        self.assertEqual(
            compute_target_amps(-100, 230, 1, min_amps=5, max_amps=16), 0
        )


class DecideActionTests(unittest.TestCase):
    BASE = dict(
        current_amps=0,
        vehicle_soc=50.0,
        target_soc=80.0,
        above_since=None,
        below_since=None,
        now=1000.0,
        start_hysteresis_s=120,
        stop_hysteresis_s=180,
        min_amps=5,
    )

    def test_disconnected_terminates(self):
        action, reason = decide_action(
            target_amps=10, charging_state="Disconnected", **self.BASE
        )
        self.assertEqual(action, "terminate")
        self.assertIn("Disconnected", reason)

    def test_complete_terminates(self):
        action, reason = decide_action(
            target_amps=10, charging_state="Complete", **self.BASE
        )
        self.assertEqual(action, "terminate")

    def test_target_soc_reached_terminates(self):
        kwargs = {**self.BASE, "vehicle_soc": 80.0, "target_soc": 80.0}
        action, reason = decide_action(
            target_amps=10, charging_state="Charging", **kwargs
        )
        self.assertEqual(action, "terminate")
        self.assertIn("target_soc_reached", reason)

    def test_starts_after_hysteresis(self):
        kwargs = {**self.BASE, "above_since": 800.0}  # 200s above, > 120s threshold
        action, _ = decide_action(
            target_amps=10, charging_state="Stopped", **kwargs
        )
        self.assertEqual(action, "start")

    def test_holds_during_start_hysteresis(self):
        kwargs = {**self.BASE, "above_since": 950.0}  # 50s above, < 120s threshold
        action, _ = decide_action(
            target_amps=10, charging_state="Stopped", **kwargs
        )
        self.assertEqual(action, "hold")

    def test_holds_when_no_surplus_and_not_charging(self):
        action, _ = decide_action(
            target_amps=0, charging_state="Stopped", **self.BASE
        )
        self.assertEqual(action, "hold")

    def test_stops_after_hysteresis(self):
        kwargs = {**self.BASE, "current_amps": 10, "below_since": 700.0}  # 300s
        action, _ = decide_action(
            target_amps=0, charging_state="Charging", **kwargs
        )
        self.assertEqual(action, "stop")

    def test_holds_during_stop_hysteresis(self):
        kwargs = {**self.BASE, "current_amps": 10, "below_since": 900.0}  # 100s
        action, _ = decide_action(
            target_amps=0, charging_state="Charging", **kwargs
        )
        self.assertEqual(action, "hold")

    def test_adjusts_when_amps_change(self):
        kwargs = {**self.BASE, "current_amps": 8, "above_since": 800.0}
        action, _ = decide_action(
            target_amps=12, charging_state="Charging", **kwargs
        )
        self.assertEqual(action, "adjust")

    def test_holds_when_amps_match(self):
        kwargs = {**self.BASE, "current_amps": 10, "above_since": 800.0}
        action, _ = decide_action(
            target_amps=10, charging_state="Charging", **kwargs
        )
        self.assertEqual(action, "hold")


if __name__ == "__main__":
    unittest.main()
