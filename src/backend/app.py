import json
import os
from datetime import datetime, timedelta, timezone

from azure.cosmos import CosmosClient
from crop_router import agente_para_cultivo, clasificar_cultivo
from diagnostico_agent import diagnostico
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from tratamiento_agent import recomendar_tratamiento

load_dotenv()

# Flask sirve el frontend construido desde static/, en el mismo origen.
app = Flask(__name__, static_folder="static", static_url_path="")

# Por defecto produccion: la identidad de desarrollo solo vale con ENTORNO=local.
ENTORNO = os.getenv("ENTORNO", "produccion")

# Las fotos van en base64 dentro del JSON. Sin limite se cargan enteras en memoria.
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# Cosmos DB
cosmos_client = CosmosClient(
    url=os.getenv("COSMOS_URI"), credential={"masterKey": os.getenv("COSMOS_KEY")}
)
database = cosmos_client.get_database_client("cultivos_db")
container = database.get_container_client("diagnosticos")


@app.before_request
def resolver_agricultor():
    """Deja en g.agricultor_id la identidad del usuario para las rutas /api.

    La cabecera la inyecta la plataforma despues de validar el login. El
    contenedor no debe quedar accesible por fuera de esa capa: cualquiera
    podria mandar la cabecera a mano.
    """
    if not request.path.startswith("/api/") or request.path == "/api/health":
        return None

    agricultor_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID")
    if not agricultor_id and ENTORNO == "local":
        agricultor_id = os.getenv("DEV_AGRICULTOR_ID")
    if not agricultor_id:
        return jsonify({"error": "No autenticado"}), 401

    g.agricultor_id = agricultor_id
    return None


def consultar(query, parametros=None):
    """Consulta acotada a la particion del agricultor autenticado.

    Sin partition_key la consulta cruzaria particiones y devolveria documentos
    de otros agricultores.
    """
    return list(
        container.query_items(
            query=query,
            parameters=parametros or [],
            partition_key=g.agricultor_id,
        )
    )


def esta_vencido(proxima_revision):
    """Indica si ya paso la fecha de proxima revision.

    Los documentos anteriores al cambio a UTC no traen zona horaria; se asumen
    UTC.
    """
    if not proxima_revision:
        return False

    fecha = datetime.fromisoformat(proxima_revision)
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha < datetime.now(timezone.utc)


@app.errorhandler(413)
def imagen_demasiado_grande(_):
    return jsonify({"error": "La imagen supera el tamaño máximo permitido"}), 413


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/health", methods=["GET"])
def health():
    """Sonda de vida. No toca Cosmos ni los agentes."""
    return jsonify({"status": "ok"}), 200


@app.route("/api/analizar-cultivo", methods=["POST"])
def analizar_cultivo():
    try:
        data = request.get_json()
        print("Request recibido")
        imagen_b64 = data.get("imagen")
        print("Imagen recibida")
        if not imagen_b64:
            return jsonify({"error": "No se proporcionó una imagen"}), 400

        nombre_planta = (data.get("nombre_planta") or "").strip()
        if not nombre_planta:
            return jsonify({"error": "No se proporcionó un nombre de planta"}), 400

        cultivo_detectado = clasificar_cultivo(imagen_b64)
        print(f"Cultivo detectado localmente: {cultivo_detectado}")
        agent_name = agente_para_cultivo(cultivo_detectado)

        respuesta_agente = diagnostico(imagen_b64, agent_name)
        print(f"Respuesta del agente: {respuesta_agente}")
        resultado_diagnostico = json.loads(respuesta_agente)
        if not resultado_diagnostico.get("planta"):
            resultado_diagnostico["planta"] = cultivo_detectado

        respuesta_agente_tratamiento = recomendar_tratamiento(resultado_diagnostico)
        print(f"Respuesta del agente de tratamiento: {respuesta_agente_tratamiento}")
        resultado_tratamiento = json.loads(respuesta_agente_tratamiento)

        ahora = datetime.now(timezone.utc)
        dias_revision = resultado_tratamiento.get("proxima_revision_dias", 7)
        proxima_revision = (ahora + timedelta(days=dias_revision)).isoformat()

        documento = {
            "id": f"diag-{ahora.strftime('%Y%m%d%H%M%S%f')}",
            # De la plataforma, nunca del cuerpo: si no, un cliente podria
            # escribir en la particion de otro.
            "agricultor_id": g.agricultor_id,
            "nombre_planta": nombre_planta,
            "cultivo_detectado": cultivo_detectado,
            "fecha": ahora.isoformat(),
            "proxima_revision": proxima_revision,
            "resultado": resultado_diagnostico,
            "tratamiento": resultado_tratamiento,
        }

        resultado = {
            "diagnostico": resultado_diagnostico,
            "tratamiento": resultado_tratamiento,
            "nombre_planta": nombre_planta,
            "cultivo_detectado": cultivo_detectado,
            "proxima_revision": proxima_revision,
        }

        try:
            container.create_item(documento)
        except Exception as e:
            print(f"No se pudo guardar el diagnostico en Cosmos DB: {e}")

        return jsonify(resultado), 200

    except HTTPException:
        # El 413 de MAX_CONTENT_LENGTH salta al leer el cuerpo; sin esto lo
        # atraparia el except de abajo y saldria como 500.
        raise
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/historial", methods=["GET"])
def historial():
    try:
        return jsonify(consultar("SELECT * FROM c ORDER BY c.fecha DESC")), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/plantas", methods=["GET"])
def plantas():
    """
    Devuelve, por cada planta etiquetada, su registro más reciente
    (diagnóstico, tratamiento, fecha de próxima revisión) y si ya
    se pasó el plazo recomendado por el agente agrónomo.
    """
    try:
        # Viene ordenado por fecha descendente: el primero de cada planta es
        # el mas reciente.
        ultimo_por_planta = {}
        for item in consultar("SELECT * FROM c ORDER BY c.fecha DESC"):
            nombre = item.get("nombre_planta")
            if nombre and nombre not in ultimo_por_planta:
                ultimo_por_planta[nombre] = item

        resultado = [
            {
                "nombre_planta": nombre,
                "fecha": item.get("fecha"),
                "proxima_revision": item.get("proxima_revision"),
                "diagnostico": item.get("resultado", {}).get("enfermedad"),
                "severidad": item.get("resultado", {}).get("severidad"),
                "explicacion": item.get("tratamiento", {}).get("explicacion"),
                "tratamiento": item.get("tratamiento", {}).get("tratamiento"),
                "prevencion": item.get("tratamiento", {}).get("prevencion"),
                "urgencia": item.get("tratamiento", {}).get("urgencia"),
                "vencido": esta_vencido(item.get("proxima_revision")),
            }
            for nombre, item in ultimo_por_planta.items()
        ]

        resultado.sort(key=lambda p: p["nombre_planta"])
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/plantas/<nombre_planta>", methods=["DELETE"])
def eliminar_planta(nombre_planta):
    """
    Elimina todo el historial asociado a una planta (todos los
    documentos con ese nombre_planta), para que deje de aparecer
    en "Mis Plantas" y en el registro completo.
    """
    try:
        items = consultar(
            "SELECT * FROM c WHERE c.nombre_planta = @nombre",
            [{"name": "@nombre", "value": nombre_planta}],
        )

        if not items:
            return jsonify({"error": "Planta no encontrada"}), 404

        for item in items:
            container.delete_item(item, partition_key=g.agricultor_id)

        return jsonify({"eliminados": len(items)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
