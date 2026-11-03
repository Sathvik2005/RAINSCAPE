from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api_helpers import request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from rainscape.api import create_app  # noqa: E402

RAW = ROOT / "data" / "raw"


@unittest.skipUnless(list(RAW.glob("ifs-20261103T00-step*-tp.grib2")),
                     "genuine ECMWF IFS integration files not present")
class TestLiveForecastAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(RAW)

    def test_metadata_and_point_forecast_expose_provenance(self):
        metadata = request(self.app, "GET", "/v1/forecast/metadata")
        self.assertEqual(metadata.status_code, 200)
        body = metadata.json()
        self.assertEqual(body["model"], "ifs")
        self.assertEqual(body["source_units"], "m")
        self.assertEqual(body["display_units"], "mm")
        self.assertEqual(
            [(s["interval_start_hour"], s["interval_end_hour"]) for s in body["steps"]],
            [(0, 3), (3, 6), (6, 9), (9, 12)],
        )
        point = request(self.app, "GET", "/v1/forecast/point", params={"latitude": 12.9716, "longitude": 77.5946})
        self.assertEqual(point.status_code, 200)
        payload = point.json()
        self.assertEqual(payload["sampling"], "nearest_grid_cell")
        self.assertEqual(payload["grid_cell"], {"latitude": 13.0, "longitude": 77.5})
        self.assertEqual(len(payload["steps"]), 4)
        self.assertTrue(all(step["source"]["source_sha256"] for step in payload["steps"]))
        self.assertIsNone(payload["steps"][0]["source"]["baseline_source_sha256"])
        self.assertTrue(payload["steps"][1]["source"]["baseline_source_sha256"])
        self.assertTrue(any(step["below_encoding_resolution"] for step in payload["steps"]))
        self.assertTrue(all(step["unit"] == "mm" for step in payload["steps"]))
        self.assertGreater(payload["steps"][1]["encoding_uncertainty_mm"], 0.0)

    def test_bounded_region_and_dateline_region(self):
        small = request(self.app, "GET", "/v1/forecast/region", params={
            "west": 77.4, "south": 12.9, "east": 77.6, "north": 13.1, "end_step": 6
        })
        self.assertEqual(small.status_code, 200)
        self.assertEqual(len(small.json()["cells"]), 1)
        self.assertEqual(small.json()["cells"][0]["latitude"], 13.0)
        self.assertEqual(small.json()["cells"][0]["longitude"], 77.5)
        wrapped = request(self.app, "GET", "/v1/forecast/region", params={
            "west": 179.5, "south": -0.1, "east": -179.5, "north": 0.1,
            "end_step": 6, "stride": 1,
        })
        self.assertEqual(wrapped.status_code, 200)
        self.assertGreaterEqual(len(wrapped.json()["cells"]), 1)

    def test_region_payload_is_bounded(self):
        response = request(self.app, "GET", "/v1/forecast/region", params={
            "west": -180, "south": -90, "east": 180, "north": 90,
            "end_step": 6, "stride": 1,
        })
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"]["code"], "region_too_large")


if __name__ == "__main__":
    unittest.main()



