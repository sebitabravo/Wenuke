"""Modelos Pydantic v2 para validación de datos — Wenuke API."""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Alerta climática
# ---------------------------------------------------------------------------

class Alerta(BaseModel):
    """Una alerta climática para un día específico del pronóstico."""
    tipo: Literal["helada", "lluvia_intensa", "viento_fuerte", "granizo"] = Field(
        ...,
        description="Tipo de evento climático adverso",
    )
    mensaje: str = Field(
        ...,
        min_length=5,
        description="Descripción legible de la alerta",
    )
    severidad: Literal["alta", "media", "baja"] = Field(
        ...,
        description="Nivel de riesgo para el cultivo",
    )
    dia: str = Field(
        ...,
        description="Fecha en formato ISO 8601 (YYYY-MM-DD)",
    )
    hora: str | None = Field(
        default=None,
        description="Hora puntual si aplica (HH:MM, 24h). Null si la alerta cubre todo el día",
    )

    model_config = {"json_schema_extra": {"examples": [
        {
            "tipo": "helada",
            "mensaje": "Temperatura bajo 0°C entre las 03:00 y 07:00. Riesgo de daño en brotes.",
            "severidad": "alta",
            "dia": "2026-05-03",
            "hora": "04:00",
        },
        {
            "tipo": "lluvia_intensa",
            "mensaje": "Precipitación acumulada de 45mm en 6h. Riesgo de anegamiento.",
            "severidad": "media",
            "dia": "2026-05-02",
            "hora": None,
        },
    ]}}


# ---------------------------------------------------------------------------
# Respuesta de clima
# ---------------------------------------------------------------------------

class ClimaResponse(BaseModel):
    """Respuesta completa del pronóstico climático para un cultivo y ubicación."""
    cultivo: str = Field(..., description="Cultivo para el cual se generó el análisis")
    ubicacion: dict = Field(
        ...,
        description="Coordenadas geográficas de la consulta",
    )
    alertas: list[Alerta] = Field(
        default_factory=list,
        description="Lista de alertas activas para los próximos días",
    )
    resumen: dict = Field(
        ...,
        description="Resumen numérico del pronóstico",
    )
    raw_forecast: dict | None = Field(
        default=None,
        description="Datos crudos de Open-Meteo. Solo presente si se solicita explícitamente",
    )

    @field_validator("ubicacion")
    @classmethod
    def ubicacion_debe_tener_lat_lon(cls, v: dict) -> dict:
        if "lat" not in v or "lon" not in v:
            raise ValueError("ubicacion debe contener las claves 'lat' y 'lon'")
        if not (-90 <= v["lat"] <= 90):
            raise ValueError("lat debe estar entre -90 y 90")
        if not (-180 <= v["lon"] <= 180):
            raise ValueError("lon debe estar entre -180 y 180")
        return v

    @field_validator("resumen")
    @classmethod
    def resumen_debe_tener_campos_requeridos(cls, v: dict) -> dict:
        campos_requeridos = {"temp_min", "temp_max", "lluvia_total_24h", "viento_max", "dias_forecast"}
        faltantes = campos_requeridos - set(v.keys())
        if faltantes:
            raise ValueError(f"resumen debe contener los campos: {faltantes}")
        return v

    model_config = {"json_schema_extra": {"examples": [
        {
            "cultivo": "papa",
            "ubicacion": {"lat": -38.7359, "lon": -72.5904},
            "alertas": [
                {
                    "tipo": "helada",
                    "mensaje": "Temperatura bajo 0°C entre las 03:00 y 07:00. Riesgo de daño en brotes.",
                    "severidad": "alta",
                    "dia": "2026-05-03",
                    "hora": "04:00",
                },
            ],
            "resumen": {
                "temp_min": -2.1,
                "temp_max": 14.5,
                "lluvia_total_24h": 12.3,
                "viento_max": 28.4,
                "dias_forecast": 7,
            },
            "raw_forecast": None,
        },
    ]}}


# ---------------------------------------------------------------------------
# Preguntar — chat con el asistente
# ---------------------------------------------------------------------------

class PreguntarRequest(BaseModel):
    """Query del usuario para el asistente climático (via Groq o modo offline)."""
    pregunta: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Pregunta del agricultor sobre clima, cultivos o prácticas agrícolas",
    )
    lat: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitud de la ubicación de la consulta",
    )
    lon: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitud de la ubicación de la consulta",
    )
    cultivo: str = Field(
        default="general",
        description="Cultivo sobre el cual se consulta",
    )

    @field_validator("pregunta")
    @classmethod
    def pregunta_no_debe_estar_vacia_ni_solo_espacios(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("La pregunta no puede estar vacía o contener solo espacios")
        return v.strip()

    model_config = {"json_schema_extra": {"examples": [
        {
            "pregunta": "¿Debo regar mis papas hoy con este pronóstico de lluvia?",
            "lat": -38.7359,
            "lon": -72.5904,
            "cultivo": "papa",
        },
    ]}}


class PreguntarResponse(BaseModel):
    """Respuesta del asistente — puede venir de Groq o del motor offline."""
    respuesta: str = Field(..., description="Texto de respuesta generado por el asistente")
    offline: bool = Field(
        default=False,
        description="True si la respuesta fue generada en modo offline (Groq no disponible)",
    )

    model_config = {"json_schema_extra": {"examples": [
        {
            "respuesta": "Hoy no se recomienda regar. El pronóstico indica 12mm de lluvia acumulada en las próximas 6 horas, suficiente para cultivos de papa en etapa de tuberización.",
            "offline": False,
        },
    ]}}


# ---------------------------------------------------------------------------
# Registrar usuario — alta de agricultor
# ---------------------------------------------------------------------------

# Regex para números chilenos: +569 seguido de 8 dígitos, o sin el + inicial
RE_CHILE_WHATSAPP = re.compile(r"^\+?56\s?9\s?\d{4}\s?\d{4}$")


CHILE_CULTIVOS = Literal["papa", "trigo", "manzano", "general"]


class RegistrarRequest(BaseModel):
    """Solicitud de registro de un agricultor para recibir alertas."""
    whatsapp: str = Field(
        ...,
        description="Número de WhatsApp chileno. Formato: +56912345678",
    )
    nombre: str = Field(
        ...,
        min_length=2,
        description="Nombre del agricultor",
    )
    lat: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitud de la parcela",
    )
    lon: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitud de la parcela",
    )
    cultivos: list[CHILE_CULTIVOS] = Field(
        ...,
        min_length=1,
        description="Lista de cultivos a monitorear. Valores permitidos: papa, trigo, manzano, general",
    )
    plan: str = Field(
        default="free",
        description="Plan: free o premium",
    )
    nombre_parcela: str = Field(
        default="Parcela 1",
        description="Nombre descriptivo de la parcela",
    )

    @field_validator("whatsapp")
    @classmethod
    def validar_whatsapp_chileno(cls, v: str) -> str:
        if not RE_CHILE_WHATSAPP.match(v):
            raise ValueError(
                "Formato inválido. Usá +56912345678 (con o sin '+', con o sin espacios)"
            )
        return v

    @field_validator("nombre")
    @classmethod
    def nombre_no_vacio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre no puede estar vacío")
        return v.strip()

    @field_validator("cultivos")
    @classmethod
    def cultivos_no_vacio(cls, v: list) -> list:
        if len(v) == 0:
            raise ValueError("Debe incluir al menos un cultivo")
        return v

    @field_validator("plan")
    @classmethod
    def plan_valido(cls, v: str) -> str:
        if v not in ("free", "premium"):
            raise ValueError("Plan debe ser 'free' o 'premium'")
        return v

    model_config = {"json_schema_extra": {"examples": [
        {
            "whatsapp": "+56912345678",
            "nombre": "Juan Pérez",
            "lat": -38.7359,
            "lon": -72.5904,
            "cultivos": ["papa", "trigo"],
            "plan": "free",
            "nombre_parcela": "Parcela Sur",
        },
    ]}}


class RegistrarResponse(BaseModel):
    """Confirmación de registro exitoso."""
    mensaje: str = Field(..., description="Mensaje de confirmación amigable")
    usuario_id: int = Field(..., description="ID del usuario registrado en SQLite")
    token: str = Field(..., description="Token de autenticación para la API")
    parcela_id: int = Field(..., description="ID de la primera parcela creada")

    model_config = {"json_schema_extra": {"examples": [
        {
            "mensaje": "¡Registro exitoso, Juan! Te avisaremos por WhatsApp ante cualquier alerta para tus cultivos de papa y trigo.",
            "usuario_id": 42,
            "token": "abc123def456...",
            "parcela_id": 1,
        },
    ]}}


# ---------------------------------------------------------------------------
# Parcelas
# ---------------------------------------------------------------------------

class ParcelaRequest(BaseModel):
    """Agregar una parcela nueva."""
    nombre: str = Field(..., min_length=1, description="Nombre de la parcela")
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    cultivos: list[CHILE_CULTIVOS] = Field(..., min_length=1)

    model_config = {"json_schema_extra": {"examples": [
        {"nombre": "Lote Norte", "lat": -38.7, "lon": -72.6, "cultivos": ["trigo"]},
    ]}}


class ParcelaResponse(BaseModel):
    """Datos de una parcela."""
    id: int
    nombre: str
    lat: float
    lon: float
    cultivos: list[CHILE_CULTIVOS]


class ParcelasListResponse(BaseModel):
    """Lista de parcelas de un usuario."""
    usuario_id: int
    plan: str
    max_parcelas: int
    parcelas: list[ParcelaResponse]


# ---------------------------------------------------------------------------
# Suscripción
# ---------------------------------------------------------------------------

class ActualizarPlanRequest(BaseModel):
    """Cambiar plan de suscripción. Token via Authorization header."""
    plan: str = Field(..., description="free o premium")

    @field_validator("plan")
    @classmethod
    def plan_valido(cls, v: str) -> str:
        if v not in ("free", "premium"):
            raise ValueError("Plan debe ser 'free' o 'premium'")
        return v


class PlanResponse(BaseModel):
    """Estado actual del plan."""
    usuario_id: int
    nombre: str
    plan: str
    parcelas_actuales: int
    parcelas_max: int


# ---------------------------------------------------------------------------
# Precios de mercado (ODEPA)
# ---------------------------------------------------------------------------

class PrecioMercado(BaseModel):
    """Precio de un producto agrícola en el mercado mayorista."""
    producto: str
    nombre: str
    precio_actual: float
    precio_min_3m: float
    precio_max_3m: float
    unidad: str
    mercado: str
    tendencia: str
    nota: str
    fuente: str
    actualizado: str


class PreciosResponse(BaseModel):
    """Lista de precios de todos los productos soportados."""
    precios: list[PrecioMercado]
    consultado_en: str

    model_config = {"json_schema_extra": {"examples": [{
        "precios": [{
            "producto": "papa",
            "nombre": "Papa",
            "precio_actual": 650,
            "precio_min_3m": 450,
            "precio_max_3m": 900,
            "unidad": "kg",
            "mercado": "Lo Valledor, Santiago",
            "tendencia": "estable",
            "nota": "Alta variabilidad según variedad.",
            "fuente": "referencia",
            "actualizado": "2026-04-30T10:00:00",
        }],
        "consultado_en": "2026-04-30T10:00:00",
    }]}}


# ---------------------------------------------------------------------------
# Clima histórico
# ---------------------------------------------------------------------------

class HistoricoRequest(BaseModel):
    """Consulta de datos históricos para una ubicación."""
    lat: float = Field(..., ge=-90, le=90, description="Latitud de la parcela")
    lon: float = Field(..., ge=-180, le=180, description="Longitud de la parcela")
    anos: int = Field(default=5, ge=1, le=10, description="Años hacia atrás a consultar")

    model_config = {"json_schema_extra": {"examples": [{"lat": -38.7359, "lon": -72.5904, "anos": 5}]}}


class ResumenAnual(BaseModel):
    """Resumen agregado por año."""
    ano: int
    temp_max_promedio: float
    temp_min_promedio: float
    temp_min_absoluta: float
    precipitacion_total: float
    dias_lluvia: int
    dias_helada: int
    viento_max: float


class HistoricoResponse(BaseModel):
    """Respuesta con datos históricos procesados."""
    ubicacion: dict
    anos_consultados: int
    resumen_anual: list[ResumenAnual]
    datos_diarios: list[dict]

    model_config = {"json_schema_extra": {"examples": [{
        "ubicacion": {"lat": -38.7359, "lon": -72.5904},
        "anos_consultados": 5,
        "resumen_anual": [{
            "ano": 2025, "temp_max_promedio": 18.5, "temp_min_promedio": 6.2,
            "temp_min_absoluta": -3.1, "precipitacion_total": 1150.0,
            "dias_lluvia": 120, "dias_helada": 15, "viento_max": 55.0,
        }],
        "datos_diarios": [],
    }]}}


# ---------------------------------------------------------------------------
# Recomendaciones diarias
# ---------------------------------------------------------------------------

class RecomendacionItem(BaseModel):
    """Una recomendación accionable para una práctica agrícola."""
    accion: str = Field(..., description="Práctica: fumigar, regar, sembrar, cosechar")
    recomendacion: str = Field(..., description="Sí / No / Precaución / Monitorear / Esperar")
    confianza: str = Field(..., description="alta / media / baja")
    detalle: str = Field(..., description="Explicación en español chileno claro")


class RecomendacionResponse(BaseModel):
    """Conjunto de recomendaciones diarias para un cultivo y ubicación."""
    cultivo: str
    ubicacion: dict
    dia: str
    recomendaciones: list[RecomendacionItem]

    model_config = {"json_schema_extra": {"examples": [{
        "cultivo": "papa",
        "ubicacion": {"lat": -38.7359, "lon": -72.5904},
        "dia": "2026-04-30",
        "recomendaciones": [{
            "accion": "fumigar",
            "recomendacion": "Sí",
            "confianza": "alta",
            "detalle": "Hoy es buen día para fumigar tu Papa...",
        }],
    }]}}


# ---------------------------------------------------------------------------
# Enviar alertas — disparo manual o cron
# ---------------------------------------------------------------------------

class EnviarAlertasResponse(BaseModel):
    """Resultado del envío masivo de alertas vía WhatsApp."""
    enviadas: int = Field(
        default=0,
        description="Cantidad de alertas efectivamente enviadas",
    )
    usuarios_afectados: int = Field(
        default=0,
        description="Usuarios que recibieron al menos una alerta",
    )
    detalle: list[dict] = Field(
        default_factory=list,
        description="Métricas agregadas por usuario: usuario_id, cultivo, cantidad_alertas, tipos (sin PII)",
    )
    envios_fallidos: int = Field(
        default=0,
        description="Cantidad de envíos WhatsApp que fallaron",
    )
    whatsapp_activo: bool = Field(
        default=False,
        description="True si WhatsApp Business API está configurada y activa",
    )

    model_config = {"json_schema_extra": {"examples": [
        {
            "enviadas": 3,
            "usuarios_afectados": 2,
            "detalle": [
                {
                    "usuario_id": 42,
                    "cultivo": "papa",
                    "cantidad_alertas": 1,
                    "tipos": ["helada"],
                },
            ],
            "envios_fallidos": 0,
            "whatsapp_activo": True,
        },
    ]}}
