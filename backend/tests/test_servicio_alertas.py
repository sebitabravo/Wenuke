"""Tests para el servicio de alertas — mockea clima y WhatsApp."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from whatsapp import WhatsAppClient  # noqa: E402


class TestEjecutarChequeoAlertas:
    """Verifica el flujo completo: clima → reglas → DB → WhatsApp."""

    @pytest.fixture
    def mock_resultado_reglas(self):
        return {
            "cultivo": "Papa",
            "alertas": [
                {
                    "tipo": "helada",
                    "mensaje": "ALERTA DE HELADA: -1.5°C",
                    "severidad": "media",
                    "dia": "2026-05-01",
                    "hora": "03:00",
                }
            ],
        }

    @pytest.fixture
    def mock_usuarios(self):
        return [
            {
                "id": 1,
                "nombre": "Juan Papero",
                "whatsapp": "+56911111111",
                "lat": -38.7,
                "lon": -72.6,
                "parcela_id": 1,
            },
            {
                "id": 2,
                "nombre": "Maria Papera",
                "whatsapp": "+56922222222",
                "lat": -38.7,
                "lon": -72.6,
                "parcela_id": 2,
            },
        ]

    @pytest.mark.asyncio
    async def test_envia_alertas_a_usuarios_con_cultivo(
        self, mock_resultado_reglas, mock_usuarios
    ):
        with (
            patch(
                "servicio_alertas.obtener_usuarios_con_cultivo",
                AsyncMock(return_value=mock_usuarios),
            ),
            patch(
                "servicio_alertas.evaluar_reglas",
                return_value=mock_resultado_reglas,
            ),
            patch(
                "servicio_alertas.registrar_alerta",
                AsyncMock(),
            ),
            patch(
                "servicio_alertas.clima_client.fetch_forecast",
                AsyncMock(return_value={"mock": True}),
            ),
            patch(
                "servicio_alertas.clima_client.parse_hourly",
                return_value=[],
            ),
            patch.object(
                WhatsAppClient, "activo", PropertyMock(return_value=True)
            ),
            patch.object(
                WhatsAppClient, "enviar_plantilla_alerta",
                AsyncMock(return_value={"enviado": True}),
            ),
        ):
            from servicio_alertas import ejecutar_chequeo_alertas

            resultado = await ejecutar_chequeo_alertas()

        assert resultado["usuarios_afectados"] >= 1
        assert resultado["enviadas"] >= 1
        assert resultado["envios_fallidos"] == 0
        assert resultado["whatsapp_activo"] is True

    @pytest.mark.asyncio
    async def test_sin_usuarios_retorna_vacio(self):
        with patch(
            "servicio_alertas.obtener_usuarios_con_cultivo",
            AsyncMock(return_value=[]),
        ):
            from servicio_alertas import ejecutar_chequeo_alertas

            resultado = await ejecutar_chequeo_alertas()

        assert resultado["enviadas"] == 0
        assert resultado["usuarios_afectados"] == 0
        assert len(resultado["detalle"]) == 0

    @pytest.mark.asyncio
    async def test_sin_alertas_no_envia_whatsapp(self, mock_usuarios):
        """Si no hay alertas climáticas, no se envía WhatsApp."""
        resultado_sin_alertas = {"cultivo": "Papa", "alertas": []}

        with (
            patch(
                "servicio_alertas.obtener_usuarios_con_cultivo",
                AsyncMock(return_value=mock_usuarios),
            ),
            patch(
                "servicio_alertas.evaluar_reglas",
                return_value=resultado_sin_alertas,
            ),
            patch("servicio_alertas.registrar_alerta", AsyncMock()),
            patch(
                "servicio_alertas.clima_client.fetch_forecast",
                AsyncMock(return_value={"mock": True}),
            ),
            patch(
                "servicio_alertas.clima_client.parse_hourly",
                return_value=[],
            ),
            patch.object(
                WhatsAppClient, "activo", PropertyMock(return_value=True)
            ),
        ):
            from servicio_alertas import ejecutar_chequeo_alertas

            resultado = await ejecutar_chequeo_alertas()

        assert resultado["enviadas"] == 0
        assert resultado["usuarios_afectados"] == 0

    @pytest.mark.asyncio
    async def test_whatsapp_fallo_se_cuenta(self, mock_resultado_reglas, mock_usuarios):
        with (
            patch(
                "servicio_alertas.obtener_usuarios_con_cultivo",
                AsyncMock(return_value=mock_usuarios),
            ),
            patch(
                "servicio_alertas.evaluar_reglas",
                return_value=mock_resultado_reglas,
            ),
            patch("servicio_alertas.registrar_alerta", AsyncMock()),
            patch(
                "servicio_alertas.clima_client.fetch_forecast",
                AsyncMock(return_value={"mock": True}),
            ),
            patch(
                "servicio_alertas.clima_client.parse_hourly",
                return_value=[],
            ),
            patch.object(
                WhatsAppClient, "activo", PropertyMock(return_value=True)
            ),
            patch.object(
                WhatsAppClient, "enviar_plantilla_alerta",
                AsyncMock(return_value={"enviado": False, "error": "timeout"}),
            ),
        ):
            from servicio_alertas import ejecutar_chequeo_alertas

            resultado = await ejecutar_chequeo_alertas()

        assert resultado["envios_fallidos"] >= 1

    @pytest.mark.asyncio
    async def test_whatsapp_no_configurado_no_envia(self, mock_resultado_reglas, mock_usuarios):
        with (
            patch(
                "servicio_alertas.obtener_usuarios_con_cultivo",
                AsyncMock(return_value=mock_usuarios),
            ),
            patch(
                "servicio_alertas.evaluar_reglas",
                return_value=mock_resultado_reglas,
            ),
            patch("servicio_alertas.registrar_alerta", AsyncMock()),
            patch(
                "servicio_alertas.clima_client.fetch_forecast",
                AsyncMock(return_value={"mock": True}),
            ),
            patch(
                "servicio_alertas.clima_client.parse_hourly",
                return_value=[],
            ),
            patch.object(
                WhatsAppClient, "activo", PropertyMock(return_value=False)
            ),
        ):
            from servicio_alertas import ejecutar_chequeo_alertas

            resultado = await ejecutar_chequeo_alertas()

        assert resultado["whatsapp_activo"] is False
        # Se registra la alerta en DB aunque no se envíe WhatsApp
        assert resultado["usuarios_afectados"] >= 1

    @pytest.mark.asyncio
    async def test_clima_falla_no_interrumpe_otros_cultivos(self, mock_usuarios):
        """Si OpenMeteo falla para un cultivo, sigue con los otros."""
        call_count = 0

        async def _fetch_forecast_fallida_primer_intento(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("OpenMeteo timeout")
            return {"mock": True}

        with (
            patch(
                "servicio_alertas.obtener_usuarios_con_cultivo",
                AsyncMock(
                    side_effect=[
                        mock_usuarios,  # papa → falla clima
                        [],              # trigo
                        [],              # manzano (sin usuarios)
                    ]
                ),
            ),
            patch("servicio_alertas.registrar_alerta", AsyncMock()),
            patch(
                "servicio_alertas.clima_client.fetch_forecast",
                _fetch_forecast_fallida_primer_intento,
            ),
            patch(
                "servicio_alertas.clima_client.parse_hourly",
                return_value=[],
            ),
            patch.object(
                WhatsAppClient, "activo", PropertyMock(return_value=False)
            ),
        ):
            from servicio_alertas import ejecutar_chequeo_alertas

            resultado = await ejecutar_chequeo_alertas()

        # No debe crashear, debe retornar métricas
        assert resultado["enviadas"] == 0

    @pytest.mark.asyncio
    async def test_ubicaciones_repetidas_comparten_cache(self):
        """Usuarios en misma ubicación comparten resultado de clima."""
        usuarios_misma_ubicacion = [
            {"id": 1, "nombre": "U1", "whatsapp": "+5691", "lat": -38.70, "lon": -72.60, "parcela_id": 1},
            {"id": 2, "nombre": "U2", "whatsapp": "+5692", "lat": -38.70, "lon": -72.60, "parcela_id": 2},
        ]

        fetch_count = 0

        async def _contar_fetch(*args, **kwargs):
            nonlocal fetch_count
            fetch_count += 1
            return {"mock": True}

        with (
            patch(
                "servicio_alertas.obtener_usuarios_con_cultivo",
                AsyncMock(return_value=usuarios_misma_ubicacion),
            ),
            patch(
                "servicio_alertas.evaluar_reglas",
                return_value={"cultivo": "Papa", "alertas": []},
            ),
            patch("servicio_alertas.registrar_alerta", AsyncMock()),
            patch(
                "servicio_alertas.clima_client.fetch_forecast", _contar_fetch,
            ),
            patch(
                "servicio_alertas.clima_client.parse_hourly", return_value=[],
            ),
            patch.object(
                WhatsAppClient, "activo", PropertyMock(return_value=False)
            ),
        ):
            from servicio_alertas import ejecutar_chequeo_alertas

            await ejecutar_chequeo_alertas()

        # fetch_forecast se llama 1 vez por cultivo (3 cultivos) aunque
        # los 2 usuarios compartan ubicación. El cache es intra-cultivo.
        from constants import CULTIVOS_PRODUCTIVOS
        assert fetch_count == len(CULTIVOS_PRODUCTIVOS)
