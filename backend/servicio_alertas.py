"""Servicio de alertas — lógica compartida entre API y scheduler."""
import logging
from clima import clima_client
from db import (
    obtener_usuarios_con_cultivo_async,
    registrar_alerta_async,
)
from reglas import evaluar_reglas
from whatsapp import whatsapp_client

logger = logging.getLogger("wenuke.servicio_alertas")


async def ejecutar_chequeo_alertas() -> dict:
    """Ejecuta chequeo completo de alertas para todos los cultivos y usuarios.
    Retorna dict con métricas: enviadas, usuarios_afectados, envios_fallidos, detalle."""
    detalle = []
    usuarios_alertados = set()
    envios_fallidos = 0

    for cultivo in ["papa", "trigo", "manzano"]:
        usuarios = await obtener_usuarios_con_cultivo_async(cultivo)
        if not usuarios:
            continue

        ubicaciones_procesadas = {}

        for u in usuarios:
            key = f"{round(u['lat'], 2)},{round(u['lon'], 2)}"

            if key not in ubicaciones_procesadas:
                try:
                    raw = await clima_client.fetch_forecast(u["lat"], u["lon"])
                    hourly = clima_client.parse_hourly(raw)
                    resultado = evaluar_reglas(hourly, cultivo)
                except Exception as e:
                    logger.error(f"Error clima para {key}: {e}")
                    continue
                ubicaciones_procesadas[key] = resultado
            else:
                resultado = ubicaciones_procesadas[key]

            alertas_usuario = resultado.get("alertas", [])
            if not alertas_usuario:
                continue

            for alerta in alertas_usuario:
                await registrar_alerta_async(u["id"], alerta["tipo"], alerta["mensaje"])

            if whatsapp_client.activo:
                envio = await whatsapp_client.enviar_plantilla_alerta(
                    u["whatsapp"], alertas_usuario, cultivo
                )
                if not envio.get("enviado"):
                    envios_fallidos += 1

            usuarios_alertados.add(u["id"])
            detalle.append({
                "usuario_id": u["id"],
                "whatsapp": u["whatsapp"],
                "nombre": u["nombre"],
                "cultivo": cultivo,
                "alertas": [
                    {"tipo": a["tipo"], "severidad": a["severidad"], "dia": a.get("dia", "")}
                    for a in alertas_usuario
                ],
            })

    return {
        "enviadas": sum(len(d["alertas"]) for d in detalle),
        "usuarios_afectados": len(usuarios_alertados),
        "detalle": detalle,
        "envios_fallidos": envios_fallidos,
        "whatsapp_activo": whatsapp_client.activo,
    }
