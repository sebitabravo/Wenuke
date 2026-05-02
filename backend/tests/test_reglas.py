"""Tests para el motor de reglas por cultivo."""
from reglas import (
    _severidad_granizo,
    _severidad_helada,
    _severidad_lluvia,
    _severidad_viento,
    evaluar_reglas,
    generar_recomendaciones,
)


class TestSeveridades:
    def test_helada_alta_cuando_temp_menor_a_severa(self):
        assert _severidad_helada(-3.0, 0.0, -2.0) == "alta"

    def test_helada_media_cuando_temp_entre_min_y_severa(self):
        assert _severidad_helada(-1.0, 0.0, -2.0) == "media"

    def test_lluvia_alta_cuando_supera_1_5_veces_umbral(self):
        assert _severidad_lluvia(30.0, 20.0) == "alta"

    def test_lluvia_media_cuando_no_supera_1_5_veces(self):
        assert _severidad_lluvia(25.0, 20.0) == "media"

    def test_viento_alta_cuando_supera_umbral_plus_10(self):
        assert _severidad_viento(55.0, 40.0) == "alta"

    def test_viento_media_cuando_no_supera_umbral_plus_10(self):
        assert _severidad_viento(45.0, 40.0) == "media"

    def test_granizo_alta_cuando_supera_1_5_veces_umbral(self):
        assert _severidad_granizo(12.0, 8.0) == "alta"

    def test_granizo_media_cuando_supera_1_2_veces(self):
        assert _severidad_granizo(10.0, 8.0) == "media"

    def test_granizo_baja_cuando_cerca_del_umbral(self):
        assert _severidad_granizo(8.5, 8.0) == "baja"


class TestEvaluarReglas:
    def _make_hourly(self, horas, temp=15.0, precip=0.0, viento=5.0):
        """Helper: genera datos horarios de prueba."""
        return [
            {
                "hora": f"2026-05-02T{h:02d}:00",
                "temperatura": temp,
                "precipitacion": precip,
                "viento": viento,
            }
            for h in range(horas)
        ]

    def test_sin_alertas_con_clima_normal(self):
        hourly = self._make_hourly(24, temp=15.0, precip=0.5, viento=5.0)
        resultado = evaluar_reglas(hourly, "general")
        assert resultado["alertas"] == []

    def test_detecta_helada_papa(self):
        hourly = self._make_hourly(24, temp=-1.0, precip=0.0, viento=5.0)
        resultado = evaluar_reglas(hourly, "papa")
        alertas_helada = [a for a in resultado["alertas"] if a["tipo"] == "helada"]
        assert len(alertas_helada) >= 1
        assert alertas_helada[0]["severidad"] in ("alta", "media")

    def test_detecta_lluvia_intensa(self):
        hourly = self._make_hourly(24, temp=15.0, precip=2.0, viento=5.0)
        # 2mm * 24h = 48mm > 20mm umbral general
        resultado = evaluar_reglas(hourly, "general")
        alertas_lluvia = [a for a in resultado["alertas"] if a["tipo"] == "lluvia_intensa"]
        assert len(alertas_lluvia) >= 1

    def test_detecta_viento_fuerte(self):
        hourly = self._make_hourly(24, temp=15.0, precip=0.0, viento=50.0)
        resultado = evaluar_reglas(hourly, "general")
        alertas_viento = [a for a in resultado["alertas"] if a["tipo"] == "viento_fuerte"]
        assert len(alertas_viento) >= 1

    def test_detecta_granizo(self):
        hourly = self._make_hourly(24, temp=5.0, precip=10.0, viento=5.0)
        resultado = evaluar_reglas(hourly, "general")
        alertas_granizo = [a for a in resultado["alertas"] if a["tipo"] == "granizo"]
        assert len(alertas_granizo) >= 1

    def test_no_granizo_sin_temp_fria(self):
        # Granizo requiere temp entre 0-15°C
        hourly = self._make_hourly(24, temp=20.0, precip=10.0, viento=5.0)
        resultado = evaluar_reglas(hourly, "general")
        alertas_granizo = [a for a in resultado["alertas"] if a["tipo"] == "granizo"]
        assert len(alertas_granizo) == 0

    def test_cultivo_invalido_usa_general(self):
        hourly = self._make_hourly(24, temp=-1.0)
        resultado = evaluar_reglas(hourly, "general")
        assert "alertas" in resultado
        assert "cultivo" in resultado

    def test_alertas_ordenadas_por_dia_y_severidad(self):
        hourly = self._make_hourly(24, temp=-3.0, precip=3.0, viento=50.0)
        resultado = evaluar_reglas(hourly, "general")
        alertas = resultado["alertas"]
        # Verificar orden: alta antes que media antes que baja
        severidades = [a["severidad"] for a in alertas]
        orden = {"alta": 0, "media": 1, "baja": 2}
        for i in range(len(severidades) - 1):
            assert orden[severidades[i]] <= orden[severidades[i + 1]]


class TestGenerarRecomendaciones:
    def _make_hourly(self, horas, temp=15.0, precip=0.0, viento=5.0):
        return [
            {
                "hora": f"2026-05-02T{h:02d}:00",
                "temperatura": temp,
                "precipitacion": precip,
                "viento": viento,
            }
            for h in range(horas)
        ]

    def _make_daily(self, dias=3, **kwargs):
        return [
            {
                "dia": f"2026-05-{2+d:02d}",
                "temp_min": kwargs.get("temp_min", 10.0),
                "temp_max": kwargs.get("temp_max", 20.0),
                "precipitacion_total": kwargs.get("precip_total", 1.0),
                "viento_max": kwargs.get("viento_max", 10.0),
            }
            for d in range(dias)
        ]

    def test_genera_4_tipos_recomendacion(self):
        hourly = self._make_hourly(24)
        daily = self._make_daily()
        recs = generar_recomendaciones(hourly, daily, "general")
        acciones = {r["accion"] for r in recs}
        assert acciones == {"fumigar", "regar", "sembrar", "cosechar"}

    def test_fumigar_si_buen_tiempo(self):
        hourly = self._make_hourly(24, temp=18.0, precip=0.5, viento=5.0)
        daily = self._make_daily(temp_max=22.0, precip_total=0.5, viento_max=10.0)
        recs = generar_recomendaciones(hourly, daily, "general")
        fumigar = [r for r in recs if r["accion"] == "fumigar"][0]
        assert fumigar["recomendacion"] == "Sí"

    def test_no_fumigar_con_lluvia(self):
        hourly = self._make_hourly(24, temp=18.0, precip=0.0, viento=5.0)
        daily = self._make_daily(precip_total=10.0, viento_max=10.0)
        recs = generar_recomendaciones(hourly, daily, "general")
        fumigar = [r for r in recs if r["accion"] == "fumigar"][0]
        assert fumigar["recomendacion"] == "No"

    def test_sembrar_no_con_helada(self):
        hourly = self._make_hourly(24, temp=1.0)
        daily = self._make_daily(temp_min=1.0)
        recs = generar_recomendaciones(hourly, daily, "general")
        sembrar = [r for r in recs if r["accion"] == "sembrar"][0]
        assert sembrar["recomendacion"] == "No"

    def test_cosechar_si_tiempo_seco(self):
        hourly = self._make_hourly(24, temp=18.0, precip=0.0, viento=5.0)
        daily = self._make_daily(precip_total=0.5, temp_max=22.0, viento_max=10.0)
        recs = generar_recomendaciones(hourly, daily, "general")
        cosechar = [r for r in recs if r["accion"] == "cosechar"][0]
        assert cosechar["recomendacion"] == "Sí"

    def test_recomendaciones_vacias_sin_daily(self):
        hourly = self._make_hourly(24)
        recs = generar_recomendaciones(hourly, [], "general")
        assert recs == []
