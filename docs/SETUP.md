# Setup local — Werken-mapu

El sistema funciona sin configurar nada — usa SQLite local y responde offline con reglas expertas.

## Levantar el proyecto

```bash
# 1. Clonar
git clone https://github.com/sebitabravo/Wenuke.git
cd Wenuke

# 2. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Variables de entorno (opcionales — el sistema funciona sin ellas)
# GROQ_API_KEY     → IA conversacional (sin key = modo offline con reglas expertas)
# WHATSAPP_TOKEN   → Envío de alertas por WhatsApp
# TURSO_DATABASE_URL + TURSO_AUTH_TOKEN → BD serverless (sin esto = SQLite local)
cp .env.example .env  # editar solo si tenés las keys

uvicorn main:app --reload --port 8000

# 3. Frontend (otra terminal)
cd frontend
python3 -m http.server 3000
# → Landing: http://localhost:3000
# → Demo:   http://localhost:3000/app
```

## Docker

```bash
docker compose up
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

## Variables de entorno

| Variable | Requerida | Default | Descripción |
|---|---|---|---|
| `GROQ_API_KEY` | No | (vacío) | API key de Groq. Sin ella, responde offline con reglas expertas |
| `WHATSAPP_TOKEN` | No | (vacío) | Token de WhatsApp Business Cloud API |
| `WHATSAPP_PHONE_NUMBER_ID` | No | (vacío) | Phone Number ID de WhatsApp |
| `ADMIN_TOKEN` | **Sí** (prod) | (vacío) | Token para `/enviar-alertas`. Mínimo 16 chars. Sin valor → 501 |
| `TURSO_DATABASE_URL` | No | (vacío) | URL de Turso. Sin ella, usa SQLite local |
| `TURSO_AUTH_TOKEN` | No | (vacío) | Auth token de Turso |
| `DB_PATH` | No | `wenuke.db` | Path del archivo SQLite local |
| `FORECAST_DAYS` | No | `7` | Días de pronóstico a consultar |
| `CACHE_TTL_SEGUNDOS` | No | `1800` | TTL del cache de clima (30 min) |
| `CORS_ORIGINS` | No | `localhost:3000,...` | Orígenes CORS permitidos (separados por coma) |

## Tests

```bash
cd backend
pytest -v                         # Unitarios
pytest -v -m e2e                  # E2E (requiere URLs de prod)
ruff check .                      # Lint
mypy . --ignore-missing-imports   # Type checking
```
