import unittest
from pathlib import Path

from api_helpers import request

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from rainscape.api import create_app


class TestForecastAPIValidation(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Path("E:/RAINSCAPE/data/not-present"))

    def test_health_is_available_without_loading_forecast(self):
        response = request(self.app, "GET", "/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_missing_forecast_is_unavailable_not_fabricated(self):
        response = request(self.app, "GET", "/v1/forecast/metadata")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "forecast_unavailable")

    def test_invalid_coordinates_are_rejected_before_source_access(self):
        response = request(self.app, "GET", "/v1/forecast/point", params={"latitude": 90.1, "longitude": 0})
        self.assertEqual(response.status_code, 422)

    def test_unsupported_model_is_rejected(self):
        response = request(self.app, "GET", "/v1/forecast/metadata", params={"model": "aifs"})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()

