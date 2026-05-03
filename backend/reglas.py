"""Motor de reglas por cultivo — dominio puro, cero I/O.
Los umbrales se cargan desde reglas.yaml (si existe) con fallback a diccionario hardcodeado.
"""

import logging
from pathlib import Path
from typing import Literal

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
        return "alta"
    return "media"


def _severidad_lluvia(total: float, umbral: float) -> str:
    if total >= umbral * 1.5:
        return "alta"
    return "media"


def _severidad_viento(vel: float, umbral: float) -> str:
    if vel >= umbral + 10:
        return "alta"
    return "media"


def _severidad_granizo(precip_hora: float, umbral: float) -> str:
    if precip_hora >= umbral * 1.5:
        return "alta"
    if precip_hora >= umbral * 1.2:
        return "media"
    return "baja"


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
    orden = {"alta": 0, "media": 1, "baja": 2}
    alertas.sort(key=lambda a: (a["dia"], orden.get(a["severidad"], 2)))

    return {
        "alertas": alertas,
        "cultivo": reglas["nombre"],
    }


def evaluar_alertas_para_cultivo(forecast_hourly: list[dict], cultivo: Cultivo, lat: float, lon: float) -> dict:
    """Wrapper que incluye metadatos de ubicación. Usado por el worker de alertas."""
    resultado = evaluar_reglas(forecast_hourly, cultivo)
    resultado["ubicacion"] = {"lat": lat, "lon": lon}
    return resultado


def generar_recomendaciones(forecast_hourly: list[dict], daily: list[dict], cultivo: Cultivo) -> list[dict]:
    """Genera recomendaciones diarias accionables para el agricultor."""
    if not daily:
        return []

    hoy = daily[0]
    manana = daily[1] if len(daily) > 1 else hoy

    reglas = cargar_reglas().get(cultivo, cargar_reglas()["general"])
    nombre = reglas["nombre"]

    temp_min_hoy = hoy.get("temp_min") or 0
    temp_max_hoy = hoy.get("temp_max") or 20
    temp_min_manana = manana.get("temp_min") or temp_min_hoy
    lluvia_hoy = hoy.get("precipitacion_total", 0)
    lluvia_manana = manana.get("precipitacion_total", 0)
    viento_hoy = hoy.get("viento_max") or 0

    # Determinar horas de lluvia hoy
    lluvia_proximas_6h = sum(
        p.get("precipitacion", 0)
        for p in forecast_hourly[:6]
    )

    # Cargar umbrales del cultivo
    v_fumigar = reglas["viento_fumigar_max"]
    l_fumigar = reglas["lluvia_fumigar_max"]
    t_fumigar = reglas["temp_fumigar_max"]
    l_manana_fumigar = reglas["lluvia_manana_fumigar_max"]
    riego_lluvia = reglas["riego_lluvia_suficiente"]
    t_riego = reglas["temp_riego_min"]
    siembra_tmin = reglas["siembra_temp_min"]
    siembra_lluvia = reglas["siembra_lluvia_3d_max"]
    siembra_viento = reglas["siembra_viento_max"]
    cosecha_lluvia = reglas["cosecha_lluvia_3d_max"]
    cosecha_temp = reglas["cosecha_temp_max"]
    cosecha_viento = reglas["cosecha_viento_max"]

    recs = []

    # --- Fumigar ---
    if viento_hoy < v_fumigar and lluvia_hoy < l_fumigar and lluvia_manana < l_manana_fumigar and temp_max_hoy < t_fumigar:
        recs.append({
            "accion": "fumigar",
            "recomendacion": "Sí",
            "confianza": "alta",
            "detalle": (
                f"Hoy es buen día para fumigar tu {nombre}. Sin viento fuerte, sin lluvia a la vista, "
                f"y temperatura bajo {t_fumigar:.0f}°C. Hacelo temprano en la mañana."
            ),
        })
    elif viento_hoy >= v_fumigar or lluvia_hoy >= l_fumigar:
        recs.append({
            "accion": "fumigar",
            "recomendacion": "No",
            "confianza": "alta",
            "detalle": (
                f"Hoy NO conviene fumigar tu {nombre}. "
                f"{'Hay viento fuerte.' if viento_hoy >= v_fumigar else ''}"
                f"{'Hay lluvia prevista.' if lluvia_hoy >= l_fumigar else ''}"
                f"{'Se espera lluvia mañana.' if lluvia_manana >= l_manana_fumigar else ''}"
            ),
        })
    else:
        recs.append({
            "accion": "fumigar",
            "recomendacion": "Precaución",
            "confianza": "media",
            "detalle": (
                f"Si vas a fumigar tu {nombre}, hacelo temprano y revisá que no haya viento. "
                f"Temperatura máxima de {temp_max_hoy:.0f}°C."
            ),
        })

    # --- Regar ---
    if lluvia_hoy >= riego_lluvia or lluvia_proximas_6h >= 5:
        recs.append({
            "accion": "regar",
            "recomendacion": "No",
            "confianza": "alta",
            "detalle": (
                f"Hoy NO hace falta regar. Se esperan {lluvia_hoy:.0f} mm de lluvia. "
                f"Aprovechá para revisar drenajes."
            ),
        })
    elif lluvia_hoy < 2 and lluvia_proximas_6h < 2 and temp_max_hoy > t_riego:
        recs.append({
            "accion": "regar",
            "recomendacion": "Sí",
            "confianza": "media",
            "detalle": (
                f"Conviene regar tu {nombre} hoy. Poca lluvia prevista y temperatura máxima de {temp_max_hoy:.0f}°C. "
                f"Regá al atardecer para evitar evaporación."
            ),
        })
    else:
        recs.append({
            "accion": "regar",
            "recomendacion": "Monitorear",
            "confianza": "baja",
            "detalle": (
                f"Revisá la humedad del suelo antes de regar. "
                f"Lluvia prevista: {lluvia_hoy:.0f} mm hoy, {lluvia_manana:.0f} mm mañana."
            ),
        })

    # --- Sembrar ---
    lluvia_3d = lluvia_hoy + lluvia_manana + (daily[2].get("precipitacion_total", 0) if len(daily) > 2 else 0)

    # Primero: revisar riesgo de helada mañana (semilla recién sembrada es vulnerable)
    if temp_min_manana <= reglas["temp_min"]:
        recs.append({
            "accion": "sembrar",
            "recomendacion": "No",
            "confianza": "alta",
            "detalle": (
                f"No siembres {nombre} hoy. Se espera helada mañana con temperatura "
                f"mínima de {temp_min_manana:.0f}°C. Las semillas y brotes recién sembrados "
                f"son muy vulnerables a la congelación."
            ),
        })
    elif temp_min_hoy > siembra_tmin and lluvia_3d < siembra_lluvia and viento_hoy < siembra_viento:
        recs.append({
            "accion": "sembrar",
            "recomendacion": "Sí",
            "confianza": "media",
            "detalle": (
                f"Buen momento para sembrar {nombre}. Suelo con temperatura adecuada "
                f"(>{siembra_tmin:.0f}°C), sin exceso de lluvia en los próximos 3 días "
                f"({lluvia_3d:.0f} mm)."
            ),
        })
    elif temp_min_hoy <= siembra_tmin:
        recs.append({
            "accion": "sembrar",
            "recomendacion": "No",
            "confianza": "alta",
            "detalle": (
                f"No siembres {nombre} hoy. Temperatura mínima de {temp_min_hoy:.0f}°C, "
                f"riesgo de daño por frío en semillas y brotes."
            ),
        })
    else:
        recs.append({
            "accion": "sembrar",
            "recomendacion": "Esperar",
            "confianza": "media",
            "detalle": (
                f"Esperá unos días para sembrar {nombre}. "
                f"Lluvia acumulada en 3 días: {lluvia_3d:.0f} mm. Viento: {viento_hoy:.0f} km/h."
            ),
        })

    # --- Cosechar ---
    if lluvia_3d < cosecha_lluvia and temp_max_hoy < cosecha_temp and viento_hoy < cosecha_viento:
        recs.append({
            "accion": "cosechar",
            "recomendacion": "Sí",
            "confianza": "alta",
            "detalle": (
                f"Buen momento para cosechar tu {nombre}. Ventana de 3 días secos, "
                f"temperatura máxima de {temp_max_hoy:.0f}°C. La cosecha en seco da mejor calidad."
            ),
        })
    elif lluvia_hoy >= 5:
        recs.append({
            "accion": "cosechar",
            "recomendacion": "No",
            "confianza": "alta",
            "detalle": (
                f"No coseches {nombre} hoy. Lluvia de {lluvia_hoy:.0f} mm. "
                f"La cosecha con lluvia daña la calidad y favorece hongos en almacenamiento."
            ),
        })
    else:
        recs.append({
            "accion": "cosechar",
            "recomendacion": "Precaución",
            "confianza": "media",
            "detalle": (
                f"Si vas a cosechar tu {nombre}, revisá que no llueva en las próximas 6 horas. "
                f"Temperatura: {temp_min_hoy:.0f}°C – {temp_max_hoy:.0f}°C."
            ),
        })

    return recs


# --- Mensajes en español chileno claro ---

def _mensaje_helada(cultivo: str, temp: float, hora: str, dia: str, severidad: str) -> str:
    emoji = "⚠️" if severidad == "media" else "🚨"
    return (
        f"{emoji} ALERTA DE HELADA para {cultivo}\n"
        f"Temperatura prevista: {temp:.1f}°C el {dia} a las {hora}.\n"
        f"Recomendación: Protege el cultivo. Si tienes sistema de riego, "
        f"considera regar de noche para reducir el daño por congelación."
    )


def _mensaje_lluvia(cultivo: str, total: float, dia: str, severidad: str) -> str:
    emoji = "🌧️" if severidad == "media" else "⛈️"
    return (
        f"{emoji} LLUVIA INTENSA prevista para {cultivo}\n"
        f"Se esperan {total:.0f} mm acumulados el {dia}.\n"
        f"Recomendación: No fumigues ni riegues. Si puedes, adelanta la cosecha."
    )


def _mensaje_viento(cultivo: str, vel: float, dia: str, severidad: str) -> str:
    emoji = "💨" if severidad == "media" else "🌪️"
    return (
        f"{emoji} VIENTO FUERTE previsto para {cultivo}\n"
        f"Ráfagas de hasta {vel:.0f} km/h previstas el {dia}.\n"
        f"Recomendación: Revisa estructuras de soporte. No fumigues."
    )


def _mensaje_granizo(cultivo: str, precip: float, hora: str, dia: str, severidad: str) -> str:
    emoji = "🌨️" if severidad == "baja" else ("⚠️" if severidad == "media" else "🚨")
    return (
        f"{emoji} RIESGO DE GRANIZO para {cultivo}\n"
        f"Precipitación intensa de {precip:.1f} mm/h prevista el {dia} a las {hora}.\n"
        f"Recomendación: Protege cultivos sensibles con malla antigranizo si dispones. "
        f"Evita trabajar en la parcela durante el evento."
    )
