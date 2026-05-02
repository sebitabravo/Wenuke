"""Capa de persistencia — SQLite con soporte multi-parcela y planes."""

import asyncio
import functools
import secrets
import sqlite3

from config import config

# NOTA: SQLite es síncrono. Las consultas breves no bloquean significativamente
# el event loop de FastAPI. Para producción con alta concurrencia, migrar a
# aiosqlite o Turso.
_executor = None


def _get_executor():
    global _executor
    if _executor is None:
        import concurrent.futures
        _executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    return _executor


async def _run_async(func, *args, **kwargs):
    """Ejecuta función síncrona en thread pool para no bloquear event loop."""
    loop = asyncio.get_running_loop()
    wrapped = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(_get_executor(), wrapped)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(config.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Crear tablas si no existen — idempotente. Soporta migración desde schema viejo."""
    conn = get_db()
    conn.executescript("""
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
    """)

    # Migración: agregar columnas que puedan faltar de schema viejo
    try:
        conn.execute("ALTER TABLE usuarios ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
    except sqlite3.OperationalError:
        pass  # Ya existe

    try:
        conn.execute("ALTER TABLE usuarios ADD COLUMN token TEXT")
    except sqlite3.OperationalError:
        pass

    # Migrar cultivos que referencian usuario_id → parcela_id si la tabla parcelas es nueva
    # Si hay datos en cultivos con usuario_id, crear parcelas automáticamente
    try:
        conn.execute("ALTER TABLE cultivos ADD COLUMN parcela_id INTEGER REFERENCES parcelas(id)")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def _generar_token() -> str:
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

def registrar_usuario(data: dict) -> dict:
    """Registra usuario, parcela inicial y cultivos. Retorna dict con id y token."""
    conn = get_db()
    token = _generar_token()
    conn.execute("BEGIN")
    try:
        cur = conn.execute(
            "INSERT INTO usuarios (whatsapp, nombre, plan, token) VALUES (?, ?, ?, ?)",
            (data["whatsapp"], data["nombre"], data.get("plan", "free"), token),
        )
        usuario_id = cur.lastrowid

        # Crear parcela inicial
        cur = conn.execute(
            "INSERT INTO parcelas (usuario_id, nombre, lat, lon) VALUES (?, ?, ?, ?)",
            (usuario_id, data.get("nombre_parcela", "Parcela 1"), data["lat"], data["lon"]),
        )
        parcela_id: int = cur.lastrowid  # type: ignore[assignment]
        assert parcela_id is not None

        for cultivo in data.get("cultivos", ["general"]):
            conn.execute(
                "INSERT INTO cultivos (parcela_id, tipo) VALUES (?, ?)",
                (parcela_id, cultivo),
            )

        conn.commit()
        return {"usuario_id": usuario_id, "token": token, "parcela_id": parcela_id}
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError(f"WhatsApp {data['whatsapp']} ya registrado")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_usuario_por_token(token: str) -> dict | None:
    """Obtiene usuario por token de autenticación."""
    conn = get_db()
    row = conn.execute("SELECT * FROM usuarios WHERE token = ?", (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


def actualizar_plan(usuario_id: int, plan: str) -> dict:
    """Cambia el plan de un usuario. Retorna datos actualizados."""
    conn = get_db()
    conn.execute("UPDATE usuarios SET plan = ? WHERE id = ?", (plan, usuario_id))
    conn.commit()
    row = conn.execute("SELECT id, nombre, whatsapp, plan FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def obtener_todos_los_usuarios() -> list[dict]:
    """Obtiene todos los usuarios con sus parcelas y cultivos."""
    conn = get_db()
    usuarios = conn.execute("SELECT * FROM usuarios").fetchall()
    resultado = []
    for u in usuarios:
        u = dict(u)
        u["parcelas"] = _obtener_parcelas_usuario(conn, u["id"])
        resultado.append(u)
    conn.close()
    return resultado


# ---------------------------------------------------------------------------
# Parcelas
# ---------------------------------------------------------------------------

def _obtener_parcelas_usuario(conn: sqlite3.Connection, usuario_id: int) -> list[dict]:
    """Helper interno — obtiene parcelas con cultivos (dos queries, sin N+1)."""
    parcelas = conn.execute(
        "SELECT * FROM parcelas WHERE usuario_id = ?", (usuario_id,)
    ).fetchall()

    if not parcelas:
        return []

    # Cargar todos los cultivos en una sola query
    parcelas_ids = [p["id"] for p in parcelas]
    placeholders = ','.join('?' * len(parcelas_ids))
    cultivos_raw = conn.execute(
        f"SELECT parcela_id, tipo FROM cultivos WHERE parcela_id IN ({placeholders})",
        parcelas_ids
    ).fetchall()

    # Indexar cultivos por parcela_id
    cultivos_por_parcela: dict[int, list[str]] = {}
    for c in cultivos_raw:
        cultivos_por_parcela.setdefault(c["parcela_id"], []).append(c["tipo"])

    resultado = []
    for p in parcelas:
        p = dict(p)
        p["cultivos"] = cultivos_por_parcela.get(p["id"], [])
        resultado.append(p)
    return resultado


def obtener_parcelas(usuario_id: int) -> list[dict]:
    """Obtiene todas las parcelas de un usuario con sus cultivos."""
    conn = get_db()
    resultado = _obtener_parcelas_usuario(conn, usuario_id)
    conn.close()
    return resultado


def agregar_parcela(usuario_id: int, data: dict) -> int:
    """Agrega una parcela nueva. Premium — sin límite. Free — máximo 1."""
    conn = get_db()

    # Validar límite plan free
    usuario = conn.execute("SELECT plan FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    if not usuario:
        conn.close()
        raise ValueError("Usuario no encontrado")

    if usuario["plan"] == "free":
        count = conn.execute(
            "SELECT COUNT(*) as n FROM parcelas WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()["n"]
        if count >= 1:
            conn.close()
            raise ValueError("Plan gratuito limitado a 1 parcela. Subí a premium para múltiples parcelas.")

    conn.execute("BEGIN")
    try:
        cur = conn.execute(
            "INSERT INTO parcelas (usuario_id, nombre, lat, lon) VALUES (?, ?, ?, ?)",
            (usuario_id, data["nombre"], data["lat"], data["lon"]),
        )
        parcela_id: int = cur.lastrowid  # type: ignore[assignment]
        assert parcela_id is not None

        for cultivo in data.get("cultivos", ["general"]):
            conn.execute(
                "INSERT INTO cultivos (parcela_id, tipo) VALUES (?, ?)",
                (parcela_id, cultivo),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return parcela_id


def eliminar_parcela(parcela_id: int, usuario_id: int) -> bool:
    """Elimina una parcela. Retorna True si se eliminó."""
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM parcelas WHERE id = ? AND usuario_id = ?",
        (parcela_id, usuario_id),
    )
    conn.commit()
    eliminado = cur.rowcount > 0
    conn.close()
    return eliminado


# ---------------------------------------------------------------------------
# Consultas para alertas (por parcela)
# ---------------------------------------------------------------------------

def obtener_usuarios_con_cultivo(tipo: str) -> list[dict]:
    """Obtiene todos los usuarios con parcelas que tengan un cultivo específico."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT DISTINCT u.id, u.nombre, u.whatsapp, p.lat, p.lon, p.id as parcela_id
        FROM usuarios u
        JOIN parcelas p ON p.usuario_id = u.id
        JOIN cultivos c ON c.parcela_id = p.id
        WHERE c.tipo = ?
        """,
        (tipo,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------

def registrar_alerta(usuario_id: int, tipo: str, mensaje: str):
    """Registra alerta enviada para auditoría."""
    conn = get_db()
    conn.execute(
        "INSERT INTO alertas_enviadas (usuario_id, tipo, mensaje) VALUES (?, ?, ?)",
        (usuario_id, tipo, mensaje),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Wrappers asíncronos — usar en endpoints async de FastAPI
# ---------------------------------------------------------------------------

async def registrar_usuario_async(data: dict) -> dict:
    return await _run_async(registrar_usuario, data)


async def obtener_usuario_por_token_async(token: str) -> dict | None:
    return await _run_async(obtener_usuario_por_token, token)


async def obtener_parcelas_async(usuario_id: int) -> list[dict]:
    return await _run_async(obtener_parcelas, usuario_id)


async def agregar_parcela_async(usuario_id: int, data: dict) -> int:
    return await _run_async(agregar_parcela, usuario_id, data)


async def eliminar_parcela_async(parcela_id: int, usuario_id: int) -> bool:
    return await _run_async(eliminar_parcela, parcela_id, usuario_id)


async def actualizar_plan_async(usuario_id: int, plan: str) -> dict:
    return await _run_async(actualizar_plan, usuario_id, plan)


async def obtener_usuarios_con_cultivo_async(tipo: str) -> list[dict]:
    return await _run_async(obtener_usuarios_con_cultivo, tipo)


async def registrar_alerta_async(usuario_id: int, tipo: str, mensaje: str):
    return await _run_async(registrar_alerta, usuario_id, tipo, mensaje)
