from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from rainscape.precipitation import (  # noqa: E402
    GridError, PrecipitationField, RegularLLGrid, SequenceError,
    derive_precipitation_intervals, is_below_encoding_resolution, to_millimetres, value_at,
)

UTC = timezone.utc
GRID = RegularLLGrid(
    ni=4, nj=3, first_latitude=90, first_longitude=0,
    last_latitude=-90, last_longitude=270, i_increment=90,
    j_increment=90, scanning_mode=0,
)


def fixture_field(step: int, values, *, start: int = 0, units: str = "m",
                  cycle=datetime(2026, 11, 3, tzinfo=UTC),
                  bitmap: bool = False, missing: float = 9999.0, packing_error: float = 0.0):
    return PrecipitationField(
        source_path=f"fixture-step-{step}", source_sha256=f"fixture-{step}",
        model="ifs", product="fixture", cycle=cycle, retrieved_at=None, step_units_code=1, parameter_short_name="tp",
        parameter_name="Total precipitation", parameter_id=228, units=units,
        step_type="accum", statistical_processing=1, start_step_hours=start,
        end_step_hours=step, valid_time=cycle + timedelta(hours=step), grid=GRID,
        values=np.asarray(values, dtype=np.float64), bitmap_present=bitmap,
        missing_value=missing, missing_count=None, packing_error=packing_error,
    )


class TestRegularLLSampling(unittest.TestCase):
    def test_north_to_south_rows_and_cyclic_longitudes(self):
        self.assertEqual(GRID.index(90, 0), 0)
        self.assertEqual(GRID.index(0, 0), 4)
        self.assertEqual(GRID.index(-90, 0), 8)
        self.assertEqual(GRID.index(90, 360), GRID.index(90, 0))
        self.assertEqual(GRID.index(0, -90), 7)
        self.assertEqual(GRID.index(0, 450), GRID.index(0, 90))

    def test_grid_bounds_and_nonfinite_coordinates(self):
        with self.assertRaises(GridError):
            GRID.index(90.001, 0)
        with self.assertRaises(GridError):
            GRID.index(float("nan"), 0)
        with self.assertRaises(GridError):
            GRID.coordinate_at(GRID.size)

    def test_nearest_cell_half_step_tie_goes_in_scan_direction(self):
        # At the equator, 45 degrees is equally close to columns 0 and 1.
        self.assertEqual(GRID.index(0, 45), 5)


class TestAccumulationFixtures(unittest.TestCase):
    def test_cumulative_steps_become_explicit_adjacent_intervals(self):
        a = fixture_field(3, np.full(GRID.size, 0.003))
        b = fixture_field(6, np.full(GRID.size, 0.008))
        c = fixture_field(9, np.full(GRID.size, 0.012))
        result = derive_precipitation_intervals([c, a, b])
        self.assertEqual([(x.interval_start_hours, x.interval_end_hours) for x in result],
                         [(0, 3), (3, 6), (6, 9)])
        self.assertTrue(np.allclose(result[1].values, 0.005))
        self.assertTrue(np.allclose(result[2].values, 0.004))
        self.assertEqual(result[1].baseline_source_path, a.source_path)
        self.assertEqual(result[1].units, "m")
        self.assertEqual(result[1].encoding_uncertainty, 0.0)

    def test_missing_cells_propagate_and_are_not_zero(self):
        a = np.full(GRID.size, 0.003)
        b = np.full(GRID.size, 0.007)
        a[2] = 9999
        b[3] = 9999
        result = derive_precipitation_intervals([
            fixture_field(3, a, bitmap=True), fixture_field(6, b, bitmap=True)
        ])
        self.assertTrue(np.isnan(result[1].values[2]))
        self.assertTrue(np.isnan(result[1].values[3]))
        self.assertIsNone(value_at(result[1], 2))
        self.assertAlmostEqual(value_at(result[1], 1), 0.004)

    def test_irregular_cumulative_gap_is_reported_as_a_wider_interval(self):
        result = derive_precipitation_intervals([
            fixture_field(3, np.full(GRID.size, 0.003)),
            fixture_field(9, np.full(GRID.size, 0.010)),
        ])
        self.assertEqual((result[1].interval_start_hours, result[1].interval_end_hours), (3, 9))
        self.assertAlmostEqual(value_at(result[1], 0), 0.007)

    def test_sub_resolution_differences_are_zeroed_and_counted(self):
        previous = fixture_field(3, np.full(GRID.size, 0.010), packing_error=0.001)
        current = fixture_field(6, np.full(GRID.size, 0.0105), packing_error=0.001)
        result = derive_precipitation_intervals([previous, current])[1]
        self.assertTrue(np.all(result.values == 0.0))
        self.assertEqual(result.values_zeroed_as_indeterminate, GRID.size)
        self.assertTrue(is_below_encoding_resolution(result, 0))
        self.assertAlmostEqual(result.encoding_uncertainty, 0.002)

    def test_duplicate_endpoint_and_decrease_are_rejected(self):
        a = fixture_field(3, np.full(GRID.size, 0.003))
        with self.assertRaises(SequenceError):
            derive_precipitation_intervals([a, fixture_field(3, np.full(GRID.size, 0.004))])
        with self.assertRaises(SequenceError):
            derive_precipitation_intervals([
                a, fixture_field(6, np.full(GRID.size, 0.002))
            ])

    def test_cycle_grid_parameter_and_valid_time_mismatches_are_rejected(self):
        a = fixture_field(3, np.full(GRID.size, 0.003))
        next_cycle = datetime(2026, 11, 3, 6, tzinfo=UTC)
        with self.assertRaises(SequenceError):
            derive_precipitation_intervals([
                a, fixture_field(6, np.full(GRID.size, 0.006), cycle=next_cycle)
            ])
        wrong_time = fixture_field(6, np.full(GRID.size, 0.006))
        object.__setattr__(wrong_time, "valid_time", wrong_time.valid_time + timedelta(minutes=1))
        with self.assertRaises(SequenceError):
            derive_precipitation_intervals([a, wrong_time])

    def test_interval_accumulations_are_used_directly_and_overlap_rejected(self):
        a = fixture_field(6, np.full(GRID.size, 0.003), start=3)
        b = fixture_field(9, np.full(GRID.size, 0.002), start=6)
        direct = derive_precipitation_intervals([a, b])
        self.assertAlmostEqual(value_at(direct[1], 0), 0.002)
        self.assertEqual((direct[1].interval_start_hours, direct[1].interval_end_hours), (6, 9))
        overlapping = fixture_field(10, np.full(GRID.size, 0.004), start=8)
        with self.assertRaises(SequenceError):
            derive_precipitation_intervals([a, b, overlapping])

    def test_only_supported_accumulation_and_units_convert_at_display_boundary(self):
        self.assertEqual(to_millimetres(0.001, "m"), 1.0)
        self.assertEqual(to_millimetres(1.0, "kg m**-2"), 1.0)
        with self.assertRaises(ValueError):
            to_millimetres(1.0, "m s-1")


if __name__ == "__main__":
    unittest.main()





