"""Capa de persistencia — dual backend: Turso (serverless) + aiosqlite (local).

Backend automático:
- Si TURSO_DATABASE_URL y TURSO_AUTH_TOKEN están definidos → Turso HTTP.
- Si no → aiosqlite local (usa DB_PATH, default "wenuke.db").

Todas las funciones públicas son async nativas — sin ThreadPoolExecutor.
"""

from __future__ import annotations

import secrets
from typing import Any

from config import config

# ---------------------------------------------------------------------------
# Import condicional de libsql-experimental (solo necesario en producción)
# ---------------------------------------------------------------------------
try:
    import libsql_experimental as libsql  # type: ignore[import-not-found]

    _HAS_LIBSQL = True
except ImportError:  # pragma: no cover — solo en dev local sin libsql
    libsql = None  # type: ignore[assignment]
    _HAS_LIBSQL = False

# ---------------------------------------------------------------------------
# Singleton del backend
# ---------------------------------------------------------------------------
_use_turso: bool = bool(config.turso_database_url and config.turso_auth_token)
_db: _TursoBackend | _AiosqliteBackend | None = None


async def _get_db():
    """Lazy singleton — resuelve el backend y conecta una sola vez."""
    global _db
    if _db is not None:
        return _db

    if _use_turso:
        if not _HAS_LIBSQL:
            raise RuntimeError(
                "TURSO_DATABASE_URL configurada pero libsql-experimental no está instalado. "
                "Ejecutá: pip install libsql-experimental"
            )
        _db = await _TursoBackend.connect(
            config.turso_database_url, config.turso_auth_token
        )
    else:
        _db = await _AiosqliteBackend.connect(config.database_path)

    return _db


# ======================================================================
# Backend: Turso (HTTP → libsql-experimental)
# ======================================================================


class _TursoBackend:
    """Cliente Turso sobre HTTP. Cada statement es atómico."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @classmethod
    async def connect(cls, url: str, token: str):
        client = libsql.connect(url, auth_token=token)  # type: ignore[union-attr]
        return cls(client)

    # -- queries ----------------------------------------------------------

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        """SELECT → lista de dicts."""
        result = await self._client.execute(sql, params)
        cols = result.columns
        return [dict(zip(cols, row)) for row in result.rows]

    async def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        """SELECT → un dict o None."""
        rows = await self.fetchall(sql, params)
        return rows[0] if rows else None

    async def execute(self, sql: str, params: tuple = ()) -> None:
        """INSERT / UPDATE / DELETE sin retorno."""
        await self._client.execute(sql, params)

    async def insert(self, sql: str, params: tuple = ()) -> int:
        """INSERT → last_insert_rowid."""
        result = await self._client.execute(sql, params)
        return result.last_insert_rowid

    async def executescript(self, script: str) -> None:
        """Ejecuta múltiples statements separados por ; (init_db)."""
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if stmt:
                await self._client.execute(stmt)

    # -- transacciones ----------------------------------------------------

    async def begin(self) -> None:
        """No-op en Turso — cada statement es atómico por HTTP."""
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    # -- cleanup ----------------------------------------------------------

    async def close(self) -> None:
        pass  # HTTP client no requiere close explícito


# ======================================================================
# Backend: aiosqlite (local)
# ======================================================================


class _AiosqliteBackend:
    """Cliente SQLite local async vía aiosqlite."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    @classmethod
    async def connect(cls, path: str):
        import aiosqlite  # type: ignore[import-not-found]

        conn = await aiosqlite.connect(path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        return cls(conn)

    # -- queries ----------------------------------------------------------

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def execute(self, sql: str, params: tuple = ()) -> None:
        """Ejecuta statement sin commit automático — el caller gestiona la tx."""
        await self._conn.execute(sql, params)

    async def insert(self, sql: str, params: tuple = ()) -> int:
        """INSERT → lastrowid. No commitea — el caller debe llamar commit()."""
        cursor = await self._conn.execute(sql, params)
        return cursor.lastrowid

    async def executescript(self, script: str) -> None:
        await self._conn.executescript(script)

    # -- transacciones ----------------------------------------------------

    async def begin(self) -> None:
        await self._conn.execute("BEGIN")

    async def commit(self) -> None:
        await self._conn.commit()

    async def rollback(self) -> None:
        await self._conn.rollback()

    # -- cleanup ----------------------------------------------------------

    async def close(self) -> None:
        await self._conn.close()


# ======================================================================
# Helpers
# ======================================================================


def _generar_token() -> str:
    return secrets.token_urlsafe(32)


# ======================================================================
# Schema — init_db
# ======================================================================


async def init_db() -> None:
    """Crear tablas si no existen — idempotente. Soporta migración desde schema viejo."""
    db = await _get_db()
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            whatsapp TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free' CHECK(plan IN ('free', 'premium')),
            token TEXT UNIQUE,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS parcelas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nombre TEXT NOT NULL DEFAULT 'Parcela 1',
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS cultivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parcela_id INTEGER NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('papa', 'trigo', 'manzano', 'general')),
            FOREIGN KEY (parcela_id) REFERENCES parcelas(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS alertas_enviadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            enviado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        );
    """
    )

    # Migración: agregar columnas que puedan faltar de schema viejo
    try:
        await db.execute("ALTER TABLE usuarios ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
    except Exception:  # pragma: no cover — solo en migración
        pass  # Ya existe

    try:
        await db.execute("ALTER TABLE usuarios ADD COLUMN token TEXT")
    except Exception:  # pragma: no cover
        pass

    try:
        await db.execute(
            "ALTER TABLE cultivos ADD COLUMN parcela_id INTEGER REFERENCES parcelas(id)"
        )
    except Exception:  # pragma: no cover
        pass


# ======================================================================
# Usuarios
# ======================================================================


async def registrar_usuario(data: dict) -> dict:
    """Registra usuario, parcela inicial y cultivos. Retorna dict con id y token."""
    db = await _get_db()
    token = _generar_token()
    await db.begin()
    try:
        usuario_id = await db.insert(
            "INSERT INTO usuarios (whatsapp, nombre, plan, token) VALUES (?, ?, ?, ?)",
            (data["whatsapp"], data["nombre"], data.get("plan", "free"), token),
        )

        parcela_id = await db.insert(
            "INSERT INTO parcelas (usuario_id, nombre, lat, lon) VALUES (?, ?, ?, ?)",
            (
                usuario_id,
                data.get("nombre_parcela", "Parcela 1"),
                data["lat"],
                data["lon"],
            ),
        )

        for cultivo in data.get("cultivos", ["general"]):
            await db.execute(
                "INSERT INTO cultivos (parcela_id, tipo) VALUES (?, ?)",
                (parcela_id, cultivo),
            )

        await db.commit()
        return {"usuario_id": usuario_id, "token": token, "parcela_id": parcela_id}
    except Exception:
        await db.rollback()
        # Re-lanzar IntegrityError como ValueError para mantener compatibilidad
        if _es_integrity_error():
            raise ValueError(f"WhatsApp {data['whatsapp']} ya registrado")
        raise


async def obtener_usuario_por_token(token: str) -> dict | None:
    """Obtiene usuario por token de autenticación."""
    db = await _get_db()
    return await db.fetchone("SELECT * FROM usuarios WHERE token = ?", (token,))


async def actualizar_plan(usuario_id: int, plan: str) -> dict:
    """Cambia el plan de un usuario. Retorna datos actualizados."""
    db = await _get_db()
    await db.execute("UPDATE usuarios SET plan = ? WHERE id = ?", (plan, usuario_id))
    await db.commit()
    return await db.fetchone(
        "SELECT id, nombre, whatsapp, plan FROM usuarios WHERE id = ?",
        (usuario_id,),
    ) or {}


async def obtener_todos_los_usuarios() -> list[dict]:
    """Obtiene todos los usuarios con sus parcelas y cultivos."""
    db = await _get_db()
    usuarios = await db.fetchall("SELECT * FROM usuarios")
    resultado = []
    for u in usuarios:
        u["parcelas"] = await _obtener_parcelas_usuario(db, u["id"])
        resultado.append(u)
    return resultado


# ======================================================================
# Parcelas
# ======================================================================


async def _obtener_parcelas_usuario(db, usuario_id: int) -> list[dict]:
    """Helper interno — obtiene parcelas con cultivos (sin N+1)."""
    parcelas = await db.fetchall(
        "SELECT * FROM parcelas WHERE usuario_id = ?", (usuario_id,)
    )

    if not parcelas:
        return []

    # Cargar todos los cultivos en una sola query (sin N+1)
    parcelas_ids = [p["id"] for p in parcelas]
    placeholders = ",".join("?" * len(parcelas_ids))
    cultivos_raw = await db.fetchall(
        f"SELECT parcela_id, tipo FROM cultivos WHERE parcela_id IN ({placeholders})",
        tuple(parcelas_ids),
    )

    # Indexar cultivos por parcela_id
    cultivos_por_parcela: dict[int, list[str]] = {}
    for c in cultivos_raw:
        cultivos_por_parcela.setdefault(c["parcela_id"], []).append(c["tipo"])

    resultado = []
    for p in parcelas:
        p["cultivos"] = cultivos_por_parcela.get(p["id"], [])
        resultado.append(p)
    return resultado


async def obtener_parcelas(usuario_id: int) -> list[dict]:
    """Obtiene todas las parcelas de un usuario con sus cultivos."""
    db = await _get_db()
    return await _obtener_parcelas_usuario(db, usuario_id)


async def agregar_parcela(usuario_id: int, data: dict) -> int:
    """Agrega una parcela nueva. Premium — sin límite. Free — máximo 1."""
    db = await _get_db()

    # Validar límite plan free
    usuario = await db.fetchone(
        "SELECT plan FROM usuarios WHERE id = ?", (usuario_id,)
    )
    if not usuario:
        raise ValueError("Usuario no encontrado")

    if usuario["plan"] == "free":
        row = await db.fetchone(
            "SELECT COUNT(*) as n FROM parcelas WHERE usuario_id = ?",
            (usuario_id,),
        )
        if row and row["n"] >= 1:
            raise ValueError(
                "Plan gratuito limitado a 1 parcela. Subí a premium para múltiples parcelas."
            )

    await db.begin()
    try:
        parcela_id = await db.insert(
            "INSERT INTO parcelas (usuario_id, nombre, lat, lon) VALUES (?, ?, ?, ?)",
            (usuario_id, data["nombre"], data["lat"], data["lon"]),
        )

        for cultivo in data.get("cultivos", ["general"]):
            await db.execute(
                "INSERT INTO cultivos (parcela_id, tipo) VALUES (?, ?)",
                (parcela_id, cultivo),
            )

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return parcela_id


async def eliminar_parcela(parcela_id: int, usuario_id: int) -> bool:
    """Elimina una parcela. Retorna True si se eliminó."""
    db = await _get_db()
    await db.execute(
        "DELETE FROM parcelas WHERE id = ? AND usuario_id = ?",
        (parcela_id, usuario_id),
    )
    await db.commit()
    # Verificar si se eliminó algo — consultar si aún existe
    row = await db.fetchone(
        "SELECT id FROM parcelas WHERE id = ?", (parcela_id,)
    )
    return row is None


# ======================================================================
# Consultas para alertas (por parcela)
# ======================================================================


async def obtener_usuarios_con_cultivo(tipo: str) -> list[dict]:
    """Obtiene todos los usuarios con parcelas que tengan un cultivo específico."""
    db = await _get_db()
    return await db.fetchall(
        """
        SELECT DISTINCT u.id, u.nombre, u.whatsapp, p.lat, p.lon, p.id as parcela_id
        FROM usuarios u
        JOIN parcelas p ON p.usuario_id = u.id
        JOIN cultivos c ON c.parcela_id = p.id
        WHERE c.tipo = ?
        """,
        (tipo,),
    )


# ======================================================================
# Alertas
# ======================================================================


async def registrar_alerta(usuario_id: int, tipo: str, mensaje: str) -> None:
    """Registra alerta enviada para auditoría — fire and forget."""
    db = await _get_db()
    await db.execute(
        "INSERT INTO alertas_enviadas (usuario_id, tipo, mensaje) VALUES (?, ?, ?)",
        (usuario_id, tipo, mensaje),
    )
    await db.commit()


# ======================================================================
# Helpers privados
# ======================================================================


def _es_integrity_error() -> bool:
    """Determina si la excepción activa es una violación de unicidad."""
    import sys

    exc = sys.exc_info()[1]
    if exc is None:
        return False
    msg = str(exc).lower()
    return "unique" in msg or "integrity" in msg or "unicidad" in msg
