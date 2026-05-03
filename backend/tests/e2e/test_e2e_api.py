"""Tests E2E de API para Werken-mapu — no requieren Playwright."""

import random

import httpx

API_URL = "https://backend-beryl-nu-18.vercel.app"


class TestAPI:
    """Verifica que los endpoints del backend respondan correctamente."""

    def test_health_check(self):
        r = httpx.get(f"{API_URL}/")
        assert r.status_code == 200
        data = r.json()
        assert data["servicio"] == "Werken-mapu API"
        assert data["estado"] == "operativo"

    def test_clima_endpoint(self):
        r = httpx.get(f"{API_URL}/clima", params={
            "lat": -38.7359,
            "lon": -72.5904,
            "cultivo": "papa",
        })
        assert r.status_code == 200
        data = r.json()
        assert "alertas" in data
        assert "resumen" in data
        assert data["cultivo"] == "Papa"

    def test_clima_validation_bad_cultivo(self):
        r = httpx.get(f"{API_URL}/clima", params={
            "lat": -38.7359,
            "lon": -72.5904,
            "cultivo": "invalido",
        })
        assert r.status_code == 400

    def test_recomendaciones_endpoint(self):
        r = httpx.get(f"{API_URL}/recomendaciones", params={
            "lat": -38.7359,
            "lon": -72.5904,
            "cultivo": "general",
        })
        assert r.status_code == 200
        data = r.json()
        assert "recomendaciones" in data
        assert len(data["recomendaciones"]) == 4

    def test_precios_endpoint(self):
        r = httpx.get(f"{API_URL}/precios")
        assert r.status_code == 200
        data = r.json()
        assert "precios" in data
        assert len(data["precios"]) >= 1

    def test_historico_endpoint(self):
        r = httpx.get(f"{API_URL}/historico", params={
            "lat": -38.7359,
            "lon": -72.5904,
            "anos": 2,
        })
        assert r.status_code == 200
        data = r.json()
        assert "resumen_anual" in data

    def test_registrar_usuario(self):
        r = httpx.post(f"{API_URL}/registrar", json={
            "whatsapp": f"+569{random.randint(10000000, 99999999)}",
            "nombre": "Test E2E",
            "lat": -38.7359,
            "lon": -72.5904,
            "cultivos": ["general"],
            "plan": "free",
            "nombre_parcela": "Parcela Test",
        })
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert "parcela_id" in data

    def test_preguntar_endpoint(self):
        r = httpx.post(f"{API_URL}/preguntar", json={
            "pregunta": "¿Llueve mañana en Temuco?",
            "lat": -38.7359,
            "lon": -72.5904,
            "cultivo": "general",
        })
        assert r.status_code == 200
        data = r.json()
        assert "respuesta" in data

    def test_enviar_alertas_sin_token(self):
        r = httpx.post(f"{API_URL}/enviar-alertas")
        assert r.status_code in (401, 403, 422)
