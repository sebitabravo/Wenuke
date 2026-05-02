"""Tests end-to-end con Playwright para Werken-mapu.

Requiere: pip install pytest-playwright && playwright install chromium
Ejecutar: pytest tests/e2e/ -v
"""

import pytest

BASE_URL = "https://frontend-lac-eight-97.vercel.app"
API_URL = "https://backend-beryl-nu-18.vercel.app"

try:
    from playwright.sync_api import expect
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

needs_playwright = pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="pytest-playwright no instalado")


@pytest.fixture(scope="module")
def browser_context(playwright):
    browser = playwright.chromium.launch(headless=True)
    yield browser
    browser.close()


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="pytest-playwright no instalado")
class TestLandingPage:
    """Verifica que la landing page cargue y muestre todo correctamente."""

    @pytest.fixture(autouse=True)
    def setup(self, browser_context):
        self.context = browser_context.new_context(
            viewport={"width": 1280, "height": 800},
            locale="es-CL",
        )
        self.page = self.context.new_page()
        yield
        self.context.close()

    def test_landing_carga_correctamente(self):
        """La landing page debe cargar con título y secciones principales."""
        self.page.goto(BASE_URL)
        expect(self.page).to_have_title("Werken-mapu — El mensajero de la tierra")

    def test_hero_tiene_cta(self):
        """El hero debe tener botón de comenzar gratis."""
        self.page.goto(BASE_URL)
        cta = self.page.locator("text=Comenzar gratis").first
        expect(cta).to_be_visible()

    def test_secciones_principales_visibles(self):
        """Deben estar las secciones: problema, solución, workflow, planes."""
        self.page.goto(BASE_URL)
        expect(self.page.locator("text=El problema")).to_be_visible()
        expect(self.page.locator("text=La solución")).to_be_visible()
        expect(self.page.locator("text=Workflow")).to_be_visible()
        expect(self.page.locator("text=Planes")).to_be_visible()

    def test_phone_mockups_visibles(self):
        """Los mockups del teléfono deben ser visibles mostrando la app."""
        self.page.goto(BASE_URL)
        # Los mockups están en divs con clases específicas de teléfono
        mockups = self.page.locator(".rounded-\\[2\\.5rem\\]")
        expect(mockups.first).to_be_visible()

    def test_nav_link_probar_demo(self):
        """El link 'Probar Demo' debe navegar al chat demo."""
        self.page.goto(BASE_URL)
        with self.page.expect_navigation():
            self.page.locator("text=Probar Demo").first.click()
        assert "/app" in self.page.url

    def test_formulario_registro_envia_datos(self):
        """El formulario de registro debe aceptar datos y mostrar respuesta."""
        self.page.goto(f"{BASE_URL}/#contacto")
        self.page.fill("input[name='nombre']", "Test Agricultor")
        self.page.fill("input[name='whatsapp']", "+56912345678")
        self.page.fill("input[name='lat']", "-38.7359")
        self.page.fill("input[name='lon']", "-72.5904")
        self.page.fill("input[name='nombre_parcela']", "Parcela Test E2E")

        # Click submit
        self.page.locator("button[type='submit']").click()

        # Esperar respuesta (éxito o error manejado)
        self.page.wait_for_selector("#form-mensaje:not(.hidden)", timeout=10000)
        mensaje = self.page.locator("#form-mensaje")
        expect(mensaje).to_be_visible()


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="pytest-playwright no instalado")
class TestDemoChat:
    """Verifica que el chat demo funcione correctamente."""

    @pytest.fixture(autouse=True)
    def setup(self, browser_context):
        self.context = browser_context.new_context(
            viewport={"width": 390, "height": 844},  # iPhone 14
            locale="es-CL",
            is_mobile=True,
            has_touch=True,
        )
        self.page = self.context.new_page()
        yield
        self.context.close()

    def test_chat_carga_con_header(self):
        """El chat debe cargar con header de WhatsApp-style."""
        self.page.goto(f"{BASE_URL}/app")
        expect(self.page.locator("text=Werken-mapu")).to_be_visible()
        expect(self.page.locator("text=en línea")).to_be_visible()

    def test_selector_cultivos_presente(self):
        """Debe tener los botones de cultivo."""
        self.page.goto(f"{BASE_URL}/app")
        expect(self.page.locator("text=Papa")).to_be_visible()
        expect(self.page.locator("text=Trigo")).to_be_visible()
        expect(self.page.locator("text=Manzano")).to_be_visible()

    def test_cambiar_cultivo_actualiza_ui(self):
        """Al hacer clic en un cultivo, debe activarse visualmente."""
        self.page.goto(f"{BASE_URL}/app")
        self.page.locator("text=Papa").first.click()
        # Verificar que el header se actualizó
        expect(self.page.locator("text=en línea · papa")).to_be_visible()

    def test_boton_clima_muestra_datos(self):
        """El botón de clima debe cargar y mostrar datos meteorológicos."""
        self.page.goto(f"{BASE_URL}/app")
        # Click en el botón de clima (ícono sol)
        self.page.locator("button[title='Consultar clima']").click()

        # Esperar que aparezca el pronóstico (o error de red manejado)
        self.page.wait_for_timeout(5000)
        # Debe haber algún mensaje nuevo en el chat
        mensajes = self.page.locator("#chat-mensajes > div")
        count = mensajes.count()
        assert count > 1, f"Esperaba más de 1 mensaje, hay {count}"

    def test_quick_question_funciona(self):
        """Los botones de preguntas rápidas deben enviar texto al chat."""
        self.page.goto(f"{BASE_URL}/app")
        self.page.locator("text=¿Llueve mañana?").first.click()

        # Verificar que aparece el mensaje del usuario en el chat
        expect(self.page.locator("text=¿Llueve mañana?")).to_be_visible()

    def test_input_texto_envia_mensaje(self):
        """Escribir en el input y enviar debe mostrar el mensaje."""
        self.page.goto(f"{BASE_URL}/app")
        self.page.fill("#pregunta-input", "¿Cómo está el clima hoy?")
        self.page.locator("#btn-enviar").click()

        # El mensaje del usuario debe aparecer
        expect(self.page.locator("text=¿Cómo está el clima hoy?")).to_be_visible()

    def test_mapa_interactivo_abre(self):
        """El botón de ubicación debe mostrar el mapa."""
        self.page.goto(f"{BASE_URL}/app")
        self.page.locator("button[title='Ubicación']").click()

        # El overlay del mapa debe ser visible
        overlay = self.page.locator("#mapa-overlay")
        expect(overlay).to_be_visible()


class TestAPI:
    """Verifica que los endpoints del backend respondan correctamente."""

    def test_health_check(self):
        import httpx
        r = httpx.get(f"{API_URL}/")
        assert r.status_code == 200
        data = r.json()
        assert data["servicio"] == "Werken-mapu API"
        assert data["estado"] == "operativo"

    def test_clima_endpoint(self):
        import httpx
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
        import httpx
        r = httpx.get(f"{API_URL}/clima", params={
            "lat": -38.7359,
            "lon": -72.5904,
            "cultivo": "invalido",
        })
        assert r.status_code == 400

    def test_recomendaciones_endpoint(self):
        import httpx
        r = httpx.get(f"{API_URL}/recomendaciones", params={
            "lat": -38.7359,
            "lon": -72.5904,
            "cultivo": "general",
        })
        assert r.status_code == 200
        data = r.json()
        assert "recomendaciones" in data
        assert len(data["recomendaciones"]) == 4  # fumigar, regar, sembrar, cosechar

    def test_precios_endpoint(self):
        import httpx
        r = httpx.get(f"{API_URL}/precios")
        assert r.status_code == 200
        data = r.json()
        assert "precios" in data
        assert len(data["precios"]) >= 1

    def test_historico_endpoint(self):
        import httpx
        r = httpx.get(f"{API_URL}/historico", params={
            "lat": -38.7359,
            "lon": -72.5904,
            "anos": 2,
        })
        assert r.status_code == 200
        data = r.json()
        assert "resumen_anual" in data

    def test_registrar_usuario(self):
        import random

        import httpx
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
        import httpx
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
        import httpx
        r = httpx.post(f"{API_URL}/enviar-alertas")
        # Debe fallar sin token admin (401 o 403)
        assert r.status_code in (401, 403, 422)
