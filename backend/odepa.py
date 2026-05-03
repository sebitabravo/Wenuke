"""Cliente ODEPA — scraping de precios mayoristas desde el sitio oficial."""

import logging
import re
import time
from datetime import datetime

logger = logging.getLogger("wenuke.odepa")

# Precios de referencia por producto (CLP/kg) — actualizados cada temporada
# Datos base: promedios mercado Lo Valledor, Santiago (fallback si scraping falla)
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
    """Cliente de precios ODEPA con scraping real y fallback a datos de referencia."""

    URL_ODEPA = "https://www.odepa.gob.cl/precios/precios-mayoristas"

    def __init__(self):
        self.cache: dict[str, dict] = {}
        self.cache_ts: dict[str, float] = {}

    async def fetch_precios(self, producto: str) -> dict:
        """Obtiene precio actual y referencia para un producto. Con cache de 6h."""
        if producto in self.cache:
            ts = self.cache_ts.get(producto, 0)
            if time.time() - ts < 6 * 3600:
                return self.cache[producto]

        # Intentar scraping real
        try:
            precios = await self._scrape_odepa(producto)
            if precios:
                precios["producto"] = producto
                precios["fuente"] = "scraping"
                precios["actualizado"] = datetime.now().isoformat()
                self.cache[producto] = precios
                self.cache_ts[producto] = time.time()
                return precios
        except Exception as e:
            logger.warning(f"Scraping ODEPA falló para {producto}: {e}")

        # Fallback a datos de referencia
        ref = PRECIOS_REFERENCIA.get(producto)
        if ref:
            ref = dict(ref)
            ref["producto"] = producto
            ref["fuente"] = "referencia"
            ref["actualizado"] = datetime.now().isoformat()
            self.cache[producto] = ref
            self.cache_ts[producto] = time.time()
            return ref

        return {"error": f"Producto '{producto}' no disponible", "fuente": "ninguna"}

    async def _scrape_odepa(self, producto: str) -> dict | None:
        """Scraping real del sitio de precios mayoristas de ODEPA.

        Usa httpx para fetch + expresiones regulares para extraer datos
        de la tabla de precios. Si el sitio cambia su estructura, retorna None
        y el caller usa fallback.
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    self.URL_ODEPA,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (compatible; Werken-mapu/1.0; "
                            "+https://github.com/sebitabravo/Wenuke)"
                        ),
                    },
                    follow_redirects=True,
                )
                r.raise_for_status()
                html = r.text
        except httpx.HTTPError as e:
            logger.error(f"HTTP error al scrapear ODEPA: {e}")
            return None

        # Mapeo de nombre de producto a cómo aparece en ODEPA
        nombres_odepa = {
            "papa": ["papa", "papas"],
            "trigo": ["trigo"],
            "manzano": ["manzana", "manzanas"],
        }

        nombres = nombres_odepa.get(producto, [producto])
        datos = None

        for nombre in nombres:
            # Buscar fila de tabla que contenga el nombre del producto y precios
            patron = re.compile(
                rf"<td[^>]*>{re.escape(nombre)}</td>\s*"
                r"<td[^>]*>\s*\$?\s*([\d.]+)\s*</td>\s*"
                r"<td[^>]*>\s*\$?\s*([\d.]+)\s*</td>\s*"
                r"<td[^>]*>\s*\$?\s*([\d.]+)\s*</td>\s*"
                r"<td[^>]*>\s*([^<]+)\s*</td>",
                re.IGNORECASE,
            )
            match = patron.search(html)
            if match:
                try:
                    precio_actual = float(match.group(1).replace(".", "").replace(",", "."))
                    precio_min = float(match.group(2).replace(".", "").replace(",", "."))
                    precio_max = float(match.group(3).replace(".", "").replace(",", "."))
                    mercado = match.group(4).strip()
                    datos = {
                        "nombre": nombre.capitalize(),
                        "unidad": "kg",
                        "precio_actual": precio_actual,
                        "precio_min_3m": precio_min,
                        "precio_max_3m": precio_max,
                        "mercado": mercado,
                        "tendencia": _calcular_tendencia(precio_actual, precio_min, precio_max),
                        "nota": f"Precio obtenido de ODEPA — {mercado}",
                    }
                    break
                except (ValueError, IndexError):
                    continue

        if datos:
            logger.info(f"Scraping ODEPA exitoso para {producto}: ${datos['precio_actual']}/kg")
        else:
            logger.debug(f"No se encontró {producto} en la estructura actual de ODEPA")

        return datos

    async def fetch_todos(self) -> list[dict]:
        """Obtiene precios de todos los productos soportados en paralelo."""
        import asyncio

        productos = ["papa", "trigo", "manzano"]
        resultados = await asyncio.gather(
            *(self.fetch_precios(p) for p in productos)
        )
        return list(resultados)


def _calcular_tendencia(actual: float, min_3m: float, max_3m: float) -> str:
    """Calcula tendencia basada en posición del precio actual en el rango 3 meses."""
    if max_3m == min_3m:
        return "estable"
    pos = (actual - min_3m) / (max_3m - min_3m)
    if pos > 0.7:
        return "alza"
    elif pos < 0.3:
        return "baja"
    return "estable"


# Singleton
odepa_client = ODEPAClient()
