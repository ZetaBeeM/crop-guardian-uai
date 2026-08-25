"""Autenticacion y aislamiento entre agricultores."""

from conftest import cabecera

RUTAS = [
    ("get", "/api/historial"),
    ("get", "/api/plantas"),
    ("delete", "/api/plantas/Tomatera"),
    ("post", "/api/analizar-cultivo"),
]


def analizar(cliente, agricultor_id, nombre_planta):
    return cliente.post(
        "/api/analizar-cultivo",
        json={"imagen": "imagen-falsa", "nombre_planta": nombre_planta},
        headers=cabecera(agricultor_id),
    )


def test_health_es_publico(cargar_app):
    app, _ = cargar_app(entorno=None)
    assert app.app.test_client().get("/api/health").status_code == 200


def test_sin_identidad_responde_401(cargar_app):
    app, _ = cargar_app(entorno=None)
    cliente = app.app.test_client()
    for metodo, ruta in RUTAS:
        respuesta = getattr(cliente, metodo)(ruta, json={})
        assert respuesta.status_code == 401, f"{metodo.upper()} {ruta}"


def test_entorno_produccion_ignora_la_identidad_de_desarrollo(cargar_app):
    """Sin ENTORNO=local, DEV_AGRICULTOR_ID no autentica a nadie."""
    for entorno in (None, "produccion"):
        app, _ = cargar_app(entorno=entorno)
        cliente = app.app.test_client()
        assert cliente.get("/api/historial").status_code == 401
        # La cabecera si funciona.
        respuesta = cliente.get("/api/historial", headers=cabecera("ana"))
        assert respuesta.status_code == 200


def test_entorno_local_acepta_la_identidad_de_desarrollo(cargar_app):
    app, _ = cargar_app(entorno="local")
    assert app.app.test_client().get("/api/historial").status_code == 200


def test_entorno_local_sin_variable_sigue_exigiendo_cabecera(cargar_app):
    app, _ = cargar_app(entorno="local", dev_agricultor_id="")
    assert app.app.test_client().get("/api/historial").status_code == 401


def test_el_agricultor_id_del_cuerpo_se_ignora(cliente):
    http, _, contenedor = cliente
    http.post(
        "/api/analizar-cultivo",
        json={
            "imagen": "imagen-falsa",
            "nombre_planta": "Tomatera",
            "agricultor_id": "beto",
        },
        headers=cabecera("ana"),
    )
    assert [d["agricultor_id"] for d in contenedor.documentos] == ["ana"]


def test_cada_agricultor_solo_ve_lo_suyo(cliente):
    http, _, _ = cliente
    analizar(http, "ana", "Tomatera")
    analizar(http, "ana", "Parra")
    analizar(http, "beto", "Cerezo")

    de_ana = http.get("/api/historial", headers=cabecera("ana")).get_json()
    de_beto = http.get("/api/historial", headers=cabecera("beto")).get_json()

    assert sorted(d["nombre_planta"] for d in de_ana) == ["Parra", "Tomatera"]
    assert [d["nombre_planta"] for d in de_beto] == ["Cerezo"]


def test_no_se_puede_borrar_la_planta_de_otro(cliente):
    http, _, contenedor = cliente
    analizar(http, "beto", "Cerezo")

    respuesta = http.delete("/api/plantas/Cerezo", headers=cabecera("ana"))
    assert respuesta.status_code == 404
    assert len(contenedor.documentos) == 1

    respuesta = http.delete("/api/plantas/Cerezo", headers=cabecera("beto"))
    assert respuesta.status_code == 200
    assert contenedor.documentos == []


def test_historial_ordenado_del_mas_reciente_al_mas_antiguo(cliente):
    http, _, contenedor = cliente
    analizar(http, "ana", "Primera")
    analizar(http, "ana", "Segunda")
    # Forzar el orden en vez de depender de la marca de tiempo.
    contenedor.documentos[0]["fecha"] = "2020-01-01T00:00:00+00:00"

    historial = http.get("/api/historial", headers=cabecera("ana")).get_json()
    assert historial[0]["nombre_planta"] == "Segunda"
