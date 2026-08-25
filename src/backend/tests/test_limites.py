"""Validacion de entrada y limite de tamano."""

from conftest import cabecera


def test_falta_la_imagen(cliente):
    http, _, _ = cliente
    respuesta = http.post(
        "/api/analizar-cultivo",
        json={"nombre_planta": "Tomatera"},
        headers=cabecera("ana"),
    )
    assert respuesta.status_code == 400


def test_falta_el_nombre_de_la_planta(cliente):
    http, _, _ = cliente
    respuesta = http.post(
        "/api/analizar-cultivo",
        json={"imagen": "imagen-falsa", "nombre_planta": "   "},
        headers=cabecera("ana"),
    )
    assert respuesta.status_code == 400


def test_imagen_demasiado_grande_devuelve_413_con_json(cliente):
    """Al leer el cuerpo salta el 413; no debe salir como 500."""
    http, app, contenedor = cliente
    limite = app.app.config["MAX_CONTENT_LENGTH"]

    respuesta = http.post(
        "/api/analizar-cultivo",
        json={"imagen": "x" * (limite + 1024), "nombre_planta": "Tomatera"},
        headers=cabecera("ana"),
    )

    assert respuesta.status_code == 413
    assert "error" in respuesta.get_json()
    assert contenedor.documentos == []
