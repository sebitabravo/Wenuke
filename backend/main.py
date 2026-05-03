"""Werken-mapu API — Asistente climático para pequeños agricultores de La Araucanía."""

import hashlib
import logging
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import cast

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from clima import clima_client
from config import config
from db import (
    actualizar_plan,
    agregar_parcela,
    eliminar_parcela,
    init_db,
    obtener_parcelas,
    obtener_usuario_por_token_hash,
    registrar_usuario,
)
from db import (
    refresh_token as db_refresh_token,
)
from llm import llm_client
from models import (
    ActualizarPlanRequest,
    ClimaResponse,
    EnviarAlertasResponse,
    HistoricoResponse,
    ParcelaRequest,
    ParcelaResponse,
    ParcelasListResponse,
    PlanResponse,
    PrecioMercado,
    PreciosResponse,
    PreguntarRequest,
    PreguntarResponse,
    RecomendacionItem,
    RecomendacionResponse,
    RegistrarRequest,
    RegistrarResponse,
    ResumenAnual,
)
from odepa import odepa_client
from reglas import Cultivo, evaluar_reglas, generar_recomendaciones
from scheduler import alert_scheduler
from servicio_alertas import ejecutar_chequeo_alertas

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("wenuke.main")

CULTIVOS_VALIDOS = {"papa", "trigo", "manzano", "general"}

# Rate limiting simple (en memoria — suficiente para serverless MVP)
_rate_limits: dict[str, list[float]] = {}
_RATE_WINDOW = 60  # segundos


def _check_rate_limit(key: str, max_requests: int) -> None:
    """Rate limiter basado en sliding window. Lanza 429 si se excede."""
    ahora = time.time()
    ventana = [t for t in _rate_limits.get(key, []) if ahora - t < _RATE_WINDOW]
    if len(ventana) >= max_requests:
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Esperá un minuto.")
    ventana.append(ahora)
    _rate_limits[key] = ventana


# ---------------------------------------------------------------------------
# Dependencies de autenticación (FastAPI Depends)
# ---------------------------------------------------------------------------


def _hash_token(token: str) -> str:
    """Hash SHA-256 del token para comparación con BD."""
    return hashlib.sha256(token.encode()).hexdigest()


def _extraer_token(authorization: str) -> str:
    """Extrae el token de un header Authorization: Bearer <token>."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Formato: Authorization: Bearer <token>")
    token = authorization[7:]
    if not token or len(token) < 8:
        raise HTTPException(status_code=401, detail="Token vacío o inválido")
    return token


async def auth_usuario(authorization: str = Header(..., description="Bearer <token>")) -> dict:
    """Dependency: autentica usuario y retorna dict con sus datos."""
    token = _extraer_token(authorization)
    token_hash = _hash_token(token)
    usuario = await obtener_usuario_por_token_hash(token_hash)
    if not usuario:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    # Verificar expiración
    expires_at = usuario.get("token_expires_at")
    if expires_at:
        expires_dt = datetime.fromisoformat(expires_at)
        if expires_dt < datetime.now(datetime.UTC):
            raise HTTPException(status_code=401, detail="Token expirado. Volvé a registrarte.")
    return usuario


async def auth_admin(authorization: str = Header(..., description="Admin Bearer <token>")) -> None:
    """Dependency: autentica admin token con comparación en tiempo constante."""
    if not config.admin_token_activo:
        raise HTTPException(status_code=501, detail="Admin token no configurado en el servidor")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Formato: Authorization: Bearer <token>")
    provided = authorization[7:]
    if not secrets.compare_digest(provided, config.admin_token):
        raise HTTPException(status_code=403, detail="Admin token inválido")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    alert_scheduler.iniciar()
    yield
    alert_scheduler.detener()


# ---------------------------------------------------------------------------
# Seguridad: headers HTTP
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response


app = FastAPI(
    title="Werken-mapu API",
    description="Werken-mapu — Asistente climático con IA para pequeños agricultores de La Araucanía",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)

origins = config.cors_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "servicio": "Werken-mapu API",
        "version": "0.1.0",
        "estado": "operativo",
        "offline": llm_client.modo_offline,
    }


# ---------------------------------------------------------------------------
# GET /clima — Pronóstico con alertas por cultivo
# ---------------------------------------------------------------------------
@app.get("/clima", response_model=ClimaResponse)
async def clima(
    lat: float = Query(..., ge=-90, le=90, description="Latitud de la parcela"),
    lon: float = Query(..., ge=-180, le=180, description="Longitud de la parcela"),
    cultivo: str = Query("general", description="Cultivo: papa, trigo, manzano, general"),
):
    if cultivo not in CULTIVOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Cultivo '{cultivo}' no soportado. Usar: {', '.join(CULTIVOS_VALIDOS)}",
        )
    cultivo = cast(Cultivo, cultivo)

    try:
        raw = await clima_client.fetch_forecast(lat, lon)
    except Exception as e:
        logger.error(f"OpenMeteo forecast error: {e}")
        raise HTTPException(status_code=502, detail="Error al consultar datos climáticos")

    hourly = clima_client.parse_hourly(raw)
    daily = clima_client.extract_daily(raw)

    # Evaluar reglas por cultivo
    resultado = evaluar_reglas(hourly, cultivo)

    # Construir resumen desde datos diarios
    hoy = daily[0] if daily else {}
    resumen = {
        "temp_min": hoy.get("temp_min", "N/D"),
        "temp_max": hoy.get("temp_max", "N/D"),
        "lluvia_total_24h": hoy.get("precipitacion_total", 0.0),
        "viento_max": hoy.get("viento_max", "N/D"),
        "dias_forecast": config.forecast_days,
    }

    return ClimaResponse(
        cultivo=resultado["cultivo"],
        ubicacion={"lat": lat, "lon": lon},
        alertas=resultado["alertas"],
        resumen=resumen,
        raw_forecast=raw,
    )


# ---------------------------------------------------------------------------
# POST /preguntar — Asistente conversacional
# ---------------------------------------------------------------------------
@app.post("/preguntar", response_model=PreguntarResponse)
async def preguntar(req: PreguntarRequest, request: Request):
    _check_rate_limit(f"preguntar:{request.client.host if request.client else 'unknown'}", 10)
    # Obtener contexto climático para el LLM
    if req.cultivo not in CULTIVOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Cultivo no soportado: {req.cultivo}")
    cultivo = cast(Cultivo, req.cultivo)
    resultado = {"alertas": [], "cultivo": req.cultivo}
    resumen = {}
    try:
        raw = await clima_client.fetch_forecast(req.lat, req.lon)
        hourly = clima_client.parse_hourly(raw)
        resultado = evaluar_reglas(hourly, cultivo)

        daily = clima_client.extract_daily(raw)
        hoy = daily[0] if daily else {}
        resumen = {
            "temp_min": hoy.get("temp_min", "N/D"),
            "temp_max": hoy.get("temp_max", "N/D"),
            "lluvia_total_24h": hoy.get("precipitacion_total", 0.0),
            "viento_max": hoy.get("viento_max", "N/D"),
        }
    except Exception:
        logger.warning("No se pudo obtener clima para /preguntar — LLM en modo offline")

    contexto = {
        "resumen": resumen,
        "alertas": resultado.get("alertas", []),
    }

    respuesta = await llm_client.preguntar(req.pregunta, contexto, req.cultivo)
    return PreguntarResponse(**respuesta)


# ---------------------------------------------------------------------------
# POST /registrar — Alta de agricultor
# ---------------------------------------------------------------------------
@app.post("/registrar", response_model=RegistrarResponse)
async def registrar(req: RegistrarRequest, request: Request):
    _check_rate_limit(f"registrar:{request.client.host if request.client else 'unknown'}", 3)
    try:
        resultado = await registrar_usuario({
            "whatsapp": req.whatsapp,
            "nombre": req.nombre,
            "lat": req.lat,
            "lon": req.lon,
            "cultivos": req.cultivos,
            "plan": req.plan,
            "nombre_parcela": req.nombre_parcela,
        })
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    cultivos_str = ", ".join(req.cultivos)
    return RegistrarResponse(
        mensaje=(
            f"¡Registro exitoso, {req.nombre}! Te avisaremos por WhatsApp "
            f"ante cualquier alerta para tus cultivos de {cultivos_str}. "
            f"Plan: {req.plan}."
        ),
        usuario_id=resultado["usuario_id"],
        token=resultado["token"],
        parcela_id=resultado["parcela_id"],
    )


# ---------------------------------------------------------------------------
# Parcelas CRUD
# ---------------------------------------------------------------------------
@app.get("/parcelas", response_model=ParcelasListResponse)
async def listar_parcelas(usuario: dict = Depends(auth_usuario)):

    parcelas = await obtener_parcelas(usuario["id"])
    max_parcelas = 1 if usuario["plan"] == "free" else 10

    return ParcelasListResponse(
        usuario_id=usuario["id"],
        plan=usuario["plan"],
        parcelas=[ParcelaResponse(**p) for p in parcelas],
        max_parcelas=max_parcelas,
    )


@app.post("/parcelas", response_model=ParcelaResponse)
async def crear_parcela(
    req: ParcelaRequest,
    usuario: dict = Depends(auth_usuario),
):
    try:
        parcela_id = await agregar_parcela(usuario["id"], req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return ParcelaResponse(id=parcela_id, nombre=req.nombre, lat=req.lat, lon=req.lon, cultivos=req.cultivos)


@app.delete("/parcelas/{parcela_id}")
async def borrar_parcela(
    parcela_id: int,
    usuario: dict = Depends(auth_usuario),
):

    eliminado = await eliminar_parcela(parcela_id, usuario["id"])
    if not eliminado:
        raise HTTPException(status_code=404, detail="Parcela no encontrada o no pertenece al usuario")

    return {"mensaje": "Parcela eliminada", "parcela_id": parcela_id}


# ---------------------------------------------------------------------------
# Plan / Suscripción
# ---------------------------------------------------------------------------
@app.get("/plan", response_model=PlanResponse)
async def ver_plan(usuario: dict = Depends(auth_usuario)):

    parcelas = await obtener_parcelas(usuario["id"])
    max_parcelas = 1 if usuario["plan"] == "free" else 10

    return PlanResponse(
        usuario_id=usuario["id"],
        nombre=usuario["nombre"],
        plan=usuario["plan"],
        parcelas_actuales=len(parcelas),
        parcelas_max=max_parcelas,
    )


@app.post("/plan", response_model=PlanResponse)
async def cambiar_plan(
    req: ActualizarPlanRequest,
    usuario: dict = Depends(auth_usuario),
):

    actualizado = await actualizar_plan(usuario["id"], req.plan)
    parcelas = await obtener_parcelas(usuario["id"])
    max_parcelas = 1 if req.plan == "free" else 10

    return PlanResponse(
        usuario_id=actualizado["id"],
        nombre=actualizado["nombre"],
        plan=actualizado["plan"],
        parcelas_actuales=len(parcelas),
        parcelas_max=max_parcelas,
    )


# ---------------------------------------------------------------------------
# POST /refresh-token — Rotar token de autenticación
# ---------------------------------------------------------------------------


@app.post("/refresh-token", response_model=RegistrarResponse)
async def refresh_token(usuario: dict = Depends(auth_usuario)):
    resultado = await db_refresh_token(usuario["id"])
    return RegistrarResponse(
        mensaje="Token renovado con éxito. Guardalo bien.",
        usuario_id=resultado["usuario_id"],
        token=resultado["token"],
        parcela_id=resultado.get("parcela_id", 0),
    )


# ---------------------------------------------------------------------------
# GET /precios — Precios de mercado mayorista (ODEPA)
# ---------------------------------------------------------------------------
@app.get("/precios", response_model=PreciosResponse)
async def precios(
    producto: str | None = Query(None, description="Filtrar por producto: papa, trigo, manzano"),
):
    if producto:
        if producto not in ("papa", "trigo", "manzano"):
            raise HTTPException(status_code=400, detail=f"Producto no soportado: {producto}")
        datos = [await odepa_client.fetch_precios(producto)]
    else:
        datos = await odepa_client.fetch_todos()

    return PreciosResponse(
        precios=[PrecioMercado(**d) for d in datos if "error" not in d],
        consultado_en=datetime.now().isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /recomendaciones — Recomendaciones diarias accionables
# ---------------------------------------------------------------------------
@app.get("/recomendaciones", response_model=RecomendacionResponse)
async def recomendaciones(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    cultivo: str = Query("general", description="Cultivo: papa, trigo, manzano, general"),
):
    if cultivo not in CULTIVOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Cultivo no soportado: {cultivo}")
    cultivo = cast(Cultivo, cultivo)

    try:
        raw = await clima_client.fetch_forecast(lat, lon)
        hourly = clima_client.parse_hourly(raw)
        daily = clima_client.extract_daily(raw)
    except Exception as e:
        logger.error(f"OpenMeteo forecast error en /recomendaciones: {e}")
        raise HTTPException(status_code=502, detail="Error al consultar datos climáticos")

    recs_raw = generar_recomendaciones(hourly, daily, cultivo)

    return RecomendacionResponse(
        cultivo=cultivo,
        ubicacion={"lat": lat, "lon": lon},
        dia=daily[0]["dia"] if daily else "",
        recomendaciones=[
            RecomendacionItem(**r) for r in recs_raw
        ],
    )


# ---------------------------------------------------------------------------
# GET /historico — Datos climáticos históricos para análisis de tendencias
# ---------------------------------------------------------------------------
@app.get("/historico", response_model=HistoricoResponse)
async def historico(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    anos: int = Query(5, ge=1, le=10),
):
    hoy = date.today()
    inicio = f"{hoy.year - anos}-{hoy.month:02d}-{hoy.day:02d}"
    fin = f"{hoy.year - 1}-{hoy.month:02d}-{hoy.day:02d}"

    try:
        raw = await clima_client.fetch_historico(lat, lon, inicio, fin)
    except Exception as e:
        logger.error(f"OpenMeteo histórico error: {e}")
        raise HTTPException(status_code=502, detail="Error al consultar datos climáticos históricos")

    diarios = clima_client.parse_historico(raw)

    # Agregar por año
    agrupado: dict[int, list[dict]] = {}
    for d in diarios:
        ano = int(d["fecha"][:4])
        agrupado.setdefault(ano, []).append(d)

    resumen_anual = []
    for ano in sorted(agrupado.keys()):
        dias = agrupado[ano]
        temps_max = [d["temp_max"] for d in dias if d["temp_max"] is not None]
        temps_min = [d["temp_min"] for d in dias if d["temp_min"] is not None]
        precip = [d["precipitacion"] for d in dias]
        vientos = [d["viento_max"] for d in dias if d["viento_max"] is not None]

        resumen_anual.append(ResumenAnual(
            ano=ano,
            temp_max_promedio=round(sum(temps_max) / len(temps_max), 1) if temps_max else 0,
            temp_min_promedio=round(sum(temps_min) / len(temps_min), 1) if temps_min else 0,
            temp_min_absoluta=round(min(temps_min), 1) if temps_min else 0,
            precipitacion_total=round(sum(precip), 1),
            dias_lluvia=sum(1 for p in precip if p > 1.0),
            dias_helada=sum(1 for t in temps_min if t <= 0),
            viento_max=round(max(vientos), 1) if vientos else 0,
        ))

    return HistoricoResponse(
        ubicacion={"lat": lat, "lon": lon},
        anos_consultados=anos,
        resumen_anual=resumen_anual,
        datos_diarios=diarios,
    )


# ---------------------------------------------------------------------------
# POST /enviar-alertas — Dispatch manual de alertas (protegido con admin token)
# ---------------------------------------------------------------------------
@app.post("/enviar-alertas", response_model=EnviarAlertasResponse)
async def enviar_alertas(_: None = Depends(auth_admin)):
    resultado = await ejecutar_chequeo_alertas()
    return EnviarAlertasResponse(**resultado)
