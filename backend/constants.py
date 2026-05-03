"""Constantes del dominio — fuente única de verdad para strings mágicos.

Usar estas constantes en vez de strings literales evita typos silenciosos.
Un typo en CULTIVO_PAPA rompe en importación. Un typo en "papa" rompe en runtime.
"""

from typing import Literal

# ---------------------------------------------------------------------------
# Cultivos
# ---------------------------------------------------------------------------
Cultivo = Literal["papa", "trigo", "manzano", "general"]

CULTIVO_PAPA: Cultivo = "papa"
CULTIVO_TRIGO: Cultivo = "trigo"
CULTIVO_MANZANO: Cultivo = "manzano"
CULTIVO_GENERAL: Cultivo = "general"

CULTIVOS_VALIDOS: frozenset[str] = frozenset({"papa", "trigo", "manzano", "general"})

# Cultivos que disparan alertas productivas (excluye "general" que es comodín)
CULTIVOS_PRODUCTIVOS: tuple[str, ...] = ("papa", "trigo", "manzano")

# ---------------------------------------------------------------------------
# Severidad
# ---------------------------------------------------------------------------
Severidad = Literal["alta", "media", "baja"]

SEVERIDAD_ALTA: Severidad = "alta"
SEVERIDAD_MEDIA: Severidad = "media"
SEVERIDAD_BAJA: Severidad = "baja"

SEVERIDAD_ORDEN: dict[str, int] = {"alta": 0, "media": 1, "baja": 2}

# ---------------------------------------------------------------------------
# Planes
# ---------------------------------------------------------------------------
PLAN_FREE = "free"
PLAN_PREMIUM = "premium"
PLANES_VALIDOS = (PLAN_FREE, PLAN_PREMIUM)

# ---------------------------------------------------------------------------
# Tipos de alerta
# ---------------------------------------------------------------------------
TipoAlerta = Literal["helada", "lluvia_intensa", "viento_fuerte", "granizo"]

ALERTA_HELADA: TipoAlerta = "helada"
ALERTA_LLUVIA_INTENSA: TipoAlerta = "lluvia_intensa"
ALERTA_VIENTO_FUERTE: TipoAlerta = "viento_fuerte"
ALERTA_GRANIZO: TipoAlerta = "granizo"

# ---------------------------------------------------------------------------
# Acciones de recomendación
# ---------------------------------------------------------------------------
ACCION_FUMIGAR = "fumigar"
ACCION_REGAR = "regar"
ACCION_SEMBRAR = "sembrar"
ACCION_COSECHAR = "cosechar"

# ---------------------------------------------------------------------------
# Recomendaciones (valores posibles)
# ---------------------------------------------------------------------------
REC_SI = "Sí"
REC_NO = "No"
REC_PRECAUCION = "Precaución"
REC_MONITOREAR = "Monitorear"
REC_ESPERAR = "Esperar"

# ---------------------------------------------------------------------------
# Confianza
# ---------------------------------------------------------------------------
CONFIANZA_ALTA = "alta"
CONFIANZA_MEDIA = "media"
CONFIANZA_BAJA = "baja"
