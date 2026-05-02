"""Cliente ODEPA — precios mayoristas de productos agrícolas en Chile.

Scraping liviano de precios de referencia. Con fallback a datos simulados
basados en precios reales del mercado chileno (actualizados periódicamente).

Fuentes:
- ODEPA: https://www.odepa.gob.cl/precios/precios-mayoristas
- Cotizaciones de referencia por temporada
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger("wenuke.odepa")

# Precios de referencia por producto (CLP/kg) — actualizados cada temporada
# Datos base: promedios mercado Lo Valledor, Santiago
PRECIOS_REFERENCIA: dict[str, dict] = {
    "papa": {
        "nombre": "Papa",
        "unidad": "kg",
        "precio_actual": 650,
        "precio_min_3m": 450,
        "precio_max_3m": 900,
        "mercado": "Lo Valledor, Santiago",
        "tendencia": "estable",
        "nota": "Precio de referencia. Alta variabilidad según variedad (désirée, rosada, negra).",
    },
    "trigo": {
        "nombre": "Trigo",
        "unidad": "kg",
        "precio_actual": 280,
        "precio_min_3m": 250,
        "precio_max_3m": 310,
        "mercado": "Bolsa de Productos, Santiago",
        "tendencia": "alza",
        "nota": "Cotización bolsa. Precio panadero ~$320/kg. Temporada de cosecha diciembre-enero baja el precio.",
    },
    "manzano": {
        "nombre": "Manzana",
        "unidad": "kg",
        "precio_actual": 850,
        "precio_min_3m": 700,
        "precio_max_3m": 1200,
        "mercado": "Lo Valledor, Santiago",
        "tendencia": "estable",
        "nota": "Variedad Fuji. Gala ~$100 menos. Pink Lady ~$200 más. Calidad exportación paga 2-3x.",
    },
}


class ODEPAClient:
    """Cliente de precios ODEPA con fallback a datos de referencia."""

    URL_ODEPA = "https://www.odepa.gob.cl/precios/precios-mayoristas"

    def __init__(self):
        self.cache: dict[str, dict] = {}
        self.cache_ts: dict[str, float] = {}

    async def fetch_precios(self, producto: str) -> dict:
        """Obtiene precio actual y referencia para un producto. Con cache de 6h."""
        import time

        if producto in self.cache:
            ts = self.cache_ts.get(producto, 0)
            if time.time() - ts < 6 * 3600:
                return self.cache[producto]

        # Intentar scraping real
        try:
            precios = await self._scrape_odepa(producto)
            if precios:
                precios["producto"] = producto
                self.cache[producto] = precios
                self.cache_ts[producto] = time.time()
                return precios
        except Exception as e:
            logger.warning(f"Scraping ODEPA falló para {producto}: {e}")

        # Fallback a datos de referencia
        ref = PRECIOS_REFERENCIA.get(producto)
        if ref:
            ref = dict(ref)  # no mutar el original
            ref["producto"] = producto
            ref["fuente"] = "referencia"
            ref["actualizado"] = datetime.now().isoformat()
            return ref

        return {"error": f"Producto '{producto}' no disponible", "fuente": "ninguna"}

    async def _scrape_odepa(self, producto: str) -> dict | None:
        """Retorna None — scraping real no implementado.

        Nota: El scraping real requiere parseo de la estructura HTML específica
        de ODEPA, que cambia frecuentemente. Para MVP de portafolio usamos datos
        de referencia (PRECIOS_REFERENCIA) como fuente primaria.
        """
        logger.debug(
            f"Scraping ODEPA omitido para '{producto}' — usando datos de referencia"
        )
        return None

    async def fetch_todos(self) -> list[dict]:
        """Obtiene precios de todos los productos soportados en paralelo."""
        productos = ["papa", "trigo", "manzano"]
        resultados = await asyncio.gather(
            *(self.fetch_precios(p) for p in productos)
        )
        return list(resultados)


# Singleton
odepa_client = ODEPAClient()
