"""Cliente WhatsApp Business Cloud API — envío real de alertas."""

import logging
import re

import httpx

from config import config

logger = logging.getLogger("wenuke.whatsapp")


class WhatsAppClient:
    """Wrapper liviano sobre la WhatsApp Business Cloud API (Meta)."""

    def __init__(self):
        self.token = config.whatsapp_token
        self.phone_number_id = config.whatsapp_phone_number_id
        self.base_url = "https://graph.facebook.com/v21.0"

    @property
    def activo(self) -> bool:
        return bool(self.token and self.phone_number_id)

    async def enviar_mensaje(self, numero: str, texto: str) -> dict:
        """Envía mensaje de texto a un número de WhatsApp en formato E.164. Retorna respuesta de la API."""
        if not self.activo:
            return {"enviado": False, "error": "WhatsApp no configurado (WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID)"}

        # Normalizar a E.164: eliminar espacios, guiones, paréntesis; mantener o prefijar "+"
        digits = re.sub(r'[\s\-\(\)]', '', numero)
        if not digits.startswith('+'):
            digits = '+' + digits
        numero_limpio = digits

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero_limpio,
            "type": "text",
            "text": {"preview_url": False, "body": texto},
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.post(url, json=payload, headers=headers)
                r.raise_for_status()
                return {"enviado": True, "wa_message_id": r.json().get("messages", [{}])[0].get("id", "")}
            except httpx.HTTPError as e:
                detalle = getattr(e, "response", None) and e.response.text[:300]
                logger.error(f"WhatsApp API error enviando a {numero_limpio}: {e} — {detalle}")
                return {"enviado": False, "error": str(e), "detalle": detalle}

    async def enviar_plantilla_alerta(self, numero: str, alertas: list[dict], cultivo: str) -> dict:
        """Envía un resumen de alertas formateado para WhatsApp."""
        if not alertas:
            return {"enviado": False, "error": "Sin alertas para enviar"}

        lineas = [f"🌱 *Werken-mapu — Alerta para {cultivo}*\n"]
        for a in alertas:
            iconos = {"helada": "❄️", "lluvia_intensa": "🌧️", "viento_fuerte": "💨", "granizo": "🌨️"}
            icono = iconos.get(a["tipo"], "⚠️")
            nivel = "🚨 URGENTE" if a["severidad"] == "alta" else "⚠️ Precaución"
            lineas.append(f"{icono} *{a['tipo'].replace('_', ' ').title()}* — {nivel}")
            lineas.append(f"   {a['dia']}")
            lineas.append(f"   {a['mensaje'][:200]}")
            lineas.append("")

        lineas.append("_Responde a este mensaje para consultar al asistente._")
        return await self.enviar_mensaje(numero, "\n".join(lineas))


# Singleton
whatsapp_client = WhatsAppClient()
