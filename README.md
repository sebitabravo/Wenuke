# Werken-mapu — El mensajero de la tierra

> Asistente climático agrícola por WhatsApp para pequeños agricultores de La Araucanía, Chile.
> Alertas anticipadas 48–72h, recomendaciones diarias y asistente IA conversacional. Sin apps, sin sensores, sin complicaciones.

[![Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://frontend-lac-eight-97.vercel.app)
[![API](https://img.shields.io/badge/API-live-blue)](https://backend-beryl-nu-18.vercel.app)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

---

## El problema

Los pequeños agricultores de La Araucanía pierden hasta el **30% de su producción anual** por decisiones basadas en pronósticos climáticos diseñados para cientos de kilómetros, no para su parcela.

- ❄️ Una helada sin aviso arruina meses de trabajo en una noche
- 🌧️ Una lluvia no prevista lava la fumigación del día anterior
- 🌾 Un día seco no aprovechado retrasa la siembra semanas

## La solución

Werken-mapu ("mensajero de la tierra" en mapudungún) llega donde el agricultor ya está: en su teléfono, por **WhatsApp**, sin necesidad de descargar nada.

```
Agricultor escribe → comparte ubicación → elige cultivos → recibe alertas y recomendaciones
```

## Demo en vivo

| Entorno | URL |
|---|---|
| **Landing page** | [frontend-lac-eight-97.vercel.app](https://frontend-lac-eight-97.vercel.app) |
| **Demo chat** | [frontend-lac-eight-97.vercel.app/app](https://frontend-lac-eight-97.vercel.app/app) |
| **API** | [backend-beryl-nu-18.vercel.app](https://backend-beryl-nu-18.vercel.app) |

## Arquitectura

```
┌─────────────────────────────────────────────────┐
│              Frontend (Vercel Static)             │
│  landing (index.html) ←→ demo chat (app.html)    │
│  Tailwind CSS • Vanilla JS • Leaflet Maps        │
└─────────────────┬───────────────────────────────┘
                  │ HTTPS
┌─────────────────▼───────────────────────────────┐
│            Backend (Vercel Serverless)            │
│  FastAPI • Python 3.12 • SQLite                  │
│  ┌──────────┬──────────┬──────────┬───────────┐  │
│  │ OpenMeteo│  Groq    │  ODEPA   │ WhatsApp  │  │
│  │ (gratis) │ (Llama)  │ (precios)│ Business  │  │
│  └──────────┴──────────┴──────────┴───────────┘  │
└─────────────────────────────────────────────────┘
```

## Stack tecnológico

| Capa | Tecnología | Justificación |
|---|---|---|
| Frontend | HTML5 + Tailwind CSS + Vanilla JS | Cero dependencias, carga instantánea |
| Backend | FastAPI (Python 3.12) | Alto rendimiento, tipado fuerte, async nativo |
| Base de datos | SQLite (WAL mode) | Self-hosted, $0, sin infraestructura externa |
| Clima | OpenMeteo API | Gratis, sin API key, cobertura completa Chile |
| IA | Groq (Llama 3.1 70B) | $0.59/M tokens, latencia baja, fallback offline |
| Precios | ODEPA (scraping + referencia) | Datos públicos de mercado mayorista chileno |
| Mapas | Leaflet + OpenStreetMap | Open source, sin API key |
| Deploy | Vercel | Static + Serverless, HTTPS, CDN global |

**Costo operativo: ~$10 USD/mes** (vs $200 USD con APIs comerciales).

## Features

### Plan Libre — $0 para siempre
- ✅ Alertas de helada, lluvia intensa, viento fuerte y granizo
- ✅ Pronóstico 7 días por ubicación GPS
- ✅ 1 parcela
- ✅ Acceso por WhatsApp y web

### Plan Premium — $3.000 CLP/mes
- ✅ Todo lo del plan libre
- ✅ Hasta 10 parcelas
- ✅ Alertas personalizadas por cultivo (papa, trigo, manzano)
- ✅ Asistente IA conversacional 24/7
- ✅ Recomendaciones diarias: fumigar, regar, sembrar, cosechar
- ✅ Análisis de precios de mercado (ODEPA)
- ✅ Historial climático 5–10 años
- ✅ Calendario de rotación de cultivos

### B2B — PRODESAL / Cooperativas
- Paquetes para 100–500 agricultores afiliados
- $1.500 CLP/mes por agricultor
- Administración centralizada, reportes de uso

## API endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/clima` | Pronóstico + alertas por cultivo y ubicación |
| `POST` | `/preguntar` | Asistente conversacional con IA |
| `GET` | `/recomendaciones` | Recomendaciones diarias accionables |
| `GET` | `/historico` | Datos climáticos históricos 1–10 años |
| `GET` | `/precios` | Precios mayoristas ODEPA |
| `POST` | `/registrar` | Alta de agricultor (retorna token) |
| `GET` | `/parcelas` | Listar parcelas del usuario |
| `POST` | `/parcelas` | Agregar parcela nueva |
| `DELETE` | `/parcelas/{id}` | Eliminar parcela |
| `GET` | `/plan` | Ver plan actual |
| `POST` | `/plan` | Cambiar plan (free ↔ premium) |
| `POST` | `/enviar-alertas` | Dispatch manual de alertas (WhatsApp) |

## Estructura del proyecto

```
Wenuke/
├── frontend/                 # Static (Vercel)
│   ├── index.html            # Landing page
│   ├── app.html              # Demo chat (WhatsApp-style)
│   ├── app.js                # Lógica del chat
│   └── vercel.json
├── backend/                  # Serverless Python (Vercel Functions)
│   ├── main.py               # FastAPI — 17 endpoints
│   ├── models.py             # Schemas Pydantic v2
│   ├── reglas.py             # Motor de reglas por cultivo (dominio puro)
│   ├── clima.py              # Cliente OpenMeteo + cache + histórico
│   ├── llm.py                # Cliente Groq + fallback offline
│   ├── odepa.py              # Scraping precios ODEPA
│   ├── whatsapp.py           # WhatsApp Business Cloud API
│   ├── scheduler.py          # Scheduler de alertas cada 6h
│   ├── db.py                 # SQLite CRUD + multi-parcela + planes
│   ├── config.py             # Configuración desde env vars
│   ├── requirements.txt
│   └── vercel.json
├── docs/
│   ├── pitch.pdf             # Deck de presentación
│   └── pitch-2.pdf           # Deck complementario
├── DESIGN.md                 # Design system (Stitch/awesome-design-md)
├── vercel.json               # Root config monorepo
└── README.md
```

## Diseño

El sistema de diseño está documentado en [DESIGN.md](./DESIGN.md) siguiendo el estándar [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) (Google Stitch).

**Paleta WhatsApp-inspired:**
- `#075e54` — Header, elementos primarios
- `#128c7e` — Avatares, badges
- `#25d366` — Acciones, botón enviar
- `#efeae2` — Fondo de chat (con patrón sutil)
- `#d9fdd3` — Burbuja de mensaje del usuario

## Setup local

```bash
# 1. Clonar
git clone https://github.com/sebitabravo/Wenuke.git
cd Wenuke

# 2. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Editar con GROQ_API_KEY (opcional)
uvicorn main:app --reload --port 8000

# 3. Frontend (otra terminal)
cd frontend
python3 -m http.server 3000
# → Landing: http://localhost:3000
# → Demo:   http://localhost:3000/app
```

## Variables de entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `GROQ_API_KEY` | No | API key de Groq. Sin ella, responde offline. |
| `WHATSAPP_TOKEN` | No | Token de WhatsApp Business Cloud API |
| `WHATSAPP_PHONE_NUMBER_ID` | No | Phone Number ID de WhatsApp |
| `DB_PATH` | No | Path de SQLite. Default: `wenuke.db` |

## Recursos

- [Presentación (PPTX)](https://chat.z.ai/space/f1jpm3pxbtz1-ppt)
- [Deck Pitch (PDF)](./docs/pitch.pdf)
- [Deck Pitch 2 (PDF)](./docs/pitch-2.pdf)
- [Design System](./DESIGN.md)

## Licencia

MIT © 2026 Werken-mapu
