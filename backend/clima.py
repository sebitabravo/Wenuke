"""Cliente de OpenMeteo — forecast gratuito sin API key."""

import logging
import time

import httpx
from config import config

logger = logging.getLogger("wenuke.clima")


class OpenMeteoClient:
    def __init__(self):
        self.base_url = config.openmeteo_base_url
        self.cache: dict[str, tuple[float, dict]] = {}  # key -> (timestamp, data)

    def _cache_key(self, lat: float, lon: float) -> str:
        # Redondear a 2 decimales para cache (~1.1km de precisión)
        return f"{round(lat, 2)},{round(lon, 2)}"

    async def fetch_forecast(self, lat: float, lon: float) -> dict:
        """Obtiene pronóstico horario de OpenMeteo. Usa cache en memoria."""
        key = self._cache_key(lat, lon)

        # Verificar cache
        if key in self.cache:
            ts, data = self.cache[key]
            if time.time() - ts < config.cache_ttl_segundos:
                return data

        # Fetch de OpenMeteo
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(
                    f"{self.base_url}/forecast",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "hourly": "temperature_2m,precipitation,wind_speed_10m",
                        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
                        "forecast_days": config.forecast_days,
                        "timezone": "America/Santiago",
                    },
                )
                r.raise_for_status()
                data = r.json()
                self.cache[key] = (time.time(), data)
                return data
            except httpx.HTTPError as e:
                logger.error(f"OpenMeteo forecast falló para {key}: {e}")
                # Si hay cache vencido, devolverlo como fallback
                if key in self.cache:
                    return self.cache[key][1]
                raise Exception(f"No se pudo obtener el pronóstico: {e}")

    @staticmethod
    def parse_hourly(raw: dict) -> list[dict]:
        """Convierte datos horarios de OpenMeteo a lista de dicts."""
        hourly = raw.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        precip = hourly.get("precipitation", [])
        vientos = hourly.get("wind_speed_10m", [])

        if not times:
            return []

        resultado = []
        for i, t in enumerate(times):
            resultado.append({
                "hora": t,
                "temperatura": temps[i] if i < len(temps) else None,
                "precipitacion": precip[i] if i < len(precip) else 0.0,
                "viento": vientos[i] if i < len(vientos) else None,
            })
        return resultado

    @staticmethod
    def extract_daily(raw: dict) -> list[dict]:
        """Extrae resumen diario del forecast."""
        daily = raw.get("daily", {})
        times = daily.get("time", [])
        temps_max = daily.get("temperature_2m_max", [])
        temps_min = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_sum", [])
        vientos = daily.get("wind_speed_10m_max", [])

        resultado = []
        for i, t in enumerate(times):
            resultado.append({
                "dia": t,
                "temp_max": temps_max[i] if i < len(temps_max) else None,
                "temp_min": temps_min[i] if i < len(temps_min) else None,
                "precipitacion_total": precip[i] if i < len(precip) else 0.0,
                "viento_max": vientos[i] if i < len(vientos) else None,
            })
        return resultado


    async def fetch_historico(self, lat: float, lon: float, inicio: str, fin: str) -> dict:
        """Obtiene datos históricos de OpenMeteo Archive API (gratis, sin key)."""
        key = f"hist:{round(lat, 2)},{round(lon, 2)},{inicio},{fin}"

        if key in self.cache:
            ts, data = self.cache[key]
            if time.time() - ts < config.cache_ttl_segundos * 24:  # histórico cachea 24x más
                return data

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                r = await client.get(
                    "https://archive-api.open-meteo.com/v1/archive",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "start_date": inicio,
                        "end_date": fin,
                        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
                        "timezone": "America/Santiago",
                    },
                )
                r.raise_for_status()
                data = r.json()
                self.cache[key] = (time.time(), data)
                return data
            except httpx.HTTPError as e:
                logger.error(f"OpenMeteo histórico falló para {key}: {e}")
                if key in self.cache:
                    return self.cache[key][1]
                raise Exception(f"No se pudo obtener datos históricos: {e}")

    @staticmethod
    def parse_historico(raw: dict) -> list[dict]:
        """Convierte datos diarios históricos a lista de dicts con promedios anuales."""
        daily = raw.get("daily", {})
        times = daily.get("time", [])
        temps_max = daily.get("temperature_2m_max", [])
        temps_min = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_sum", [])
        vientos = daily.get("wind_speed_10m_max", [])

        resultado = []
        for i, t in enumerate(times):
            resultado.append({
                "fecha": t,
                "temp_max": temps_max[i] if i < len(temps_max) else None,
                "temp_min": temps_min[i] if i < len(temps_min) else None,
                "precipitacion": precip[i] if i < len(precip) else 0.0,
                "viento_max": vientos[i] if i < len(vientos) else None,
            })
        return resultado


# Singleton
clima_client = OpenMeteoClient()
