from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import eccodes
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from rainscape.precipitation import (  # noqa: E402
    derive_precipitation_intervals, load_grib_field,
)

RAW = ROOT / "data" / "raw"
STEPS = (3, 6, 9, 12)
COORDINATES = (
    (12.9716, 77.5946),   # Bengaluru
    (0.0, -180.0),       # antimeridian
    (0.0, 180.0),        # same longitude through alternate notation
    (90.0, 0.0),         # north boundary
    (-90.0, 359.75),     # south boundary and wrap
    (-33.8688, 151.2093),
)


def direct_element(path: Path, key: str, index: int):
    with path.open("rb") as stream:
        gid = eccodes.codes_grib_new_from_file(stream)
        try:
            return float(eccodes.codes_get_elements(gid, key, [index])[0])
        finally:
            eccodes.codes_release(gid)


@unittest.skipUnless(all((RAW / f"ifs-20261103T00-step{s:03d}-tp.grib2").exists() for s in STEPS),
                     "genuine ECMWF IFS integration files not present")
class TestGenuineIFSGrib(unittest.TestCase):
    """Live-source checks; unlike deterministic fixtures, these need downloaded GRIBs."""

    @classmethod
    def setUpClass(cls):
        cls.paths = {
            step: RAW / f"ifs-20261103T00-step{step:03d}-tp.grib2" for step in STEPS
        }
        cls.fields = {step: load_grib_field(path) for step, path in cls.paths.items()}

    def test_each_message_has_expected_verified_metadata(self):
        expected_ranges = {3: (0, 3), 6: (0, 6), 9: (0, 9), 12: (0, 12)}
        for step, field in self.fields.items():
            with self.subTest(step=step):
                self.assertEqual(field.parameter_short_name, "tp")
                self.assertEqual(field.parameter_id, 228)
                self.assertEqual(field.parameter_name, "Total precipitation")
                self.assertEqual(field.units, "m")
                self.assertEqual(field.step_type, "accum")
                self.assertEqual(field.statistical_processing, 1)
                self.assertEqual((field.start_step_hours, field.end_step_hours), expected_ranges[step])
                self.assertEqual(field.valid_time.hour, step)
                self.assertEqual(field.grid.grid_type, "regular_ll")
                self.assertEqual((field.grid.ni, field.grid.nj), (1440, 721))
                self.assertEqual(field.grid.scanning_mode, 0)
                self.assertEqual(field.missing_count, 0)
                self.assertGreater(field.packing_error, 0.0)
                self.assertEqual(len(field.values), field.grid.size)

    def test_cumulative_values_and_direct_ecCodes_samples_agree(self):
        intervals = derive_precipitation_intervals([self.fields[s] for s in STEPS])
        self.assertEqual(
            [(x.interval_start_hours, x.interval_end_hours) for x in intervals],
            [(0, 3), (3, 6), (6, 9), (9, 12)],
        )
        self.assertTrue(all(np.nanmin(x.values) >= 0.0 for x in intervals))
        self.assertGreater(intervals[1].values_zeroed_as_indeterminate, 0)
        self.assertGreater(intervals[2].values_zeroed_as_indeterminate, 0)
        for lat, lon in COORDINATES:
            field = self.fields[3]
            idx = field.grid.index(lat, lon)
            actual_lat = direct_element(self.paths[3], "latitudes", idx)
            actual_lon = direct_element(self.paths[3], "longitudes", idx)
            requested_lat, requested_lon = field.grid.coordinate_at(idx)
            self.assertAlmostEqual(actual_lat, requested_lat, places=6)
            # Longitude equality is circular because ecCodes normalizes to [-180, 180).
            self.assertLessEqual(abs((actual_lon - requested_lon + 180) % 360 - 180), 1e-6)
            self.assertLessEqual(abs(actual_lat - lat), field.grid.j_increment / 2 + 1e-6)
            self.assertLessEqual(abs((actual_lon - lon + 180) % 360 - 180), field.grid.i_increment / 2 + 1e-6)
            source_value = direct_element(self.paths[3], "values", idx)
            self.assertAlmostEqual(float(field.values[idx]), source_value, places=12)
            self.assertAlmostEqual(float(intervals[0].values[idx]), source_value, places=12)
            # Independent indexed ecCodes reads verify the differenced amount.
            previous = direct_element(self.paths[3], "values", idx)
            current = direct_element(self.paths[6], "values", idx)
            self.assertAlmostEqual(float(intervals[1].values[idx]), current - previous, places=12)


if __name__ == "__main__":
    unittest.main()

