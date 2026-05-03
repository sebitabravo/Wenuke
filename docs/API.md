# API — Werken-mapu

Base URL: `https://backend-beryl-nu-18.vercel.app`

OpenAPI docs: [backend-beryl-nu-18.vercel.app/docs](https://backend-beryl-nu-18.vercel.app/docs)

## Endpoints

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `GET` | `/` | — | Health check (servicio, versión, estado, modo offline) |
| `GET` | `/clima` | — | Pronóstico 7 días + alertas por cultivo y coordenadas |
| `POST` | `/preguntar` | — | Asistente IA conversacional con contexto climático real |
| `GET` | `/recomendaciones` | — | Recomendaciones diarias: fumigar, regar, sembrar, cosechar |
| `GET` | `/historico` | — | Datos climáticos históricos 1–10 años (OpenMeteo Archive) |
| `GET` | `/precios` | — | Precios mayoristas de referencia por producto |
| `POST` | `/registrar` | — | Alta de agricultor — retorna token de autenticación |
| `GET` | `/parcelas` | Bearer | Listar parcelas del usuario autenticado |
| `POST` | `/parcelas` | Bearer | Agregar parcela nueva (validación plan free/premium) |
| `DELETE` | `/parcelas/{id}` | Bearer | Eliminar parcela (valida ownership) |
| `GET` | `/plan` | Bearer | Ver plan actual y uso de parcelas |
| `POST` | `/plan` | Bearer | Cambiar plan (free ↔ premium) |
| `POST` | `/refresh-token` | Bearer | Rotar token de autenticación |
| `POST` | `/enviar-alertas` | Admin Bearer | Dispatch manual de alertas vía WhatsApp |

## Autenticación

- **Usuarios:** `Authorization: Bearer <token>` — token generado en `/registrar`, almacenado como hash SHA-256 en BD. Expira a los 90 días. Usar `/refresh-token` para rotar.
- **Admin:** `Authorization: Bearer <admin_token>` — configurado via `ADMIN_TOKEN` env var. Sin valor configurado (mínimo 16 caracteres), el endpoint retorna 501.

## Modelo de datos

```
usuarios ──< parcelas ──< cultivos
    │
    └──< alertas_enviadas (auditoría)
```

- **usuarios:** id, whatsapp (UNIQUE), nombre, plan (free|premium), token (UNIQUE)
- **parcelas:** id, usuario_id (FK), nombre, lat, lon
- **cultivos:** id, parcela_id (FK), tipo (papa|trigo|manzano|general)
- **alertas_enviadas:** id, usuario_id (FK), tipo, mensaje, timestamp

## Planes

### Plan Libre — $0 para siempre
- Alertas de helada, lluvia intensa, viento fuerte y granizo
- Pronóstico 7 días por ubicación GPS
- 1 parcela
- Acceso por WhatsApp y web

### Plan Premium — $3.000 CLP/mes
- Todo lo del plan libre
- Hasta 10 parcelas
- Alertas personalizadas por cultivo (papa, trigo, manzano)
- Asistente IA conversacional 24/7
- Recomendaciones diarias: fumigar, regar, sembrar, cosechar
- Análisis de precios de mercado (ODEPA)
- Historial climático 5–10 años
- Calendario de rotación de cultivos

### B2B — PRODESAL / Cooperativas
- Paquetes para 100–500 agricultores afiliados
- $1.500 CLP/mes por agricultor
- Administración centralizada, reportes de uso
