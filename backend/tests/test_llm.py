"""Tests para el cliente LLM — Groq + fallback offline."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLLMClientOffline:
    """Modo offline: sin API key de Groq."""

    @pytest.fixture
    def client_offline(self):
        import llm

        client = llm.LLMClient()
        client.api_key = ""  # Sin API key
        client.client = None  # Forzar offline
        return client

    def test_modo_offline_detectado(self, client_offline):
        assert client_offline.modo_offline is True

    def test_respuesta_offline_helada(self, client_offline):
        resp = client_offline._respuesta_offline(
            "¿Cómo protejo mis papas de la helada?", "papa"
        )
        assert "helada" in resp.lower() or "proteger" in resp.lower()
        assert len(resp) > 20

    def test_respuesta_offline_fumigar(self, client_offline):
        resp = client_offline._respuesta_offline("¿Puedo fumigar hoy?", "trigo")
        assert "fumigar" in resp.lower()
        assert len(resp) > 20

    def test_respuesta_offline_default(self, client_offline):
        resp = client_offline._respuesta_offline("Hola", "general")
        assert "werken" in resp.lower() or "compa" in resp.lower()
        assert len(resp) > 20

    def test_respuesta_offline_formatea_cultivo(self, client_offline):
        resp = client_offline._respuesta_offline("¿Cuándo siembro?", "papa")
        assert "papa" in resp.lower()

    @pytest.mark.asyncio
    async def test_preguntar_offline_retorna_flag(self, client_offline):
        resultado = await client_offline.preguntar(
            "¿Llueve mañana?", {"resumen": {}, "alertas": []}, "general"
        )
        assert resultado["offline"] is True
        assert "respuesta" in resultado

    def test_offline_respuestas_carga_json(self, client_offline):
        respuestas = client_offline.offline_respuestas
        assert "categorias" in respuestas
        assert "default" in respuestas
        assert len(respuestas["categorias"]) >= 7

    def test_hardcoded_fallback_tiene_categorias(self, client_offline):
        hard = client_offline._hardcoded_respuestas()
        assert len(hard["categorias"]) >= 7
        assert "default" in hard


class TestLLMClientOnline:
    """Modo online: Groq responde correctamente."""

    @pytest.fixture
    def mock_groq(self):
        """Mock del cliente AsyncGroq."""
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(
                message=MagicMock(
                    content="Sí compa, hoy es buen día para fumigar tus papas."
                )
            )
        ]

        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        return mock_client

    @pytest.fixture
    def client_online(self, mock_groq):
        import llm

        client = llm.LLMClient()
        client.api_key = "fake-key"
        client.client = mock_groq
        return client

    @pytest.mark.asyncio
    async def test_preguntar_online_retorna_respuesta(self, client_online):
        resultado = await client_online.preguntar(
            "¿Puedo fumigar hoy?",
            {
                "resumen": {"temp_min": 10, "temp_max": 22, "lluvia_total_24h": 0, "viento_max": 10},
                "alertas": [],
            },
            "papa",
        )
        assert resultado["offline"] is False
        assert "respuesta" in resultado

    @pytest.mark.asyncio
    async def test_preguntar_online_falla_vuelve_a_offline(self, client_online):
        client_online.client.chat.completions.create = AsyncMock(
            side_effect=Exception("Groq timeout")
        )
        resultado = await client_online.preguntar(
            "¿Llueve?",
            {"resumen": {}, "alertas": []},
            "general",
        )
        assert resultado["offline"] is True
        assert "respuesta" in resultado

    def test_formatear_contexto(self, client_online):
        contexto = {
            "resumen": {
                "temp_min": -2.1,
                "temp_max": 14.5,
                "lluvia_total_24h": 12.3,
                "viento_max": 28.4,
            },
            "alertas": [
                {
                    "tipo": "helada",
                    "mensaje": "Temperatura bajo 0°C. Riesgo de daño en brotes.",
                    "severidad": "alta",
                }
            ],
        }
        texto = client_online._formatear_contexto(contexto)
        assert "-2.1" in texto
        assert "14.5" in texto
        assert "12.3" in texto
        assert "ALERTAS ACTIVAS" in texto
