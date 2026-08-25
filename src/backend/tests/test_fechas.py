"""Marcas de tiempo en UTC y calculo de revision vencida."""

from datetime import datetime, timedelta, timezone

from conftest import cabecera


def test_los_documentos_se_guardan_con_zona_horaria(cliente):
    http, _, contenedor = cliente
    http.post(
        "/api/analizar-cultivo",
        json={"imagen": "imagen-falsa", "nombre_planta": "Tomatera"},
        headers=cabecera("ana"),
    )

    documento = contenedor.documentos[0]
    for campo in ("fecha", "proxima_revision"):
        assert datetime.fromisoformat(documento[campo]).tzinfo is not None, campo


def test_proxima_revision_usa_los_dias_del_agente(cliente):
    http, _, contenedor = cliente
    http.post(
        "/api/analizar-cultivo",
        json={"imagen": "imagen-falsa", "nombre_planta": "Tomatera"},
        headers=cabecera("ana"),
    )

    documento = contenedor.documentos[0]
    diferencia = datetime.fromisoformat(
        documento["proxima_revision"]
    ) - datetime.fromisoformat(documento["fecha"])
    assert diferencia == timedelta(days=7)


def test_esta_vencido_con_fecha_futura(app_local):
    app, _ = app_local
    futuro = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert app.esta_vencido(futuro) is False


def test_esta_vencido_con_fecha_pasada(app_local):
    app, _ = app_local
    pasado = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert app.esta_vencido(pasado) is True


def test_esta_vencido_con_documento_antiguo_sin_zona_horaria(app_local):
    """Los documentos viejos no traen offset."""
    app, _ = app_local
    pasado = (
        (datetime.now(timezone.utc) - timedelta(days=1))
        .replace(tzinfo=None)
        .isoformat()
    )
    assert app.esta_vencido(pasado) is True


def test_esta_vencido_sin_fecha(app_local):
    app, _ = app_local
    assert app.esta_vencido(None) is False
    assert app.esta_vencido("") is False


def test_plantas_expone_el_campo_vencido(cliente):
    http, _, contenedor = cliente
    http.post(
        "/api/analizar-cultivo",
        json={"imagen": "imagen-falsa", "nombre_planta": "Tomatera"},
        headers=cabecera("ana"),
    )
    contenedor.documentos[0]["proxima_revision"] = "2020-01-01T00:00:00+00:00"

    plantas = http.get("/api/plantas", headers=cabecera("ana")).get_json()
    assert plantas[0]["vencido"] is True
