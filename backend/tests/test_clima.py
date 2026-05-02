"""Tests para el cliente de clima."""
from clima import OpenMeteoClient


class TestOpenMeteoClient:
    def setup_method(self):
        self.client = OpenMeteoClient()

    def test_parse_hourly_estructura(self):
        raw = {
            "hourly": {
                "time": ["2026-05-02T00:00", "2026-05-02T01:00"],
                "temperature_2m": [15.0, 16.0],
                "precipitation": [0.0, 1.5],
                "wind_speed_10m": [10.0, 12.0],
            }
        }
        result = self.client.parse_hourly(raw)
        assert len(result) == 2
        assert result[0]["hora"] == "2026-05-02T00:00"
        assert result[0]["temperatura"] == 15.0
        assert result[0]["precipitacion"] == 0.0
        assert result[0]["viento"] == 10.0

    def test_parse_hourly_vacio(self):
        result = self.client.parse_hourly({})
        assert result == []

    def test_extract_daily_estructura(self):
        raw = {
            "daily": {
                "time": ["2026-05-02", "2026-05-03"],
                "temperature_2m_min": [10.0, 11.0],
                "temperature_2m_max": [20.0, 21.0],
                "precipitation_sum": [0.0, 5.0],
                "wind_speed_10m_max": [15.0, 20.0],
            }
        }
        result = self.client.extract_daily(raw)
        assert len(result) == 2
        assert result[0]["dia"] == "2026-05-02"
        assert result[0]["temp_min"] == 10.0
        assert result[0]["temp_max"] == 20.0

    def test_extract_daily_vacio(self):
        result = self.client.extract_daily({})
        assert result == []

    def test_cache_key_formato(self):
        key = self.client._cache_key(-38.7359, -72.5904)
        assert key == "-38.74,-72.59"
