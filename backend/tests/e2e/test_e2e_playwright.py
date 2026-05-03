"""Tests E2E con Playwright para Werken-mapu — frontend."""

import pytest

pytest.importorskip("pytest_playwright")

from playwright.sync_api import expect

BASE_URL = "https://frontend-lac-eight-97.vercel.app"


@pytest.fixture(scope="module")
def browser_context(playwright):
    browser = playwright.chromium.launch(headless=True)
    yield browser
    browser.close()


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
        self.page.goto(BASE_URL)
        expect(self.page).to_have_title("Werken-mapu — El mensajero de la tierra")

    def test_hero_tiene_cta(self):
        self.page.goto(BASE_URL)
        cta = self.page.locator("text=Comenzar gratis").first
        expect(cta).to_be_visible()

    def test_secciones_principales_visibles(self):
        self.page.goto(BASE_URL)
        expect(self.page.locator("text=El problema")).to_be_visible()
        expect(self.page.locator("text=La solución")).to_be_visible()
        expect(self.page.locator("text=Workflow")).to_be_visible()
        expect(self.page.locator("text=Planes")).to_be_visible()

    def test_phone_mockups_visibles(self):
        self.page.goto(BASE_URL)
        mockups = self.page.locator(".rounded-\\[2\\.5rem\\]")
        expect(mockups.first).to_be_visible()

    def test_nav_link_probar_demo(self):
        self.page.goto(BASE_URL)
        with self.page.expect_navigation():
            self.page.locator("text=Probar Demo").first.click()
        assert "/app" in self.page.url

    def test_formulario_registro_envia_datos(self):
        self.page.goto(f"{BASE_URL}/#contacto")
        self.page.fill("input[name='nombre']", "Test Agricultor")
        self.page.fill("input[name='whatsapp']", "+56912345678")
        self.page.fill("input[name='lat']", "-38.7359")
        self.page.fill("input[name='lon']", "-72.5904")
        self.page.fill("input[name='nombre_parcela']", "Parcela Test E2E")
        self.page.locator("button[type='submit']").click()
        self.page.wait_for_selector("#form-mensaje:not(.hidden)", timeout=10000)
        mensaje = self.page.locator("#form-mensaje")
        expect(mensaje).to_be_visible()


class TestDemoChat:
    """Verifica que el chat demo funcione correctamente."""

    @pytest.fixture(autouse=True)
    def setup(self, browser_context):
        self.context = browser_context.new_context(
            viewport={"width": 390, "height": 844},
            locale="es-CL",
            is_mobile=True,
            has_touch=True,
        )
        self.page = self.context.new_page()
        yield
        self.context.close()

    def test_chat_carga_con_header(self):
        self.page.goto(f"{BASE_URL}/app")
        expect(self.page.locator("text=Werken-mapu")).to_be_visible()
        expect(self.page.locator("text=en línea")).to_be_visible()

    def test_selector_cultivos_presente(self):
        self.page.goto(f"{BASE_URL}/app")
        expect(self.page.locator("text=Papa")).to_be_visible()
        expect(self.page.locator("text=Trigo")).to_be_visible()
        expect(self.page.locator("text=Manzano")).to_be_visible()

    def test_cambiar_cultivo_actualiza_ui(self):
        self.page.goto(f"{BASE_URL}/app")
        self.page.locator("text=Papa").first.click()
        expect(self.page.locator("text=en línea · papa")).to_be_visible()

    def test_boton_clima_muestra_datos(self):
        self.page.goto(f"{BASE_URL}/app")
        self.page.locator("button[title='Consultar clima']").click()
        self.page.wait_for_timeout(5000)
        mensajes = self.page.locator("#chat-mensajes > div")
        count = mensajes.count()
        assert count > 1, f"Esperaba más de 1 mensaje, hay {count}"

    def test_quick_question_funciona(self):
        self.page.goto(f"{BASE_URL}/app")
        self.page.locator("text=¿Llueve mañana?").first.click()
        expect(self.page.locator("text=¿Llueve mañana?")).to_be_visible()

    def test_input_texto_envia_mensaje(self):
        self.page.goto(f"{BASE_URL}/app")
        self.page.fill("#pregunta-input", "¿Cómo está el clima hoy?")
        self.page.locator("#btn-enviar").click()
        expect(self.page.locator("text=¿Cómo está el clima hoy?")).to_be_visible()

    def test_mapa_interactivo_abre(self):
        self.page.goto(f"{BASE_URL}/app")
        self.page.locator("button[title='Ubicación']").click()
        overlay = self.page.locator("#mapa-overlay")
        expect(overlay).to_be_visible()
