// ─── Werken-mapu — Lógica del frontend ───────────────────────────────
// Asistente climático para pequeños agricultores de La Araucanía

const API = window.API_BASE || 'http://localhost:8000';

const state = {
  lat: -38.7359,
  lon: -72.5904,
  cultivo: 'general',
  online: navigator.onLine,
};

// ─── Inicialización ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initMap();
  initEvents();
  initOffline();
  updateStatus();
});

// ─── Mapa ────────────────────────────────────────────────────────
let map, marker;

function initMap() {
  map = L.map('mapa', { attributionControl: false }).setView([state.lat, state.lon], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 }).addTo(map);
  marker = L.marker([state.lat, state.lon], { draggable: true }).addTo(map);

  map.on('click', e => setCoords(e.latlng.lat, e.latlng.lng));
  marker.on('dragend', () => {
    const p = marker.getLatLng();
    setCoords(p.lat, p.lng);
  });
  updateCoordInputs();
}

function setCoords(lat, lon) {
  state.lat = +lat.toFixed(4);
  state.lon = +lon.toFixed(4);
  marker.setLatLng([state.lat, state.lon]);
  updateCoordInputs();
  updateStatus();
}

function updateCoordInputs() {
  const le = id => document.getElementById(id);
  le('lat-input').value = state.lat;
  le('lon-input').value = state.lon;
  le('lat-display').textContent = state.lat.toFixed(2);
  le('lon-display').textContent = state.lon.toFixed(2);
}

function toggleMapa() {
  const overlay = document.getElementById('mapa-overlay');
  overlay.classList.toggle('hidden');
  if (!overlay.classList.contains('hidden')) {
    setTimeout(() => map.invalidateSize(), 150);
  }
}

// ─── Eventos ─────────────────────────────────────────────────────
function initEvents() {
  document.getElementById('btn-enviar').addEventListener('click', enviarPregunta);
  document.getElementById('pregunta-input').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviarPregunta(); }
  });
  document.getElementById('lat-input').addEventListener('change', onCoordInputChange);
  document.getElementById('lon-input').addEventListener('change', onCoordInputChange);

  document.querySelectorAll('.cultivo-btn').forEach(btn => {
    btn.addEventListener('click', () => selectCrop(btn.dataset.cultivo));
  });

  // Auto-grow textarea
  const ta = document.getElementById('pregunta-input');
  ta.addEventListener('input', () => {
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 96) + 'px';
  });
}

function onCoordInputChange() {
  const lat = +document.getElementById('lat-input').value;
  const lon = +document.getElementById('lon-input').value;
  if (!isNaN(lat) && !isNaN(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
    setCoords(lat, lon);
    map.setView([state.lat, state.lon], 13);
  }
}

// Clases base para botones de cultivo — se definen en HTML, no en JS.
// JS solo alterna la clase cultivo-active via classList.
const CULTIVO_ACTIVE_CLS = [
  'bg-wa-medium', 'text-white',
];
const CULTIVO_INACTIVE_CLS = [
  'bg-white', 'text-gray-600', 'border', 'border-gray-200',
  'hover:border-wa-light', 'hover:text-wa-medium',
];

function selectCrop(cultivo) {
  state.cultivo = cultivo;
  document.querySelectorAll('.cultivo-btn').forEach(b => {
    const sel = b.dataset.cultivo === cultivo;
    b.setAttribute('aria-pressed', sel ? 'true' : 'false');
    if (sel) {
      b.classList.add('cultivo-active', ...CULTIVO_ACTIVE_CLS);
      b.classList.remove(...CULTIVO_INACTIVE_CLS);
    } else {
      b.classList.remove('cultivo-active', ...CULTIVO_ACTIVE_CLS);
      b.classList.add(...CULTIVO_INACTIVE_CLS);
    }
  });
  updateStatus();
}

// ─── Offline ─────────────────────────────────────────────────────
function initOffline() {
  window.addEventListener('online', () => { state.online = true; updateStatus(); });
  window.addEventListener('offline', () => { state.online = false; updateStatus(); });
}

function updateStatus() {
  const dot = document.getElementById('status-dot');
  const txt = document.getElementById('header-status');
  if (state.online) {
    dot.classList.remove('bg-red-400');
    dot.classList.add('bg-green-300');
    txt.textContent = `en línea · ${state.cultivo} · ${state.lat.toFixed(1)}°,${state.lon.toFixed(1)}°`;
  } else {
    dot.classList.remove('bg-green-300');
    dot.classList.add('bg-red-400');
    txt.textContent = 'sin conexión';
  }
}

// ─── API ─────────────────────────────────────────────────────────
async function consultarClima() {
  showTyping();
  try {
    const r = await fetch(`${API}/clima?lat=${state.lat}&lon=${state.lon}&cultivo=${state.cultivo}`);
    if (!r.ok) throw r;
    const data = await r.json();
    hideTyping();
    renderClima(data);
  } catch {
    hideTyping();
    addMsg('bot', 'No pude consultar el clima ahora. ¿Tenés conexión a internet? Intentá de nuevo.');
  }
}

async function enviarPregunta() {
  const input = document.getElementById('pregunta-input');
  const text = input.value.trim();
  if (!text) return;

  addMsg('user', text);
  input.value = '';
  input.style.height = 'auto';
  showTyping();

  try {
    const r = await fetch(`${API}/preguntar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pregunta: text, lat: state.lat, lon: state.lon, cultivo: state.cultivo }),
    });
    if (!r.ok) throw r;
    const data = await r.json();
    hideTyping();
    let resp = data.respuesta;
    if (data.offline) resp += '\n\n_📵 Respuesta sin conexión al asistente._';
    addMsg('bot', resp);
  } catch {
    hideTyping();
    addMsg('bot', offlineFallback(text));
  }
}

function enviarEjemplo(texto) {
  document.getElementById('pregunta-input').value = texto;
  enviarPregunta();
}

// ─── Renderizado ─────────────────────────────────────────────────
// User text only via textContent — no innerHTML para datos de usuario (XSS)

function _el(tag, cls, attrs) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (attrs) Object.entries(attrs).forEach(([k, v]) => { if (v != null) e[k] = v; });
  return e;
}

function _safeText(el, text) {
  // Usa textContent para datos de usuario — inmune a XSS
  el.textContent = text;
}

function _safeHTML(el, html) {
  // Solo para HTML estructural sin datos de usuario (íconos, badges)
  el.insertAdjacentHTML('beforeend', html);
}

function addMsg(type, text) {
  const chat = document.getElementById('chat-mensajes');
  const row = _el('div', 'msg-enter flex mb-2 ' + (type === 'user' ? 'justify-end' : 'gap-2'));

  if (type === 'user') {
    const bubble = _el('div', 'bg-[#d9fdd3] rounded-lg rounded-br-none px-4 py-2.5 max-w-[80%] shadow-sm');
    const p = _el('p', 'text-sm text-gray-800 whitespace-pre-wrap');
    _safeText(p, text);
    const ts = _el('span', 'text-[10px] text-gray-500 float-right ml-4 mt-1');
    _safeText(ts, now());
    bubble.append(p, ts);
    row.append(bubble);
  } else {
    const avatar = _el('div', 'flex-shrink-0 w-7 h-7 bg-wa-medium rounded-full flex items-center justify-center text-xs shadow-sm');
    _safeText(avatar, '🌱');
    const bubble = _el('div', 'bg-white rounded-lg rounded-bl-none px-4 py-2.5 max-w-[80%] shadow-sm border border-gray-100');
    const p = _el('p', 'text-sm text-gray-800 whitespace-pre-wrap');
    // fmt() aplica esc() primero, luego parsea **bold** → HTML seguro
    _safeHTML(p, fmt(text));
    const ts = _el('span', 'text-[10px] text-gray-500 block mt-1');
    _safeText(ts, now());
    bubble.append(p, ts);
    row.append(avatar, bubble);
  }

  chat.appendChild(row);
  scrollDown();
}

function addAlertCard(alerta) {
  const chat = document.getElementById('chat-mensajes');
  const row = _el('div', 'msg-enter flex gap-2 mb-2');

  const COLORS = {
    helada: { border: 'border-l-blue-500', bg: 'bg-blue-50', icon: '❄️', label: 'Helada' },
    lluvia_intensa: { border: 'border-l-cyan-500', bg: 'bg-cyan-50', icon: '🌧️', label: 'Lluvia intensa' },
    viento_fuerte: { border: 'border-l-orange-500', bg: 'bg-orange-50', icon: '💨', label: 'Viento fuerte' },
    granizo: { border: 'border-l-purple-500', bg: 'bg-purple-50', icon: '🌨️', label: 'Granizo' },
  };
  const BADGES = {
    alta: 'URGENTE',
    media: 'Precaución',
    baja: 'Aviso',
  };
  const c = COLORS[alerta.tipo] || { border: 'border-l-gray-400', bg: 'bg-gray-50', icon: '⚠️', label: 'Alerta' };
  const badgeText = BADGES[alerta.severidad] || BADGES.media;
  const badgeCls = {
    alta: 'bg-red-500',
    media: 'bg-amber-500',
    baja: 'bg-green-500',
  };
  const bc = badgeCls[alerta.severidad] || 'bg-amber-500';

  // Avatar (sin user data)
  const avatar = _el('div', 'flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs shadow-sm ' + c.bg);
  _safeText(avatar, c.icon);

  // Card
  const card = _el('div', 'bg-white border-l-4 ' + c.border + ' ' + c.bg + ' rounded-r-lg px-4 py-3 max-w-[80%] shadow-sm');

  // Header row: label, badge, date
  const header = _el('div', 'flex items-center gap-2 mb-1.5');
  const labelEl = _el('span', 'text-[11px] font-bold uppercase text-gray-500');
  _safeText(labelEl, c.label);

  const badgeEl = _el('span', 'text-white text-[10px] px-2 py-0.5 rounded-full font-semibold ' + bc);
  _safeText(badgeEl, badgeText);

  const dateEl = _el('span', 'text-[10px] text-gray-400');
  _safeText(dateEl, alerta.dia || '');

  header.append(labelEl, badgeEl, dateEl);

  // Message body (user data → textContent)
  const msgEl = _el('p', 'text-sm text-gray-800 whitespace-pre-wrap');
  _safeText(msgEl, alerta.mensaje);

  card.append(header, msgEl);
  row.append(avatar, card);
  chat.appendChild(row);
  scrollDown();
}

function showTyping() {
  const chat = document.getElementById('chat-mensajes');
  const div = document.createElement('div');
  div.id = 'typing';
  div.className = 'msg-enter flex gap-2 mb-2';
  div.innerHTML = `<div class="flex-shrink-0 w-7 h-7 bg-wa-medium rounded-full flex items-center justify-center text-xs shadow-sm">🌱</div><div class="bg-white rounded-lg rounded-bl-none px-4 py-3 shadow-sm border border-gray-100"><div class="flex gap-1"><div class="w-2 h-2 bg-gray-400 rounded-full pulse-dot"></div><div class="w-2 h-2 bg-gray-400 rounded-full pulse-dot"></div><div class="w-2 h-2 bg-gray-400 rounded-full pulse-dot"></div></div></div>`;
  chat.appendChild(div);
  scrollDown();
}

function hideTyping() {
  const el = document.getElementById('typing');
  if (el) el.remove();
}

function renderClima(data) {
  const { alertas, resumen, cultivo } = data;
  let txt = `🌤️ **Pronóstico para ${cultivo || state.cultivo}**\n`;
  if (resumen) {
    txt += `📊 ${resumen.temp_min ?? '?'}°C – ${resumen.temp_max ?? '?'}°C  ·  💧 ${resumen.lluvia_total_24h != null ? resumen.lluvia_total_24h.toFixed(1) : '?'} mm  ·  💨 ${resumen.viento_max ?? '?'} km/h\n`;
    txt += `📅 Próximos ${resumen.dias_forecast ?? '?'} días`;
  }
  addMsg('bot', txt);

  if (!alertas || alertas.length === 0) {
    addMsg('bot', '✅ Sin alertas para tu cultivo. ¡Todo tranquilo por ahora!');
  } else {
    alertas.forEach(addAlertCard);
  }
}

// ─── Utilidades ──────────────────────────────────────────────────
function scrollDown() {
  const el = document.getElementById('main-chat');
  requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
}

function esc(t) {
  const d = document.createElement('div');
  d.textContent = t;
  return d.innerHTML;
}

function fmt(t) {
  return esc(t).replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>').replace(/\n/g, '<br>');
}

function now() {
  return new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
}

function id(s) { return document.getElementById(s); }

// Fallback offline de último recurso — solo se usa si el backend es inalcanzable.
// La fuente de verdad primaria es llm.py:_hardcoded_respuestas() + respuestas_offline.json.
// Este bloque existe para que la UI no quede en blanco sin conectividad alguna.
function offlineFallback(p) {
  const q = p.toLowerCase();
  let r = 'Compa, no tengo conexión al asistente. Probá con el botón de clima ☀️ o intentá de nuevo más tarde.\n\n📵 _Respuesta offline._';
  if (/helada|fr[ií]o|escarcha|hielo/i.test(q)) r = '🌡️ Para heladas: regá de noche si tenés riego. La tierra mojada libera calor y protege. Cubrí brotes con malla o plástico.\n\n📵 _Offline._';
  else if (/lluvia|llover|llueve/i.test(q)) r = '🌧️ Con lluvia no fumigues — el producto se lava. Revisá drenajes. Si ya fumigaste, necesitás 4h sin lluvia.\n\n📵 _Offline._';
  else if (/viento/i.test(q)) r = '💨 Con viento fuerte no fumigues. Revisá estructuras. Si tenés trigo, ojo con el volcado.\n\n📵 _Offline._';
  else if (/granizo|granizada|granizar/i.test(q)) r = '🌨️ Con riesgo de granizo protegé los cultivos sensibles con malla. No trabajes en la parcela durante la tormenta. Después del evento revisá daños en brotes y frutos.\n\n📵 _Offline._';
  else if (/fumigar|pesticida/i.test(q)) r = '🧪 Fumigá temprano, sin viento, sin lluvia en 6h. Sobre 25°C el producto pierde efecto.\n\n📵 _Offline._';
  else if (/sembrar|siembra/i.test(q)) r = '🌱 Sembrá con suelo húmedo pero sin lluvia fuerte los 3 días siguientes. Revisá el clima.\n\n📵 _Offline._';
  else if (/cosechar|cosecha/i.test(q)) r = '🌽 Cosechá en ventana de 2-3 días secos. Si viene helada, adelantá aunque no esté 100% listo.\n\n📵 _Offline._';
  return r;
}
