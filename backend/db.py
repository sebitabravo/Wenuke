"""Capa de persistencia — SQLite con soporte multi-parcela y planes."""

import secrets
import sqlite3
from config import config


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
        parcela_id = cur.lastrowid

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
    """Helper interno — obtiene parcelas con cultivos."""
    parcelas = conn.execute(
        "SELECT * FROM parcelas WHERE usuario_id = ?", (usuario_id,)
    ).fetchall()
    resultado = []
    for p in parcelas:
        p = dict(p)
        cultivos = conn.execute(
            "SELECT tipo FROM cultivos WHERE parcela_id = ?", (p["id"],)
        ).fetchall()
        p["cultivos"] = [c["tipo"] for c in cultivos]
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

    cur = conn.execute(
        "INSERT INTO parcelas (usuario_id, nombre, lat, lon) VALUES (?, ?, ?, ?)",
        (usuario_id, data["nombre"], data["lat"], data["lon"]),
    )
    parcela_id = cur.lastrowid

    for cultivo in data.get("cultivos", ["general"]):
        conn.execute(
            "INSERT INTO cultivos (parcela_id, tipo) VALUES (?, ?)",
            (parcela_id, cultivo),
        )

    conn.commit()
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
