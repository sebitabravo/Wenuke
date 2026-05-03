"""Motor de reglas por cultivo — dominio puro, cero I/O.
Los umbrales se cargan desde reglas.yaml (si existe) con fallback a diccionario hardcodeado.
"""

import logging
from pathlib import Path
from typing import Literal

from constants import (
    ACCION_COSECHAR,
    ACCION_FUMIGAR,
    ACCION_REGAR,
    ACCION_SEMBRAR,
    CONFIANZA_ALTA,
    CONFIANZA_BAJA,
    CONFIANZA_MEDIA,
    REC_ESPERAR,
    REC_MONITOREAR,
    REC_NO,
    REC_PRECAUCION,
    REC_SI,
    SEVERIDAD_ALTA,
    SEVERIDAD_BAJA,
    SEVERIDAD_MEDIA,
    SEVERIDAD_ORDEN,
)

logger = logging.getLogger("wenuke.reglas")

Cultivo = Literal["papa", "trigo", "manzano", "general"]

_REGLAS_CACHE: dict | None = None


def cargar_reglas() -> dict:
    """Carga umbrales desde reglas.yaml. Si no existe o falla, usa hardcodeados."""
    global _REGLAS_CACHE
    if _REGLAS_CACHE is not None:
        return _REGLAS_CACHE

    yaml_path = Path(__file__).parent / "reglas.yaml"
    if yaml_path.exists():
        try:
            import yaml  # type: ignore[import-untyped,import-not-found]

            with open(yaml_path, encoding="utf-8") as f:
                _REGLAS_CACHE = yaml.safe_load(f)
            logger.info("Reglas cargadas desde reglas.yaml")
            return _REGLAS_CACHE
        except Exception as e:
            logger.warning(f"No se pudo cargar reglas.yaml: {e}. Usando hardcodeadas.")

    _REGLAS_CACHE = _REGLAS_HARDCODEADAS
    return _REGLAS_CACHE


# Umbrales por cultivo: temp_min (°C), lluvia_max_24h (mm), viento_max (km/h),
# precip_hora_max (mm/h proxy granizo), y umbrales para recomendaciones agronómicas.
_REGLAS_HARDCODEADAS: dict[Cultivo, dict] = {
    "papa": {
        "nombre": "Papa",
        "temp_min": 0.0,
        "lluvia_max_24h": 20.0,
        "viento_max": 40.0,
        "helada_severa": -2.0,
        "precip_hora_max": 8.0,
        # Umbrales para recomendaciones
        "viento_fumigar_max": 18.0,
        "lluvia_fumigar_max": 2.0,
        "temp_fumigar_max": 28.0,
        "lluvia_manana_fumigar_max": 4.0,
        "riego_lluvia_suficiente": 10.0,
        "temp_riego_min": 20.0,
        "siembra_temp_min": 3.0,
        "siembra_lluvia_3d_max": 25.0,
        "siembra_viento_max": 30.0,
        "cosecha_lluvia_3d_max": 5.0,
        "cosecha_temp_max": 28.0,
        "cosecha_viento_max": 28.0,
    },
    "trigo": {
        "nombre": "Trigo",
        "temp_min": -2.0,
        "lluvia_max_24h": 25.0,
        "viento_max": 45.0,
        "helada_severa": -4.0,
        "precip_hora_max": 10.0,
        # Umbrales para recomendaciones
        "viento_fumigar_max": 22.0,
        "lluvia_fumigar_max": 2.0,
        "temp_fumigar_max": 30.0,
        "lluvia_manana_fumigar_max": 5.0,
        "riego_lluvia_suficiente": 12.0,
        "temp_riego_min": 18.0,
        "siembra_temp_min": 1.0,
        "siembra_lluvia_3d_max": 35.0,
        "siembra_viento_max": 40.0,
        "cosecha_lluvia_3d_max": 5.0,
        "cosecha_temp_max": 32.0,
        "cosecha_viento_max": 32.0,
    },
    "manzano": {
        "nombre": "Manzano",
        "temp_min": 0.0,
        "lluvia_max_24h": 15.0,
        "viento_max": 35.0,
        "helada_severa": -1.5,
        "precip_hora_max": 5.0,
        # Umbrales para recomendaciones
        "viento_fumigar_max": 15.0,
        "lluvia_fumigar_max": 1.0,
        "temp_fumigar_max": 26.0,
        "lluvia_manana_fumigar_max": 3.0,
        "riego_lluvia_suficiente": 8.0,
        "temp_riego_min": 22.0,
        "siembra_temp_min": 2.0,
        "siembra_lluvia_3d_max": 25.0,
        "siembra_viento_max": 30.0,
        "cosecha_lluvia_3d_max": 3.0,
        "cosecha_temp_max": 28.0,
        "cosecha_viento_max": 25.0,
    },
    "general": {
        "nombre": "General",
        "temp_min": 0.0,
        "lluvia_max_24h": 20.0,
        "viento_max": 40.0,
        "helada_severa": -2.0,
        "precip_hora_max": 8.0,
        # Umbrales para recomendaciones
        "viento_fumigar_max": 20.0,
        "lluvia_fumigar_max": 2.0,
        "temp_fumigar_max": 28.0,
        "lluvia_manana_fumigar_max": 5.0,
        "riego_lluvia_suficiente": 10.0,
        "temp_riego_min": 20.0,
        "siembra_temp_min": 2.0,
        "siembra_lluvia_3d_max": 30.0,
        "siembra_viento_max": 35.0,
        "cosecha_lluvia_3d_max": 5.0,
        "cosecha_temp_max": 30.0,
        "cosecha_viento_max": 30.0,
    },
}


def _severidad_helada(temp: float, umbral: float, severa: float) -> str:
    if temp <= severa:
        return SEVERIDAD_ALTA
    return SEVERIDAD_MEDIA


def _severidad_lluvia(total: float, umbral: float) -> str:
    if total >= umbral * 1.5:
        return SEVERIDAD_ALTA
    return SEVERIDAD_MEDIA


def _severidad_viento(vel: float, umbral: float) -> str:
    if vel >= umbral + 10:
        return SEVERIDAD_ALTA
    return SEVERIDAD_MEDIA


def _severidad_granizo(precip_hora: float, umbral: float) -> str:
    if precip_hora >= umbral * 1.5:
        return SEVERIDAD_ALTA
    if precip_hora >= umbral * 1.2:
        return SEVERIDAD_MEDIA
    return SEVERIDAD_BAJA


def evaluar_reglas(forecast_hourly: list[dict], cultivo: Cultivo = "general") -> dict:
    """Evalúa datos horarios contra reglas del cultivo. Retorna alertas encontradas."""
    reglas = cargar_reglas().get(cultivo, cargar_reglas()["general"])
    alertas: list[dict] = []

    # Acumular lluvia por día
    lluvia_por_dia: dict[str, float] = {}
    for punto in forecast_hourly:
        dia = punto["hora"][:10]  # "YYYY-MM-DD"
        lluvia_por_dia[dia] = lluvia_por_dia.get(dia, 0.0) + punto.get("precipitacion", 0.0)

    # Evaluar heladas, viento y granizo (por punto horario)
    heladas_encontradas: set[str] = set()
    vientos_encontrados: set[str] = set()
    granizos_encontrados: set[str] = set()

    for punto in forecast_hourly:
        dia = punto["hora"][:10]
        hora = punto["hora"][11:16]  # "HH:MM"
        temp = punto.get("temperatura")
        viento = punto.get("viento")
        precip = punto.get("precipitacion", 0.0)

        # Helada
        if temp is not None and temp <= reglas["temp_min"] and dia not in heladas_encontradas:
            heladas_encontradas.add(dia)
            severidad = _severidad_helada(temp, reglas["temp_min"], reglas["helada_severa"])
            alertas.append({
                "tipo": "helada",
                "mensaje": _mensaje_helada(reglas["nombre"], temp, hora, dia, severidad),
                "severidad": severidad,
                "dia": dia,
                "hora": hora,
            })

        # Viento
        if viento is not None and viento >= reglas["viento_max"] and dia not in vientos_encontrados:
            vientos_encontrados.add(dia)
            severidad = _severidad_viento(viento, reglas["viento_max"])
            alertas.append({
                "tipo": "viento_fuerte",
                "mensaje": _mensaje_viento(reglas["nombre"], viento, dia, severidad),
                "severidad": severidad,
                "dia": dia,
                "hora": None,
            })

        # Granizo (proxy: precipitación horaria intensa + temperatura en rango de formación 0-15°C)
        if (
            precip >= reglas["precip_hora_max"]
            and temp is not None
            and 0 <= temp <= 15
            and dia not in granizos_encontrados
        ):
            granizos_encontrados.add(dia)
            severidad = _severidad_granizo(precip, reglas["precip_hora_max"])
            alertas.append({
                "tipo": "granizo",
                "mensaje": _mensaje_granizo(reglas["nombre"], precip, hora, dia, severidad),
                "severidad": severidad,
                "dia": dia,
                "hora": hora,
            })

    # Evaluar lluvia intensa (por día acumulado)
    for dia, total in lluvia_por_dia.items():
        if total >= reglas["lluvia_max_24h"]:
            severidad = _severidad_lluvia(total, reglas["lluvia_max_24h"])
            alertas.append({
                "tipo": "lluvia_intensa",
                "mensaje": _mensaje_lluvia(reglas["nombre"], total, dia, severidad),
                "severidad": severidad,
                "dia": dia,
                "hora": None,
            })

    # Ordenar por severidad y día
    alertas.sort(key=lambda a: (a["dia"], SEVERIDAD_ORDEN.get(a["severidad"], 2)))

    return {
        "alertas": alertas,
        "cultivo": reglas["nombre"],
    }


def evaluar_alertas_para_cultivo(forecast_hourly: list[dict], cultivo: Cultivo, lat: float, lon: float) -> dict:
    """Wrapper que incluye metadatos de ubicación. Usado por el worker de alertas."""
    resultado = evaluar_reglas(forecast_hourly, cultivo)
    resultado["ubicacion"] = {"lat": lat, "lon": lon}
    return resultado


def _build_context_agronomico(
    forecast_hourly: list[dict], daily: list[dict], cultivo: Cultivo
) -> dict:
    """Construye diccionario con todos los datos necesarios para generar recomendaciones."""
    hoy = daily[0]
    manana = daily[1] if len(daily) > 1 else hoy
    reglas = cargar_reglas().get(cultivo, cargar_reglas()["general"])

    lluvia_3d = (
        hoy.get("precipitacion_total", 0)
        + manana.get("precipitacion_total", 0)
        + (daily[2].get("precipitacion_total", 0) if len(daily) > 2 else 0)
    )

    return {
        "nombre": reglas["nombre"],
        "reglas": reglas,
        "temp_min_hoy": hoy.get("temp_min") or 0,
        "temp_max_hoy": hoy.get("temp_max") or 20,
        "temp_min_manana": manana.get("temp_min") or hoy.get("temp_min") or 0,
        "lluvia_hoy": hoy.get("precipitacion_total", 0),
        "lluvia_manana": manana.get("precipitacion_total", 0),
        "lluvia_3d": lluvia_3d,
        "viento_hoy": hoy.get("viento_max") or 0,
        "lluvia_proximas_6h": sum(
            p.get("precipitacion", 0) for p in forecast_hourly[:6]
        ),
    }


def _recomendar_fumigar(ctx: dict) -> dict:
    r = ctx["reglas"]
    ok = (
        ctx["viento_hoy"] < r["viento_fumigar_max"]
        and ctx["lluvia_hoy"] < r["lluvia_fumigar_max"]
        and ctx["lluvia_manana"] < r["lluvia_manana_fumigar_max"]
        and ctx["temp_max_hoy"] < r["temp_fumigar_max"]
    )
    mal = ctx["viento_hoy"] >= r["viento_fumigar_max"] or ctx["lluvia_hoy"] >= r["lluvia_fumigar_max"]

    if ok:
        return {
            "accion": ACCION_FUMIGAR, "recomendacion": REC_SI, "confianza": CONFIANZA_ALTA,
            "detalle": (
                f"Hoy es buen día para fumigar tu {ctx['nombre']}. Sin viento fuerte, "
                f"sin lluvia a la vista, y temperatura bajo {r['temp_fumigar_max']:.0f}°C. "
                f"Hacelo temprano en la mañana."
            ),
        }
    if mal:
        return {
            "accion": ACCION_FUMIGAR, "recomendacion": REC_NO, "confianza": CONFIANZA_ALTA,
            "detalle": (
                f"Hoy NO conviene fumigar tu {ctx['nombre']}. "
                f"{'Hay viento fuerte.' if ctx['viento_hoy'] >= r['viento_fumigar_max'] else ''}"
                f"{'Hay lluvia prevista.' if ctx['lluvia_hoy'] >= r['lluvia_fumigar_max'] else ''}"
                f"{'Se espera lluvia mañana.' if ctx['lluvia_manana'] >= r['lluvia_manana_fumigar_max'] else ''}"
            ),
        }
    return {
        "accion": ACCION_FUMIGAR, "recomendacion": REC_PRECAUCION, "confianza": CONFIANZA_MEDIA,
        "detalle": (
            f"Si vas a fumigar tu {ctx['nombre']}, hacelo temprano y revisá que no haya viento. "
            f"Temperatura máxima de {ctx['temp_max_hoy']:.0f}°C."
        ),
    }


def _recomendar_regar(ctx: dict) -> dict:
    r = ctx["reglas"]
    if ctx["lluvia_hoy"] >= r["riego_lluvia_suficiente"] or ctx["lluvia_proximas_6h"] >= 5:
        return {
            "accion": ACCION_REGAR, "recomendacion": REC_NO, "confianza": CONFIANZA_ALTA,
            "detalle": (
                f"Hoy NO hace falta regar. Se esperan {ctx['lluvia_hoy']:.0f} mm de lluvia. "
                f"Aprovechá para revisar drenajes."
            ),
        }
    if ctx["lluvia_hoy"] < 2 and ctx["lluvia_proximas_6h"] < 2 and ctx["temp_max_hoy"] > r["temp_riego_min"]:
        return {
            "accion": ACCION_REGAR, "recomendacion": REC_SI, "confianza": CONFIANZA_MEDIA,
            "detalle": (
                f"Conviene regar tu {ctx['nombre']} hoy. Poca lluvia prevista y temperatura "
                f"máxima de {ctx['temp_max_hoy']:.0f}°C. Regá al atardecer para evitar evaporación."
            ),
        }
    return {
        "accion": ACCION_REGAR, "recomendacion": REC_MONITOREAR, "confianza": CONFIANZA_BAJA,
        "detalle": (
            f"Revisá la humedad del suelo antes de regar. "
            f"Lluvia prevista: {ctx['lluvia_hoy']:.0f} mm hoy, {ctx['lluvia_manana']:.0f} mm mañana."
        ),
    }


def _recomendar_sembrar(ctx: dict) -> dict:
    r = ctx["reglas"]
    # Riesgo de helada mañana: semilla recién sembrada es vulnerable
    if ctx["temp_min_manana"] <= r["temp_min"]:
        return {
            "accion": ACCION_SEMBRAR, "recomendacion": REC_NO, "confianza": CONFIANZA_ALTA,
            "detalle": (
                f"No siembres {ctx['nombre']} hoy. Se espera helada mañana con temperatura "
                f"mínima de {ctx['temp_min_manana']:.0f}°C. Las semillas y brotes recién "
                f"sembrados son muy vulnerables a la congelación."
            ),
        }
    if (
        ctx["temp_min_hoy"] > r["siembra_temp_min"]
        and ctx["lluvia_3d"] < r["siembra_lluvia_3d_max"]
        and ctx["viento_hoy"] < r["siembra_viento_max"]
    ):
        return {
            "accion": ACCION_SEMBRAR, "recomendacion": REC_SI, "confianza": CONFIANZA_MEDIA,
            "detalle": (
                f"Buen momento para sembrar {ctx['nombre']}. Suelo con temperatura adecuada "
                f"(>{r['siembra_temp_min']:.0f}°C), sin exceso de lluvia en los próximos 3 días "
                f"({ctx['lluvia_3d']:.0f} mm)."
            ),
        }
    if ctx["temp_min_hoy"] <= r["siembra_temp_min"]:
        return {
            "accion": ACCION_SEMBRAR, "recomendacion": REC_NO, "confianza": CONFIANZA_ALTA,
            "detalle": (
                f"No siembres {ctx['nombre']} hoy. Temperatura mínima de "
                f"{ctx['temp_min_hoy']:.0f}°C, riesgo de daño por frío en semillas y brotes."
            ),
        }
    return {
        "accion": ACCION_SEMBRAR, "recomendacion": REC_ESPERAR, "confianza": CONFIANZA_MEDIA,
        "detalle": (
            f"Esperá unos días para sembrar {ctx['nombre']}. "
            f"Lluvia acumulada en 3 días: {ctx['lluvia_3d']:.0f} mm. "
            f"Viento: {ctx['viento_hoy']:.0f} km/h."
        ),
    }


def _recomendar_cosechar(ctx: dict) -> dict:
    r = ctx["reglas"]
    if (
        ctx["lluvia_3d"] < r["cosecha_lluvia_3d_max"]
        and ctx["temp_max_hoy"] < r["cosecha_temp_max"]
        and ctx["viento_hoy"] < r["cosecha_viento_max"]
    ):
        return {
            "accion": ACCION_COSECHAR, "recomendacion": REC_SI, "confianza": CONFIANZA_ALTA,
            "detalle": (
                f"Buen momento para cosechar tu {ctx['nombre']}. Ventana de 3 días secos, "
                f"temperatura máxima de {ctx['temp_max_hoy']:.0f}°C. "
                f"La cosecha en seco da mejor calidad."
            ),
        }
    if ctx["lluvia_hoy"] >= 5:
        return {
            "accion": ACCION_COSECHAR, "recomendacion": REC_NO, "confianza": CONFIANZA_ALTA,
            "detalle": (
                f"No coseches {ctx['nombre']} hoy. Lluvia de {ctx['lluvia_hoy']:.0f} mm. "
                f"La cosecha con lluvia daña la calidad y favorece hongos en almacenamiento."
            ),
        }
    return {
        "accion": ACCION_COSECHAR, "recomendacion": REC_PRECAUCION, "confianza": CONFIANZA_MEDIA,
        "detalle": (
            f"Si vas a cosechar tu {ctx['nombre']}, revisá que no llueva en las próximas 6 horas. "
            f"Temperatura: {ctx['temp_min_hoy']:.0f}°C – {ctx['temp_max_hoy']:.0f}°C."
        ),
    }


def generar_recomendaciones(forecast_hourly: list[dict], daily: list[dict], cultivo: Cultivo) -> list[dict]:
    """Genera recomendaciones diarias accionables para el agricultor.

    Delega cada tipo de recomendación a su propia función (fumigar, regar,
    sembrar, cosechar) para mantener baja la complejidad ciclomática.
    """
    if not daily:
        return []

    ctx = _build_context_agronomico(forecast_hourly, daily, cultivo)
    return [
        _recomendar_fumigar(ctx),
        _recomendar_regar(ctx),
        _recomendar_sembrar(ctx),
        _recomendar_cosechar(ctx),
    ]


# --- Mensajes en español chileno claro ---

def _mensaje_helada(cultivo: str, temp: float, hora: str, dia: str, severidad: str) -> str:
    emoji = "⚠️" if severidad == SEVERIDAD_MEDIA else "🚨"
    return (
        f"{emoji} ALERTA DE HELADA para {cultivo}\n"
        f"Temperatura prevista: {temp:.1f}°C el {dia} a las {hora}.\n"
        f"Recomendación: Protege el cultivo. Si tienes sistema de riego, "
        f"considera regar de noche para reducir el daño por congelación."
    )


def _mensaje_lluvia(cultivo: str, total: float, dia: str, severidad: str) -> str:
    emoji = "🌧️" if severidad == SEVERIDAD_MEDIA else "⛈️"
    return (
        f"{emoji} LLUVIA INTENSA prevista para {cultivo}\n"
        f"Se esperan {total:.0f} mm acumulados el {dia}.\n"
        f"Recomendación: No fumigues ni riegues. Si puedes, adelanta la cosecha."
    )


def _mensaje_viento(cultivo: str, vel: float, dia: str, severidad: str) -> str:
    emoji = "💨" if severidad == SEVERIDAD_MEDIA else "🌪️"
    return (
        f"{emoji} VIENTO FUERTE previsto para {cultivo}\n"
        f"Ráfagas de hasta {vel:.0f} km/h previstas el {dia}.\n"
        f"Recomendación: Revisa estructuras de soporte. No fumigues."
    )


def _mensaje_granizo(cultivo: str, precip: float, hora: str, dia: str, severidad: str) -> str:
    emoji = "🌨️" if severidad == SEVERIDAD_BAJA else ("⚠️" if severidad == SEVERIDAD_MEDIA else "🚨")
    return (
        f"{emoji} RIESGO DE GRANIZO para {cultivo}\n"
        f"Precipitación intensa de {precip:.1f} mm/h prevista el {dia} a las {hora}.\n"
        f"Recomendación: Protege cultivos sensibles con malla antigranizo si dispones. "
        f"Evita trabajar en la parcela durante el evento."
    )
