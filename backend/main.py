"""Wenuke API — Asistente climático para pequeños agricultores de La Araucanía."""

from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from clima import clima_client
from config import config
from db import (
    actualizar_plan,
    agregar_parcela,
    eliminar_parcela,
    init_db,
    obtener_parcelas,
    obtener_todos_los_usuarios,
    obtener_usuario_por_token,
    obtener_usuarios_con_cultivo,
    registrar_alerta,
    registrar_usuario,
)
from llm import llm_client
from models import (
    ActualizarPlanRequest,
    ClimaResponse,
    EnviarAlertasResponse,
    HistoricoRequest,
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
from reglas import evaluar_reglas, generar_recomendaciones
from scheduler import alert_scheduler
from whatsapp import whatsapp_client

CULTIVOS_VALIDOS = {"papa", "trigo", "manzano", "general"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    alert_scheduler.iniciar()
    yield
    alert_scheduler.detener()


app = FastAPI(
    title="Wenuke API",
    description="Asistente climático con IA para pequeños agricultores de La Araucanía",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "servicio": "Wenuke API",
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

    try:
        raw = await clima_client.fetch_forecast(lat, lon)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al consultar OpenMeteo: {e}")

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
async def preguntar(req: PreguntarRequest):
    # Obtener contexto climático para el LLM
    try:
        raw = await clima_client.fetch_forecast(req.lat, req.lon)
        hourly = clima_client.parse_hourly(raw)
        resultado = evaluar_reglas(hourly, req.cultivo)

        daily = clima_client.extract_daily(raw)
        hoy = daily[0] if daily else {}
        resumen = {
            "temp_min": hoy.get("temp_min", "N/D"),
            "temp_max": hoy.get("temp_max", "N/D"),
            "lluvia_total_24h": hoy.get("precipitacion_total", 0.0),
            "viento_max": hoy.get("viento_max", "N/D"),
        }
    except Exception:
        # Sin clima, el LLM igual puede responder en modo offline
        resultado = {"alertas": [], "cultivo": req.cultivo}
        resumen = {}

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
async def registrar(req: RegistrarRequest):
    try:
        resultado = registrar_usuario({
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
async def listar_parcelas(token: str = Query(..., description="Token de autenticación")):
    usuario = obtener_usuario_por_token(token)
    if not usuario:
        raise HTTPException(status_code=401, detail="Token inválido")

    parcelas = obtener_parcelas(usuario["id"])
    max_parcelas = 1 if usuario["plan"] == "free" else 10

    return ParcelasListResponse(
        usuario_id=usuario["id"],
        plan=usuario["plan"],
        parcelas=[ParcelaResponse(**p) for p in parcelas],
        max_parcelas=max_parcelas,
    )


@app.post("/parcelas", response_model=ParcelaResponse)
async def crear_parcela(req: ParcelaRequest, token: str = Query(..., description="Token de autenticación")):
    usuario = obtener_usuario_por_token(token)
    if not usuario:
        raise HTTPException(status_code=401, detail="Token inválido")

    try:
        parcela_id = agregar_parcela(usuario["id"], req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return ParcelaResponse(id=parcela_id, nombre=req.nombre, lat=req.lat, lon=req.lon, cultivos=req.cultivos)


@app.delete("/parcelas/{parcela_id}")
async def borrar_parcela(parcela_id: int, token: str = Query(..., description="Token de autenticación")):
    usuario = obtener_usuario_por_token(token)
    if not usuario:
        raise HTTPException(status_code=401, detail="Token inválido")

    if not eliminar_parcela(parcela_id, usuario["id"]):
        raise HTTPException(status_code=404, detail="Parcela no encontrada o no pertenece al usuario")

    return {"mensaje": "Parcela eliminada", "parcela_id": parcela_id}


# ---------------------------------------------------------------------------
# Plan / Suscripción
# ---------------------------------------------------------------------------
@app.get("/plan", response_model=PlanResponse)
async def ver_plan(token: str = Query(..., description="Token de autenticación")):
    usuario = obtener_usuario_por_token(token)
    if not usuario:
        raise HTTPException(status_code=401, detail="Token inválido")

    parcelas = obtener_parcelas(usuario["id"])
    max_parcelas = 1 if usuario["plan"] == "free" else 10

    return PlanResponse(
        usuario_id=usuario["id"],
        nombre=usuario["nombre"],
        plan=usuario["plan"],
        parcelas_actuales=len(parcelas),
        parcelas_max=max_parcelas,
    )


@app.post("/plan", response_model=PlanResponse)
async def cambiar_plan(req: ActualizarPlanRequest):
    usuario = obtener_usuario_por_token(req.token)
    if not usuario:
        raise HTTPException(status_code=401, detail="Token inválido")

    actualizado = actualizar_plan(usuario["id"], req.plan)
    parcelas = obtener_parcelas(usuario["id"])
    max_parcelas = 1 if req.plan == "free" else 10

    return PlanResponse(
        usuario_id=actualizado["id"],
        nombre=actualizado["nombre"],
        plan=actualizado["plan"],
        parcelas_actuales=len(parcelas),
        parcelas_max=max_parcelas,
    )


# ---------------------------------------------------------------------------
# GET /precios — Precios de mercado mayorista (ODEPA)
# ---------------------------------------------------------------------------
@app.get("/precios", response_model=PreciosResponse)
async def precios(
    producto: Optional[str] = Query(None, description="Filtrar por producto: papa, trigo, manzano"),
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

    try:
        raw = await clima_client.fetch_forecast(lat, lon)
        hourly = clima_client.parse_hourly(raw)
        daily = clima_client.extract_daily(raw)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error OpenMeteo: {e}")

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
        raise HTTPException(status_code=502, detail=f"Error al consultar histórico OpenMeteo: {e}")

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
# POST /enviar-alertas — Dispatch manual de alertas (mock worker)
# ---------------------------------------------------------------------------
@app.post("/enviar-alertas", response_model=EnviarAlertasResponse)
async def enviar_alertas():
    detalle: list[dict] = []
    usuarios_alertados: set[int] = set()
    envios_fallidos: int = 0

    for cultivo in ["papa", "trigo", "manzano"]:
        usuarios = obtener_usuarios_con_cultivo(cultivo)
        if not usuarios:
            continue

        # Agrupar usuarios por ubicación (cache hit)
        ubicaciones_procesadas: dict[str, dict] = {}

        for u in usuarios:
            key = f"{round(u['lat'], 2)},{round(u['lon'], 2)}"

            if key not in ubicaciones_procesadas:
                try:
                    raw = await clima_client.fetch_forecast(u["lat"], u["lon"])
                    hourly = clima_client.parse_hourly(raw)
                    resultado = evaluar_reglas(hourly, cultivo)
                except Exception:
                    continue
                ubicaciones_procesadas[key] = resultado
            else:
                resultado = ubicaciones_procesadas[key]

            alertas_usuario = resultado.get("alertas", [])
            if not alertas_usuario:
                continue

            # Registrar alertas en BD
            for alerta in alertas_usuario:
                registrar_alerta(u["id"], alerta["tipo"], alerta["mensaje"])

            # Enviar por WhatsApp si está configurado
            if whatsapp_client.activo:
                envio = await whatsapp_client.enviar_plantilla_alerta(
                    u["whatsapp"], alertas_usuario, cultivo
                )
                if not envio["enviado"]:
                    envios_fallidos += 1

            usuarios_alertados.add(u["id"])
            detalle.append({
                "usuario_id": u["id"],
                "whatsapp": u["whatsapp"],
                "nombre": u["nombre"],
                "cultivo": cultivo,
                "alertas": [
                    {"tipo": a["tipo"], "severidad": a["severidad"], "dia": a.get("dia", "")}
                    for a in alertas_usuario
                ],
            })

    return EnviarAlertasResponse(
        enviadas=sum(len(d["alertas"]) for d in detalle),
        usuarios_afectados=len(usuarios_alertados),
        detalle=detalle,
        envios_fallidos=envios_fallidos,
        whatsapp_activo=whatsapp_client.activo,
    )
