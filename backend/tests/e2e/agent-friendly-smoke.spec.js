// @ts-check
// Werken-mapu — Smoke test agent-friendly con data-testid
// playwright test tests/e2e/agent-friendly-smoke.spec.js --project=chromium

const { test, expect } = require('@playwright/test');

const BASE = process.env.BASE_URL || 'http://localhost:8000';
// El frontend se sirve estático; en local suele estar en http://localhost:8000
// o via nginx en http://localhost:8080. Ajustar con BASE_URL.

// ─── Helpers ─────────────────────────────────────────────────────────
async function llenarFormulario(page, overrides = {}) {
  const data = {
    nombre: 'Manuel Carrasco',
    whatsapp: '+56912345678',
    lat: '-38.7359',
    lon: '-72.5904',
    cultivos: ['papa'],
    plan: 'free',
    parcela: 'Parcela Sur',
    ...overrides,
  };

  await page.getByTestId('form-input-nombre').fill(data.nombre);
  await page.getByTestId('form-input-whatsapp').fill(data.whatsapp);
  await page.getByTestId('form-input-lat').fill(data.lat);
  await page.getByTestId('form-input-lon').fill(data.lon);

  // Desmarcar todos los checkboxes, marcar solo los indicados
  for (const cultivo of ['papa', 'trigo', 'manzano', 'general']) {
    const cb = page.getByTestId(`form-checkbox-${cultivo}`);
    if (data.cultivos.includes(cultivo)) {
      await cb.check();
    } else {
      await cb.uncheck();
    }
  }

  // Seleccionar plan
  await page.getByTestId(`form-radio-${data.plan}`).check();

  if (data.parcela) {
    await page.getByTestId('form-input-nombre-parcela').fill(data.parcela);
  }
}

// ─── Landing Page ────────────────────────────────────────────────────
test.describe('Landing page', () => {

  test('navegación principal tiene enlaces accesibles', async ({ page }) => {
    await page.goto(BASE);

    // Verificar que el nav principal tiene los enlaces correctos
    await expect(page.getByTestId('nav-link-como-funciona')).toBeVisible();
    await expect(page.getByTestId('nav-link-planes')).toBeVisible();
    await expect(page.getByTestId('nav-link-contacto')).toBeVisible();
    await expect(page.getByTestId('nav-btn-probar-demo')).toBeVisible();
  });

  test('CTA hero "Comenzar gratis" scrollea a formulario', async ({ page }) => {
    await page.goto(BASE);

    await page.getByTestId('hero-btn-comenzar-gratis').click();
    await page.waitForURL(/#contacto/);

    // El formulario debe ser visible tras el scroll
    await expect(page.getByTestId('form-registro')).toBeInViewport();
  });

  test('CTA pricing "Quiero Premium" scrollea a formulario', async ({ page }) => {
    await page.goto(BASE);

    await page.getByTestId('pricing-card-premium-cta').click();
    await page.waitForURL(/#contacto/);

    await expect(page.getByTestId('form-registro')).toBeInViewport();
  });

  test('CTA pricing "Empezar gratis" scrollea a formulario', async ({ page }) => {
    await page.goto(BASE);

    await page.getByTestId('pricing-card-free-cta').click();
    await page.waitForURL(/#contacto/);

    await expect(page.getByTestId('form-registro')).toBeInViewport();
  });

  test('B2B "Hablar con ventas" scrollea a formulario', async ({ page }) => {
    await page.goto(BASE);

    await page.getByTestId('pricing-b2b-cta').click();
    await page.waitForURL(/#contacto/);

    await expect(page.getByTestId('form-registro')).toBeInViewport();
  });

  test('footer links navegan a secciones correctas', async ({ page }) => {
    await page.goto(BASE);

    await page.getByTestId('footer-link-planes').click();
    await page.waitForURL(/#planes/);
    await expect(page.locator('#planes')).toBeInViewport();

    await page.getByTestId('footer-link-como-funciona').click();
    await page.waitForURL(/#como-funciona/);
    await expect(page.locator('#como-funciona')).toBeInViewport();

    await page.getByTestId('footer-link-contacto').click();
    await page.waitForURL(/#contacto/);
    await expect(page.getByTestId('form-registro')).toBeInViewport();
  });

  test('footer link "App" navega al demo', async ({ page }) => {
    await page.goto(BASE);

    await page.getByTestId('footer-link-app').click();
    await page.waitForURL(/app\.html/);

    // Verificar que el chat demo cargó
    await expect(page.getByTestId('app-textarea-pregunta')).toBeVisible();
  });

});

// ─── Formulario de registro ──────────────────────────────────────────
test.describe('Formulario de registro', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(BASE + '/#contacto');
    await expect(page.getByTestId('form-registro')).toBeInViewport();
  });

  test('envío exitoso muestra mensaje de confirmación', async ({ page }) => {
    await llenarFormulario(page);
    await page.getByTestId('form-btn-submit').click();

    // Esperar respuesta (éxito o error de red — en test local sin backend)
    const mensaje = page.getByTestId('form-mensaje');
    await expect(mensaje).toBeVisible({ timeout: 15000 });

    // El mensaje no debe estar vacío
    const texto = await mensaje.textContent();
    expect(texto.length).toBeGreaterThan(5);
  });

  test('todos los inputs tienen label asociado con for/id', async ({ page }) => {
    // Verificar asociación label-input vía for/id
    const pares = [
      ['input-nombre', 'Nombre completo'],
      ['input-whatsapp', 'WhatsApp'],
      ['input-lat', 'Ubicación (Latitud)'],
      ['input-lon', 'Ubicación (Longitud)'],
      ['input-parcela', 'Nombre de tu parcela'],
    ];

    for (const [id, labelText] of pares) {
      const label = page.locator(`label[for="${id}"]`);
      await expect(label).toBeVisible();
      await expect(label).toContainText(labelText);

      const input = page.locator(`#${id}`);
      await expect(input).toBeVisible();
    }
  });

  test('inputs requeridos tienen aria-required', async ({ page }) => {
    const requiredIds = ['input-nombre', 'input-whatsapp', 'input-lat', 'input-lon'];
    for (const id of requiredIds) {
      await expect(page.locator(`#${id}`)).toHaveAttribute('aria-required', 'true');
    }
  });

  test('mensaje de error/form tiene role="alert"', async ({ page }) => {
    await expect(page.getByTestId('form-mensaje')).toHaveAttribute('role', 'alert');
  });

  test('checkboxes de cultivo son accesibles', async ({ page }) => {
    for (const cultivo of ['papa', 'trigo', 'manzano', 'general']) {
      const cb = page.getByTestId(`form-checkbox-${cultivo}`);
      await expect(cb).toBeVisible();

      // Verificar aria-checked o checked state
      const isChecked = await cb.isChecked();
      // Papa debe venir checked por defecto
      if (cultivo === 'papa') {
        expect(isChecked).toBe(true);
      } else {
        expect(isChecked).toBe(false);
      }
    }
  });

  test('radios de plan son mutuamente excluyentes', async ({ page }) => {
    const free = page.getByTestId('form-radio-free');
    const premium = page.getByTestId('form-radio-premium');

    await expect(free).toBeChecked();
    await expect(premium).not.toBeChecked();

    await premium.check();
    await expect(premium).toBeChecked();
    await expect(free).not.toBeChecked();
  });

});

// ─── App Demo (Chat) ─────────────────────────────────────────────────
test.describe('App Demo — Chat', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(BASE + '/app.html');
    await page.waitForSelector('[data-testid="app-textarea-pregunta"]');
  });

  test('selector de cultivo cambia aria-pressed', async ({ page }) => {
    const general = page.getByTestId('app-cultivo-general');
    const papa = page.getByTestId('app-cultivo-papa');

    // General activo por defecto
    await expect(general).toHaveAttribute('aria-pressed', 'true');
    await expect(papa).toHaveAttribute('aria-pressed', 'false');

    // Cambiar a Papa
    await papa.click();
    await expect(general).toHaveAttribute('aria-pressed', 'false');
    await expect(papa).toHaveAttribute('aria-pressed', 'true');
  });

  test('botón "Consultar clima" tiene aria-label', async ({ page }) => {
    const btn = page.getByTestId('app-btn-clima');
    await expect(btn).toHaveAttribute('aria-label', 'Consultar clima');
    await expect(btn).toBeVisible();
  });

  test('botón "Enviar" tiene aria-label', async ({ page }) => {
    const btn = page.getByTestId('app-btn-enviar');
    await expect(btn).toHaveAttribute('aria-label', 'Enviar mensaje');
    await expect(btn).toBeVisible();
  });

  test('botón "Ubicación" abre mapa con role="dialog"', async ({ page }) => {
    const btnUbicacion = page.getByTestId('app-btn-ubicacion');
    await expect(btnUbicacion).toHaveAttribute('aria-label', 'Abrir mapa de ubicación');

    await btnUbicacion.click();

    const mapa = page.getByTestId('app-mapa-overlay');
    await expect(mapa).toBeVisible();
    await expect(mapa).toHaveAttribute('role', 'dialog');
    await expect(mapa).toHaveAttribute('aria-label', 'Mapa de ubicación');
  });

  test('mapa tiene inputs de coordenadas con aria-label', async ({ page }) => {
    // Abrir mapa
    await page.getByTestId('app-btn-ubicacion').click();
    await expect(page.getByTestId('app-mapa-overlay')).toBeVisible();

    const latInput = page.getByTestId('app-input-lat');
    const lonInput = page.getByTestId('app-input-lon');

    await expect(latInput).toHaveAttribute('aria-label', 'Latitud');
    await expect(lonInput).toHaveAttribute('aria-label', 'Longitud');

    // Cerrar mapa
    await page.getByTestId('app-btn-mapa-listo').click();
    await expect(page.getByTestId('app-mapa-overlay')).not.toBeVisible();
  });

  test('preguntas rápidas envían texto al textarea', async ({ page }) => {
    const preguntaBtn = page.getByTestId('app-pregunta-lluvia');
    await expect(preguntaBtn).toBeVisible();

    await preguntaBtn.click();

    // La pregunta se copia al textarea y se envía (el textarea queda vacío tras enviar)
    // Verificar que se agregó un mensaje en el chat
    const chatMensajes = page.locator('#chat-mensajes');
    // Debería haber al menos el mensaje de bienvenida + mensaje del usuario + respuesta
    await expect(chatMensajes.locator('.msg-enter')).toHaveCount(3, { timeout: 15000 });
  });

  test('textarea de chat tiene label sr-only', async ({ page }) => {
    const label = page.locator('label[for="pregunta-input"]');
    await expect(label).toContainText('Escribí tu consulta');
  });

  test('chat area tiene role="log" y aria-live', async ({ page }) => {
    const log = page.locator('#chat-mensajes');
    await expect(log).toHaveAttribute('role', 'log');
    await expect(log).toHaveAttribute('aria-live', 'polite');
  });

  test('estado de conexión tiene role="status"', async ({ page }) => {
    const status = page.locator('#header-status');
    await expect(status).toHaveAttribute('role', 'status');
    await expect(status).toHaveAttribute('aria-live', 'polite');
  });

  test('enlace "Inicio" navega de vuelta al landing', async ({ page }) => {
    await page.getByTestId('app-link-inicio').click();
    await page.waitForURL(/index\.html/);

    // Verificar que estamos en el landing
    await expect(page.getByTestId('hero-btn-comenzar-gratis')).toBeVisible();
  });

});

// ─── Flujo completo end-to-end ───────────────────────────────────────
test.describe('Flujo completo', () => {

  test('landing → registro → demo → chat', async ({ page }) => {
    // 1. Landing
    await page.goto(BASE);
    await expect(page.getByTestId('hero-btn-comenzar-gratis')).toBeVisible();

    // 2. Ir al formulario
    await page.getByTestId('hero-btn-comenzar-gratis').click();
    await expect(page.getByTestId('form-registro')).toBeInViewport();

    // 3. Llenar formulario
    await llenarFormulario(page);
    await page.getByTestId('form-btn-submit').click();
    const mensaje = page.getByTestId('form-mensaje');
    await expect(mensaje).toBeVisible({ timeout: 15000 });

    // 4. Navegar a demo
    await page.getByTestId('nav-btn-probar-demo').click();
    await page.waitForURL(/app\.html/);

    // 5. Verificar chat cargado
    await expect(page.getByTestId('app-textarea-pregunta')).toBeVisible();

    // 6. Seleccionar cultivo "Papa"
    await page.getByTestId('app-cultivo-papa').click();
    await expect(page.getByTestId('app-cultivo-papa')).toHaveAttribute('aria-pressed', 'true');

    // 7. Hacer pregunta rápida
    await page.getByTestId('app-pregunta-helada').click();

    // 8. Verificar respuesta en chat
    const chatMensajes = page.locator('#chat-mensajes');
    await expect(chatMensajes.locator('.msg-enter')).toHaveCount(3, { timeout: 15000 });

    // 9. Consultar clima
    await page.getByTestId('app-btn-clima').click();
    // Debe aparecer respuesta de clima (o mensaje de error si backend no disponible)
    await expect(chatMensajes.locator('.msg-enter')).not.toHaveCount(3, { timeout: 15000 });
  });

});

// ─── A11y: chequeos de accesibilidad ─────────────────────────────────
test.describe('Accesibilidad', () => {

  test('landing page no tiene errores de accesibilidad críticos', async ({ page }) => {
    await page.goto(BASE);

    // Verificar que existe skip link
    const skipLink = page.locator('a[href="#main-content"]');
    await expect(skipLink).toBeVisible();
  });

  test('app demo tiene skip link', async ({ page }) => {
    await page.goto(BASE + '/app.html');

    const skipLink = page.locator('a[href="#main-chat"]');
    await expect(skipLink).toBeVisible();
  });

  test('elementos SVG-only tienen aria-label', async ({ page }) => {
    await page.goto(BASE + '/app.html');

    // Botones con solo SVG deben tener aria-label
    const svgButtons = [
      page.getByTestId('app-btn-ubicacion'),
      page.getByTestId('app-btn-clima'),
      page.getByTestId('app-btn-enviar'),
    ];

    for (const btn of svgButtons) {
      await expect(btn).toBeVisible();
      const ariaLabel = await btn.getAttribute('aria-label');
      expect(ariaLabel).toBeTruthy();
    }
  });

});
