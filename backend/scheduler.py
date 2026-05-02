"""Scheduler liviano para envío periódico de alertas. Sin dependencias externas."""

import asyncio
import logging

logger = logging.getLogger("wenuke.scheduler")


class AlertScheduler:
    """Ejecuta chequeo de alertas cada N horas usando asyncio."""

    def __init__(self, intervalo_horas: int = 6):
        self.intervalo_horas = intervalo_horas
        self._tarea: asyncio.Task | None = None

    async def _chequear_y_enviar(self):
        """Wrapper que ejecuta el servicio de alertas compartido."""
        from servicio_alertas import ejecutar_chequeo_alertas

        logger.info("Scheduler: iniciando chequeo de alertas...")
        try:
            resultado = await ejecutar_chequeo_alertas()
            logger.info(
                f"Scheduler: {resultado['enviadas']} alertas enviadas a "
                f"{resultado['usuarios_afectados']} usuarios "
                f"(fallidos: {resultado['envios_fallidos']}, "
                f"whatsapp_activo: {resultado['whatsapp_activo']})"
            )
        except Exception as e:
            logger.error(f"Scheduler: error en chequeo — {e}")

    async def _loop(self):
        """Loop infinito con sleep entre chequeos."""
        logger.info(f"Scheduler iniciado — cada {self.intervalo_horas}h")
        while True:
            await asyncio.sleep(self.intervalo_horas * 3600)
            await self._chequear_y_enviar()

    def iniciar(self):
        """Arranca el scheduler en background."""
        if self._tarea and not self._tarea.done():
            logger.warning("Scheduler ya estaba corriendo")
            return

        self._tarea = asyncio.create_task(self._loop())
        logger.info("Scheduler lanzado en background")

    def detener(self):
        """Frena el scheduler."""
        if self._tarea and not self._tarea.done():
            self._tarea.cancel()
            logger.info("Scheduler detenido")


# Singleton
alert_scheduler = AlertScheduler(intervalo_horas=6)
