"""Dobles para importar `app` sin Azure ni red.

`app.py` crea el cliente de Cosmos al importarse, y los modulos de agentes su
`AIProjectClient`. Los dobles van a `sys.modules` antes de importar `app`.
"""

import sys
import types
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


class ContenedorFalso:
    """Contenedor de Cosmos falso, con los documentos en memoria."""

    def __init__(self):
        self.documentos = []

    def query_items(self, query=None, parameters=None, partition_key=None, **kwargs):
        # Una consulta sin particion devolveria datos de otros agricultores.
        assert partition_key is not None, "consulta sin partition_key"

        items = [d for d in self.documentos if d["agricultor_id"] == partition_key]
        for parametro in parameters or []:
            if parametro["name"] == "@nombre":
                items = [
                    d for d in items if d["nombre_planta"] == parametro["value"]
                ]
        if query and "ORDER BY c.fecha DESC" in query:
            items = sorted(items, key=lambda d: d["fecha"], reverse=True)
        return items

    def create_item(self, documento):
        self.documentos.append(documento)

    def delete_item(self, item, partition_key=None):
        assert partition_key == item["agricultor_id"]
        self.documentos.remove(item)


def _instalar_dobles():
    contenedor = ContenedorFalso()

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *a, **k: None
    sys.modules["dotenv"] = dotenv

    azure = types.ModuleType("azure")
    cosmos = types.ModuleType("azure.cosmos")

    class CosmosClient:
        def __init__(self, *a, **k):
            pass

        def get_database_client(self, *a, **k):
            return types.SimpleNamespace(
                get_container_client=lambda *a, **k: contenedor
            )

    cosmos.CosmosClient = CosmosClient
    azure.cosmos = cosmos
    sys.modules["azure"] = azure
    sys.modules["azure.cosmos"] = cosmos

    router = types.ModuleType("crop_router")
    router.clasificar_cultivo = lambda imagen_b64: "Tomates"
    router.agente_para_cultivo = lambda cultivo: "agente-de-prueba"
    sys.modules["crop_router"] = router

    diagnostico = types.ModuleType("diagnostico_agent")
    diagnostico.diagnostico = lambda imagen, agente: (
        '{"enfermedad": "tizon tardio", "severidad": "alta", "confianza": 0.9}'
    )
    sys.modules["diagnostico_agent"] = diagnostico

    tratamiento = types.ModuleType("tratamiento_agent")
    tratamiento.recomendar_tratamiento = lambda d: (
        '{"tratamiento": "fungicida de cobre", "proxima_revision_dias": 7}'
    )
    sys.modules["tratamiento_agent"] = tratamiento

    return contenedor


@pytest.fixture
def cargar_app(monkeypatch):
    """Importa `app` con el entorno indicado.

    `ENTORNO` se lee al importar, asi que cada caso necesita reimportar.
    """

    def _cargar(entorno=None, dev_agricultor_id="agricultor-de-prueba"):
        monkeypatch.delenv("ENTORNO", raising=False)
        if entorno is not None:
            monkeypatch.setenv("ENTORNO", entorno)
        monkeypatch.setenv("DEV_AGRICULTOR_ID", dev_agricultor_id)
        monkeypatch.setenv("COSMOS_URI", "https://ejemplo.invalido")
        monkeypatch.setenv("COSMOS_KEY", "clave-de-prueba")

        contenedor = _instalar_dobles()
        sys.modules.pop("app", None)
        import app

        return app, contenedor

    return _cargar


@pytest.fixture
def app_local(cargar_app):
    """La app en modo local, el caso mas comun."""
    return cargar_app(entorno="local")


@pytest.fixture
def cliente(app_local):
    app, contenedor = app_local
    return app.app.test_client(), app, contenedor


def cabecera(agricultor_id):
    return {"X-MS-CLIENT-PRINCIPAL-ID": agricultor_id}
