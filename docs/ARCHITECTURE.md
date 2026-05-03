# Arquitectura — Werken-mapu

## Diagrama

```
┌──────────────────────────────────────────────────────────┐
│                    CLIENTES                               │
│  WhatsApp (prod)  │  Navegador web (demo/landing)         │
│  Meta Business API│  Vanilla JS · Leaflet · Tailwind CDN  │
└────────┬──────────┴───────────────┬──────────────────────┘
         │ HTTPS                    │ HTTPS
┌────────▼──────────────────────────▼──────────────────────┐
│                   FASTAPI (Vercel Serverless)             │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Routes (main.py) — 14 endpoints                     │ │
│  │  /clima  /preguntar  /recomendaciones  /historico   │ │
│  │  /precios  /registrar  /parcelas CRUD  /plan CRUD   │ │
│  │  /enviar-alertas (admin)                             │ │
│  └──────────┬──────────────┬───────────────────────────┘ │
│             │              │                              │
│  ┌──────────▼────┐  ┌──────▼──────────┐                  │
│  │  Domain Layer │  │  External APIs  │                  │
│  │  (zero I/O)   │  │  (async HTTP)   │                  │
│  │               │  │                 │                  │
│  │  reglas.py    │  │  clima.py       │                  │
│  │  Motor de     │  │  OpenMeteo      │                  │
│  │  reglas por   │  │  forecast +     │                  │
│  │  cultivo      │  │  archive (gratis│                  │
│  │  19 umbrales  │  │  sin API key)   │                  │
│  │  por cultivo  │  │                 │                  │
│  └───────────────┘  │  llm.py         │                  │
│                     │  Groq Llama 3.1  │                  │
│                     │  + fallback      │                  │
│                     │  offline con     │                  │
│                     │  reglas expertas │                  │
│                     │                 │                  │
│                     │  odepa.py        │                  │
│                     │  Precios mercado │                  │
│                     │  + referencia    │                  │
│                     │                 │                  │
│                     │  whatsapp.py     │                  │
│                     │  Meta Graph API  │                  │
│                     │  v21.0           │                  │
│                     └─────────────────┘                  │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Data Layer (db.py) — Dual backend                   │ │
│  │  ┌──────────────────┐  ┌──────────────────────────┐ │ │
│  │  │ Turso (HTTP)     │  │ aiosqlite (local)         │ │ │
│  │  │ libsql-experiment│  │ WAL mode · FK enabled     │ │ │
│  │  │ Serverless prod  │  │ Desarrollo local          │ │ │
│  │  └──────────────────┘  └──────────────────────────┘ │ │
│  │  Interfaz unificada: fetchall fetchone execute insert│ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Background (scheduler.py)                           │ │
│  │  asyncio loop cada 6h → evalúa reglas → WhatsApp    │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

## Stack tecnológico

| Capa | Tecnología | Decisión |
|---|---|---|
| **API** | FastAPI 0.115 (Python 3.12) | Tipado fuerte, async nativo, validación Pydantic v2, OpenAPI auto-generado |
| **Base de datos** | Turso + aiosqlite (dual) | Turso: SQLite sobre HTTP, serverless, $0 free tier. aiosqlite: mismo schema para dev local |
| **Clima** | OpenMeteo API | Gratis, sin API key, cobertura global, forecast horario + archivo histórico |
| **IA** | Groq (Llama 3.1 70B) + fallback offline | $0.59/M tokens. Sin key → responde con reglas expertas pre-cargadas |
| **Precios** | ODEPA datos de referencia | Mercado mayorista chileno (Lo Valledor) |
| **Mensajería** | WhatsApp Business Cloud API | Meta Graph API v21.0. Envío directo, sin proveedor intermediario |
| **Mapas** | Leaflet + OpenStreetMap | Open source, sin API key, tiles gratuitos |
| **Frontend** | HTML5 + Tailwind CSS CDN + Vanilla JS | Cero build step, cero dependencias npm, carga instantánea |
| **CI/CD** | GitHub Actions → Vercel | Ruff + mypy + pytest. Deploy automático desde main |
| **Infra** | Vercel (Static + Serverless) | HTTPS, CDN global, deploy desde monorepo con rootDirectory por proyecto |

**Costo operativo estimado: $0–10 USD/mes** (vs $200+ con APIs comerciales equivalentes).

## Estructura del proyecto

```
Wenuke/
├── frontend/                    # Vercel Static
│   ├── index.html               # Landing page — diseño WhatsApp-inspired
│   ├── app.html                 # Demo chat — interfaz mobile-first
│   ├── app.js                   # Lógica del chat (vanilla JS, 274 LOC)
│   └── vercel.json
├── backend/                     # Vercel Serverless (Python)
│   ├── main.py                  # FastAPI app — 14 endpoints, lifespan, CORS
│   ├── models.py                # Schemas Pydantic v2 — 17 modelos
│   ├── reglas.py                # Motor de reglas por cultivo — dominio puro, cero I/O
│   ├── clima.py                 # Cliente OpenMeteo — forecast + histórico + cache
│   ├── llm.py                   # Cliente Groq + fallback offline con reglas expertas
│   ├── odepa.py                 # Precios mayoristas — referencia + scraping
│   ├── whatsapp.py              # WhatsApp Business API — envío directo
│   ├── servicio_alertas.py      # Lógica compartida API/scheduler
│   ├── scheduler.py             # Loop asyncio cada 6h para chequeo automático
│   ├── db.py                    # Dual backend Turso/aiosqlite — interfaz unificada
│   ├── config.py                # Configuración tipada desde variables de entorno
│   ├── .env.example             # Variables de entorno de referencia
│   ├── requirements.txt
│   ├── vercel.json
│   └── tests/
│       ├── e2e/
│       │   ├── test_e2e_api.py       # httpx contra prod
│       │   └── test_e2e_playwright.py # Browser contra prod
│       └── test_*.py                  # Unitarios (reglas, clima)
├── docs/
│   ├── ARCHITECTURE.md           # Este archivo
│   ├── API.md                    # Endpoints y autenticación
│   ├── SETUP.md                  # Setup local y variables de entorno
│   ├── screenshots/              # Capturas de pantalla
│   ├── pitch.pdf                 # Deck de presentación
│   └── pitch-2.pdf               # Deck complementario
├── DESIGN.md                    # Design system (Stitch/awesome-design-md)
├── CONTRIBUTING.md              # Guía de contribución
└── .github/workflows/test.yml   # CI: ruff + mypy + pytest
```

## Decisiones técnicas

### ¿Por qué FastAPI y no Django/Flask?

FastAPI da validación automática vía Pydantic, documentación OpenAPI sin configuración extra, y soporte async nativo — crítico para un sistema que consulta 3 APIs externas por request. Django era sobre-ingeniería para 14 endpoints. Flask requería demasiado boilerplate para validación.

### ¿Por qué Turso + aiosqlite y no PostgreSQL?

SQLite es la base de datos más usada del mundo. Turso la expone sobre HTTP con replicación global, ideal para serverless (Vercel Functions no mantienen conexiones persistentes). aiosqlite permite desarrollo local sin depender de servicios externos. El dual backend abstrae la diferencia: mismo schema, misma interfaz, cero cambios de código entre entornos.

PostgreSQL para este caso de uso (MVP, usuarios <1000) habría sido costo y complejidad innecesarios.

### ¿Por qué Llama 3.1 70B vía Groq y no GPT-4o?

Costo. Groq cobra $0.59/M tokens vs $5+ de OpenAI. Para un sistema que podría procesar cientos de consultas diarias de agricultores, la diferencia es significativa. Además, el fallback offline con reglas expertas hardcodeadas asegura que el sistema nunca deje de responder — ni siquiera sin conexión a internet.

### ¿Por qué Vanilla JS y no React/Vue?

El chat demo es una SPA de una sola pantalla. React habría agregado ~40KB de JS para un componente que son 274 líneas de vanilla. La landing page es estática. No hay estado complejo que justifique un framework. Tailwind CDN evita build step.

Para un producto real con múltiples pantallas y lógica de suscripción, React con Next.js sería la elección correcta — pero para MVP de hackathon, vanilla JS es la decisión consciente.

## Cobertura de tests

El motor de reglas (`reglas.py`, dominio puro) tiene **20+ tests unitarios** cubriendo severidades de helada/lluvia/viento/granizo, detección de alertas por cultivo, y generación de recomendaciones (fumigar/regar/sembrar/cosechar). Cliente de clima con tests de parseo y cache. API con tests E2E (`httpx` + `playwright`). CI corre ruff + mypy + pytest en cada push.
