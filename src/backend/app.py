import json
import os
from datetime import datetime, timedelta

from azure.cosmos import CosmosClient
from crop_router import agente_para_cultivo, clasificar_cultivo
from diagnostico_agent import diagnostico
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from tratamiento_agent import recomendar_tratamiento

load_dotenv()

app = Flask(__name__, static_folder="static")
CORS(app)

# Cosmos DB
cosmos_client = CosmosClient(
    url=os.getenv("COSMOS_URI"), credential={"masterKey": os.getenv("COSMOS_KEY")}
)
database = cosmos_client.get_database_client("cultivos_db")
container = database.get_container_client("diagnosticos")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/analizar-cultivo", methods=["POST"])
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

        ahora = datetime.now()
        dias_revision = resultado_tratamiento.get("proxima_revision_dias", 7)
        proxima_revision = (ahora + timedelta(days=dias_revision)).isoformat()

        documento = {
            "id": f"diag-{ahora.strftime('%Y%m%d%H%M%S%f')}",
            "agricultor_id": data.get("agricultor_id", "agricultor-demo"),
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

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/historial", methods=["GET"])
def historial():
    try:
        items = list(container.read_all_items())
        items.sort(key=lambda i: i.get("fecha", ""), reverse=True)
        return jsonify(items), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/plantas", methods=["GET"])
def plantas():
    """
    Devuelve, por cada planta etiquetada, su registro más reciente
    (diagnóstico, tratamiento, fecha de próxima revisión) y si ya
    se pasó el plazo recomendado por el agente agrónomo.
    """
    try:
        items = list(container.read_all_items())

        ultimo_por_planta = {}
        for item in items:
            nombre = item.get("nombre_planta")
            if not nombre:
                continue

            actual = ultimo_por_planta.get(nombre)
            if actual is None or item.get("fecha", "") > actual.get("fecha", ""):
                ultimo_por_planta[nombre] = item

        ahora = datetime.now().isoformat()
        resultado = []
        for nombre, item in ultimo_por_planta.items():
            proxima_revision = item.get("proxima_revision")
            vencido = bool(proxima_revision) and proxima_revision < ahora

            resultado.append(
                {
                    "nombre_planta": nombre,
                    "fecha": item.get("fecha"),
                    "proxima_revision": proxima_revision,
                    "diagnostico": item.get("resultado", {}).get("enfermedad"),
                    "severidad": item.get("resultado", {}).get("severidad"),
                    "explicacion": item.get("tratamiento", {}).get("explicacion"),
                    "tratamiento": item.get("tratamiento", {}).get("tratamiento"),
                    "prevencion": item.get("tratamiento", {}).get("prevencion"),
                    "urgencia": item.get("tratamiento", {}).get("urgencia"),
                    "vencido": vencido,
                }
            )

        resultado.sort(key=lambda p: p["nombre_planta"])
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/plantas/<nombre_planta>", methods=["DELETE"])
def eliminar_planta(nombre_planta):
    """
    Elimina todo el historial asociado a una planta (todos los
    documentos con ese nombre_planta), para que deje de aparecer
    en "Mis Plantas" y en el registro completo.
    """
    try:
        items = list(
            container.query_items(
                query="SELECT * FROM c WHERE c.nombre_planta = @nombre",
                parameters=[{"name": "@nombre", "value": nombre_planta}],
                enable_cross_partition_query=True,
            )
        )

        if not items:
            return jsonify({"error": "Planta no encontrada"}), 404

        for item in items:
            # Asume que la clave de partición del contenedor es /agricultor_id.
            # Si tu contenedor usa otra clave de partición, ajusta este valor.
            container.delete_item(item, partition_key=item["agricultor_id"])

        return jsonify({"eliminados": len(items)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
