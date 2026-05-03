"""Tests de integración para capa de persistencia — usa aiosqlite con DB temporal."""

import os
import sys
from pathlib import Path

import pytest

# Asegurar que backend/ está en sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Forzar aiosqlite (no Turso) durante tests
os.environ.pop("TURSO_DATABASE_URL", None)
os.environ.pop("TURSO_AUTH_TOKEN", None)

from config import config  # noqa: E402

config.database_path = ":memory:"  # type: ignore[attr-defined]

import db as db_mod  # noqa: E402


@pytest.fixture(autouse=True)
async def _reset_db():
    """Resetea el singleton de base de datos entre tests."""
    db_mod._db = None
    db_mod._use_turso = False
    config.database_path = ":memory:"  # type: ignore[attr-defined]
    await db_mod.init_db()
    yield
    if db_mod._db is not None:
        try:
            await db_mod._db.close()
        except Exception:
            pass
    db_mod._db = None


class TestRegistrarUsuario:
    async def test_registro_exitoso_retorna_token_y_parcela(self):
        resultado = await db_mod.registrar_usuario({
            "whatsapp": "+56912345678",
            "nombre": "Juan Test",
            "lat": -38.7359,
            "lon": -72.5904,
            "cultivos": ["papa", "trigo"],
            "plan": "free",
        })

        assert "token" in resultado
        assert len(resultado["token"]) >= 32
        assert resultado["parcela_id"] > 0
        assert resultado["usuario_id"] > 0

    async def test_whatsapp_duplicado_lanza_valueerror(self):
        await db_mod.registrar_usuario({
            "whatsapp": "+56987654321",
            "nombre": "Primero",
            "lat": -38.7,
            "lon": -72.6,
            "cultivos": ["general"],
        })

        with pytest.raises(ValueError, match="ya registrado"):
            await db_mod.registrar_usuario({
                "whatsapp": "+56987654321",
                "nombre": "Duplicado",
                "lat": -38.7,
                "lon": -72.6,
                "cultivos": ["general"],
            })

    async def test_token_hash_no_se_almacena_en_plano(self):
        resultado = await db_mod.registrar_usuario({
            "whatsapp": "+56911111111",
            "nombre": "Hash Test",
            "lat": -38.7,
            "lon": -72.6,
            "cultivos": ["general"],
        })

        token_plano = resultado["token"]
        db = await db_mod._get_db()
        usuario = await db.fetchone(
            "SELECT token_hash FROM usuarios WHERE id = ?",
            (resultado["usuario_id"],),
        )
        assert usuario is not None
        assert usuario["token_hash"] is not None
        assert usuario["token_hash"] != token_plano
        assert len(usuario["token_hash"]) == 64


class TestAuth:
    async def test_obtener_usuario_por_token_hash(self):
        resultado = await db_mod.registrar_usuario({
            "whatsapp": "+56922222222",
            "nombre": "Auth Test",
            "lat": -38.7,
            "lon": -72.6,
            "cultivos": ["general"],
        })

        token_plano = resultado["token"]
        token_hash = db_mod._hash_token(token_plano)

        usuario = await db_mod.obtener_usuario_por_token_hash(token_hash)
        assert usuario is not None
        assert usuario["nombre"] == "Auth Test"

    async def test_token_invalido_retorna_none(self):
        fake_hash = "a" * 64
        usuario = await db_mod.obtener_usuario_por_token_hash(fake_hash)
        assert usuario is None

    async def test_refresh_token_genera_nuevo_valido(self):
        resultado = await db_mod.registrar_usuario({
            "whatsapp": "+56933333333",
            "nombre": "Refresh Test",
            "lat": -38.7,
            "lon": -72.6,
            "cultivos": ["general"],
        })

        nuevo = await db_mod.refresh_token(resultado["usuario_id"])
        assert nuevo["token"] != resultado["token"]
        assert len(nuevo["token"]) >= 32

        nuevo_hash = db_mod._hash_token(nuevo["token"])
        usuario = await db_mod.obtener_usuario_por_token_hash(nuevo_hash)
        assert usuario is not None

        viejo_hash = db_mod._hash_token(resultado["token"])
        usuario_viejo = await db_mod.obtener_usuario_por_token_hash(viejo_hash)
        assert usuario_viejo is None


class TestParcelas:
    async def test_agregar_parcela_con_cultivos(self):
        resultado = await db_mod.registrar_usuario({
            "whatsapp": "+56944444444",
            "nombre": "Parcela Test",
            "lat": -38.7,
            "lon": -72.6,
            "cultivos": ["general"],
            "plan": "premium",
        })

        parcela_id = await db_mod.agregar_parcela(
            resultado["usuario_id"],
            {"nombre": "Lote Norte", "lat": -38.8, "lon": -72.5, "cultivos": ["trigo"]},
        )
        assert parcela_id > 0

        parcelas = await db_mod.obtener_parcelas(resultado["usuario_id"])
        assert len(parcelas) == 2

    async def test_plan_free_limita_a_1_parcela(self):
        resultado = await db_mod.registrar_usuario({
            "whatsapp": "+56955555555",
            "nombre": "Free Limit",
            "lat": -38.7,
            "lon": -72.6,
            "cultivos": ["general"],
            "plan": "free",
        })

        with pytest.raises(ValueError, match="limitado"):
            await db_mod.agregar_parcela(
                resultado["usuario_id"],
                {"nombre": "Extra", "lat": -38.9, "lon": -72.4, "cultivos": ["papa"]},
            )

    async def test_eliminar_parcela(self):
        resultado = await db_mod.registrar_usuario({
            "whatsapp": "+56966666666",
            "nombre": "Delete Test",
            "lat": -38.7,
            "lon": -72.6,
            "cultivos": ["general"],
        })

        eliminado = await db_mod.eliminar_parcela(
            resultado["parcela_id"], resultado["usuario_id"]
        )
        assert eliminado is True

        parcelas = await db_mod.obtener_parcelas(resultado["usuario_id"])
        assert len(parcelas) == 0

    async def test_no_eliminar_parcela_ajena(self):
        r1 = await db_mod.registrar_usuario({
            "whatsapp": "+56977777777",
            "nombre": "Owner",
            "lat": -38.7,
            "lon": -72.6,
            "cultivos": ["general"],
        })
        r2 = await db_mod.registrar_usuario({
            "whatsapp": "+56988888888",
            "nombre": "Other",
            "lat": -38.8,
            "lon": -72.5,
            "cultivos": ["general"],
        })

        eliminado = await db_mod.eliminar_parcela(r1["parcela_id"], r2["usuario_id"])
        assert eliminado is False

        parcelas = await db_mod.obtener_parcelas(r1["usuario_id"])
        assert len(parcelas) == 1


class TestPlanes:
    async def test_actualizar_plan(self):
        resultado = await db_mod.registrar_usuario({
            "whatsapp": "+56999999999",
            "nombre": "Plan Test",
            "lat": -38.7,
            "lon": -72.6,
            "cultivos": ["general"],
            "plan": "free",
        })

        actualizado = await db_mod.actualizar_plan(resultado["usuario_id"], "premium")
        assert actualizado["plan"] == "premium"


class TestAlertas:
    async def test_registrar_alerta_fire_and_forget(self):
        resultado = await db_mod.registrar_usuario({
            "whatsapp": "+56900000000",
            "nombre": "Alerta Test",
            "lat": -38.7,
            "lon": -72.6,
            "cultivos": ["general"],
        })

        await db_mod.registrar_alerta(
            resultado["usuario_id"], "helada", "Test: helada detectada"
        )

    async def test_obtener_usuarios_con_cultivo(self):
        await db_mod.registrar_usuario({
            "whatsapp": "+56912121212",
            "nombre": "Papero",
            "lat": -38.7,
            "lon": -72.6,
            "cultivos": ["papa"],
        })
        await db_mod.registrar_usuario({
            "whatsapp": "+56913131313",
            "nombre": "Tiguero",
            "lat": -38.8,
            "lon": -72.5,
            "cultivos": ["trigo"],
        })

        paperos = await db_mod.obtener_usuarios_con_cultivo("papa")
        assert len(paperos) == 1
        assert paperos[0]["nombre"] == "Papero"

        trigueros = await db_mod.obtener_usuarios_con_cultivo("trigo")
        assert len(trigueros) == 1


class TestEsIntegrityError:
    def test_sqlite3_integrity_error_detectado(self):
        import sqlite3

        try:
            raise sqlite3.IntegrityError("UNIQUE constraint failed")
        except sqlite3.IntegrityError:
            assert db_mod._es_integrity_error() is True

    def test_error_generico_no_detectado(self):
        try:
            raise ValueError("algo random")
        except ValueError:
            assert db_mod._es_integrity_error() is False
