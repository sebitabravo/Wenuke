"""Configuración de logging estructurado.

Usa structlog si está instalado, con fallback a logging estándar.
En producción (Vercel): formato JSON para agregación.
En desarrollo: consola legible por humanos.
"""

import logging
import os
import sys

_formato_prod = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_formato_dev = "%(levelname)-5s [%(name)s] %(message)s"


def configurar_logging() -> None:
    """Configura logging raíz con formato adecuado al entorno."""
    es_prod = os.getenv("VERCEL") == "1" or os.getenv("ENV") == "production"

    nivel = logging.DEBUG if os.getenv("DEBUG") else logging.INFO
    formato = _formato_prod if es_prod else _formato_dev

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(formato, datefmt="%Y-%m-%dT%H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(nivel)
    # Evitar duplicados si ya se configuró
    if not root.handlers:
        root.addHandler(handler)

    # Silenciar logs ruidosos de librerías
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Intentar structlog para JSON estructurado en prod
    if es_prod:
        try:
            import structlog

            structlog.configure(
                processors=[
                    structlog.stdlib.filter_by_level,
                    structlog.stdlib.add_logger_name,
                    structlog.stdlib.add_log_level,
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.JSONRenderer(),
                ],
                context_class=dict,
                logger_factory=structlog.stdlib.LoggerFactory(),
                wrapper_class=structlog.stdlib.BoundLogger,
                cache_logger_on_first_use=True,
            )
        except ImportError:
            pass  # structlog no instalado, usar logging estándar


def obtener_logger(nombre: str) -> logging.Logger:
    """Obtiene logger configurado para un módulo específico."""
    return logging.getLogger(nombre)
