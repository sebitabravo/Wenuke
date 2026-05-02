"""Cliente LLM — Groq (Llama 3.1) con fallback offline."""

import json
import logging
from pathlib import Path

from config import config

logger = logging.getLogger("wenuke.llm")

SYSTEM_PROMPT = """Eres "Werken-mapu", un asistente agrícola para pequeños agricultores de La Araucanía, Chile. Tu trabajo es ayudar al agricultor a tomar decisiones diarias sobre su cultivo basándote en el clima real.

REGLAS:
- Responde en español chileno claro y simple, como hablaría un técnico agrícola de confianza
- Máximo 3 oraciones por respuesta
- Si la pregunta requiere datos meteorológicos, usa los datos provistos
- Si no tienes datos suficientes, di "No tengo esa información, compa" — NO INVENTES
- Trata al usuario con respeto, sin tecnicismos innecesarios
- Si detectas riesgo (helada, lluvia intensa, viento fuerte), avísalo claramente
- Usa palabras locales: "compa", "no más", términos comunes en el campo chileno"""


class LLMClient:
    def __init__(self):
        self.api_key = config.groq_api_key
        self.model = config.groq_model
        self.client = None
        self._offline_respuestas: dict | None = None
        if self.api_key:
            try:
                from groq import AsyncGroq
                self.client = AsyncGroq(api_key=self.api_key)
            except ImportError:
                logger.warning("groq no instalado, modo offline")

    @property
    def modo_offline(self) -> bool:
        return self.client is None

    @property
    def offline_respuestas(self) -> dict:
        """Carga respuestas offline desde JSON, con fallback a diccionario duro."""
        if self._offline_respuestas is not None:
            return self._offline_respuestas

        json_path = Path(__file__).parent / "respuestas_offline.json"
        try:
            with open(json_path, encoding="utf-8") as f:
                self._offline_respuestas = json.load(f)
            logger.info("Respuestas offline cargadas desde JSON")
        except Exception as e:
            logger.warning(f"No se pudo cargar respuestas_offline.json: {e}")
            self._offline_respuestas = self._hardcoded_respuestas()

        return self._offline_respuestas

    @staticmethod
    def _hardcoded_respuestas() -> dict:
        """Fallback duro si no se puede cargar el JSON."""
        return {
            "categorias": [
                {
                    "palabras_clave": ["helada", "hielo", "congelar", "frío", "frio", "escarcha"],
                    "respuesta": (
                        "Para proteger tu {cultivo} de las heladas: riega de noche si tienes sistema, "
                        "cubre los brotes con malla antihelada o plástico, y mantén el suelo húmedo. "
                        "La tierra mojada retiene más calor que la tierra seca."
                    ),
                },
                {
                    "palabras_clave": ["lluvia", "llover", "llueve", "precipitación", "agua"],
                    "respuesta": (
                        "Con lluvia fuerte no conviene fumigar porque el producto se lava. "
                        "Si ya fumigaste, revisa si pasaron al menos 4 horas antes de la lluvia. "
                        "Aprovecha de revisar los canales de drenaje de tu parcela."
                    ),
                },
                {
                    "palabras_clave": ["viento", "ventoso", "ráfaga", "ventisca"],
                    "respuesta": (
                        "Con viento fuerte no fumigues: el producto se va con el viento y no protege tu cultivo. "
                        "Revisa que las estructuras de soporte estén firmes. Si tienes trigo, atención al volcado."
                    ),
                },
                {
                    "palabras_clave": ["granizo", "granizada", "granizar", "piedra"],
                    "respuesta": (
                        "Con riesgo de granizo protege los cultivos sensibles con malla antigranizo si dispones. "
                        "No trabajes en la parcela durante la tormenta. Después del evento revisa daños en brotes y frutos."
                    ),
                },
                {
                    "palabras_clave": ["sembrar", "siembra", "plantar", "siembro", "semilla"],
                    "respuesta": (
                        "Para decidir si sembrar {cultivo}, fijate en la temperatura del suelo y la lluvia prevista. "
                        "Lo ideal es sembrar con suelo húmedo pero sin lluvia fuerte en los 3 días siguientes. "
                        "Revisa el pronóstico en la sección de clima para decidir el mejor día."
                    ),
                },
                {
                    "palabras_clave": ["cosechar", "cosecha", "recolectar"],
                    "respuesta": (
                        "Para cosechar tu {cultivo}, busca una ventana de 2-3 días sin lluvia. "
                        "La cosecha con suelo seco da mejor calidad y evita hongos. "
                        "Si viene helada, adelanta la cosecha aunque no esté 100% listo."
                    ),
                },
                {
                    "palabras_clave": ["fumigar", "fumigo", "pesticida", "plaga"],
                    "respuesta": (
                        "El mejor momento para fumigar es temprano en la mañana, sin viento y sin lluvia prevista en 6 horas. "
                        "Con temperatures sobre 25°C algunos productos se evaporan y pierden efecto."
                    ),
                },
                {
                    "palabras_clave": ["regar", "riego", "agua riego"],
                    "respuesta": (
                        "Revisa el pronóstico antes de regar. Si llueve en las próximas 24 horas, no gastes agua. "
                        "El mejor momento para regar es al atardecer, así el agua no se evapora con el sol."
                    ),
                },
            ],
            "default": (
                "Compa, soy Werken-mapu, tu asistente climático. Puedo ayudarte a decidir cuándo sembrar, "
                "fumigar, regar o cosechar tu {cultivo} según el clima. "
                "Pregúntame cosas como: ¿llueve mañana?, ¿puedo fumigar hoy?, ¿hay riesgo de helada?"
            ),
        }

    async def preguntar(self, pregunta: str, contexto_clima: dict, cultivo: str) -> dict:
        """Responde pregunta del agricultor. Retorna dict con 'respuesta' y 'offline'."""
        if self.modo_offline:
            return {"respuesta": self._respuesta_offline(pregunta, cultivo), "offline": True}

        prompt_usuario = (
            f"DATOS DEL CLIMA PARA LA PARCELA (próximos 7 días):\n"
            f"{self._formatear_contexto(contexto_clima)}\n\n"
            f"CULTIVO: {cultivo}\n\n"
            f"PREGUNTA: {pregunta}\n\n"
            f"RESPUESTA:"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_usuario},
                ],
                max_tokens=500,
                temperature=0.3,
            )
            return {
                "respuesta": response.choices[0].message.content.strip(),
                "offline": False,
            }
        except Exception as e:
            logger.error(f"Groq error: {e}")
            return {"respuesta": self._respuesta_offline(pregunta, cultivo), "offline": True}

    def _formatear_contexto(self, contexto: dict) -> str:
        """Formatea datos del clima para el prompt del LLM."""
        resumen = contexto.get("resumen", {})
        alertas = contexto.get("alertas", [])
        partes = [
            f"- Temp. mínima próx. días: {resumen.get('temp_min', 'N/D')}°C",
            f"- Temp. máxima próx. días: {resumen.get('temp_max', 'N/D')}°C",
            f"- Lluvia acumulada 24h: {resumen.get('lluvia_total_24h', 'N/D')} mm",
            f"- Viento máximo: {resumen.get('viento_max', 'N/D')} km/h",
        ]
        if alertas:
            partes.append("\n⚠️ ALERTAS ACTIVAS:")
            for a in alertas:
                partes.append(f"  - {a['tipo']}: {a['mensaje'][:100]}")
        return "\n".join(partes)

    def _respuesta_offline(self, pregunta: str, cultivo: str) -> str:
        """Respuestas predefinidas cuando no hay conexión al LLM.
        Carga desde JSON, con fallback a diccionario hardcodeado."""
        respuestas = self.offline_respuestas
        p = pregunta.lower()

        for categoria in respuestas["categorias"]:
            if any(w in p for w in categoria["palabras_clave"]):
                return categoria["respuesta"].format(cultivo=cultivo)

        # Default
        return respuestas["default"].format(cultivo=cultivo)


# Singleton
llm_client = LLMClient()
