"""Cliente LLM — Groq (Llama 3.1) con fallback offline."""

from config import config


SYSTEM_PROMPT = """Eres "Wenuke", un asistente agrícola para pequeños agricultores de La Araucanía, Chile. Tu trabajo es ayudar al agricultor a tomar decisiones diarias sobre su cultivo basándote en el clima real.

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
        if self.api_key:
            try:
                from groq import AsyncGroq
                self.client = AsyncGroq(api_key=self.api_key)
            except ImportError:
                pass

    @property
    def modo_offline(self) -> bool:
        return self.client is None

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
                max_tokens=300,
                temperature=0.3,
            )
            return {
                "respuesta": response.choices[0].message.content.strip(),
                "offline": False,
            }
        except Exception:
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
        """Respuestas predefinidas cuando no hay conexión al LLM."""
        p = pregunta.lower()

        if any(w in p for w in ["helada", "hielo", "congelar", "frío", "frio", "escarcha"]):
            return (
                f"Para proteger tu {cultivo} de las heladas: riega de noche si tienes sistema, "
                f"cubre los brotes con malla antihelada o plástico, y mantén el suelo húmedo. "
                f"La tierra mojada retiene más calor que la tierra seca."
            )

        if any(w in p for w in ["lluvia", "llover", "llueve", "precipitación", "agua"]):
            return (
                f"Con lluvia fuerte no conviene fumigar porque el producto se lava. "
                f"Si ya fumigaste, revisa si pasaron al menos 4 horas antes de la lluvia. "
                f"Aprovecha de revisar los canales de drenaje de tu parcela."
            )

        if any(w in p for w in ["viento", "ventoso", "ráfaga", "ventisca"]):
            return (
                f"Con viento fuerte no fumigues: el producto se va con el viento y no protege tu cultivo. "
                f"Revisa que las estructuras de soporte estén firmes. Si tienes trigo, atención al volcado."
            )

        if any(w in p for w in ["granizo", "granizada", "granizar", "piedra"]):
            return (
                f"Con riesgo de granizo protege los cultivos sensibles con malla antigranizo si dispones. "
                f"No trabajes en la parcela durante la tormenta. Después del evento revisa daños en brotes y frutos."
            )

        if any(w in p for w in ["sembrar", "siembra", "plantar", "siembro", "semilla"]):
            return (
                f"Para decidir si sembrar {cultivo}, fijate en la temperatura del suelo y la lluvia prevista. "
                f"Lo ideal es sembrar con suelo húmedo pero sin lluvia fuerte en los 3 días siguientes. "
                f"Revisa el pronóstico en la sección de clima para decidir el mejor día."
            )

        if any(w in p for w in ["cosechar", "cosecha", "recolectar"]):
            return (
                f"Para cosechar tu {cultivo}, busca una ventana de 2-3 días sin lluvia. "
                f"La cosecha con suelo seco da mejor calidad y evita hongos. "
                f"Si viene helada, adelanta la cosecha aunque no esté 100% listo."
            )

        if any(w in p for w in ["fumigar", "fumigo", "pesticida", "plaga"]):
            return (
                f"El mejor momento para fumigar es temprano en la mañana, sin viento y sin lluvia prevista en 6 horas. "
                f"Con temperatures sobre 25°C algunos productos se evaporan y pierden efecto."
            )

        if any(w in p for w in ["regar", "riego", "agua riego"]):
            return (
                f"Revisa el pronóstico antes de regar. Si llueve en las próximas 24 horas, no gastes agua. "
                f"El mejor momento para regar es al atardecer, así el agua no se evapora con el sol."
            )

        # Default
        return (
            f"Compa, soy Wenuke, tu asistente climático. Puedo ayudarte a decidir cuándo sembrar, "
            f"fumigar, regar o cosechar tu {cultivo} según el clima. "
            f"Pregúntame cosas como: ¿llueve mañana?, ¿puedo fumigar hoy?, ¿hay riesgo de helada?"
        )


# Singleton
llm_client = LLMClient()
