"""Capa de servicio — orquestación entre dominio y datos.

Separa la lógica de negocio de los handlers HTTP.
Testeable sin dependencias de FastAPI.
"""

import logging

from clima import clima_client
from config import config
from reglas import Cultivo, evaluar_reglas

logger = logging.getLogger("wenuke.servicios")


async def obtener_contexto_clima(lat: float, lon: float, cultivo: Cultivo) -> dict:
    """Obtiene y procesa datos climáticos: forecast + reglas + resumen.

    Encapsula el pipeline completo: fetch → parse → eval → resumen.
    Usado por los handlers de /clima, /preguntar y /recomendaciones.

    Raises:
        Exception: Si OpenMeteo no responde (el handler decide si 502 o fallback).

    Returns:
        dict con raw, hourly, daily, resultado (alertas + cultivo), resumen.
    """
    raw = await clima_client.fetch_forecast(lat, lon)

    hourly = clima_client.parse_hourly(raw)
    daily = clima_client.extract_daily(raw)
    resultado = evaluar_reglas(hourly, cultivo)

    hoy = daily[0] if daily else {}
    resumen = {
        "temp_min": hoy.get("temp_min", "N/D"),
        "temp_max": hoy.get("temp_max", "N/D"),
        "lluvia_total_24h": hoy.get("precipitacion_total", 0.0),
        "viento_max": hoy.get("viento_max", "N/D"),
        "dias_forecast": config.forecast_days,
    }

    return {
        "raw": raw,
        "hourly": hourly,
        "daily": daily,
        "resultado": resultado,
        "resumen": resumen,
    }
