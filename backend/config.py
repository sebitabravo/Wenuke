"""Configuración desde variables de entorno."""

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = "llama-3.1-70b-versatile"
    database_path: str = field(default_factory=lambda: os.getenv(
        "DB_PATH",
        "/tmp/wenuke.db" if os.getenv("VERCEL") else "wenuke.db"
    ))
    openmeteo_base_url: str = "https://api.open-meteo.com/v1"
    forecast_days: int = 7
    cache_ttl_segundos: int = 3600
    # WhatsApp Business Cloud API
    whatsapp_token: str = field(default_factory=lambda: os.getenv("WHATSAPP_TOKEN", ""))
    whatsapp_phone_number_id: str = field(default_factory=lambda: os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""))
    # Coordenadas default: Temuco, La Araucanía
    lat_default: float = -38.7359
    lon_default: float = -72.5904


config = Config()
