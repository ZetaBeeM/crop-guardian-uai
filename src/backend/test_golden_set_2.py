import base64
import csv
import json
import re
from pathlib import Path

from crop_router import agente_para_cultivo, clasificar_cultivo
from diagnostico_agent import diagnostico

GOLDEN_SET_DIR = Path("golden_set_2")
LABELS_CSV = Path("labels.csv")
OUTPUT_JSON = Path("resultados_golden_set_2.json")

# Cada entrada de archivo_original en labels.csv viene de una carpeta de
# origen distinta (Roboflow) según la enfermedad; el patrón se conserva en
# el prefijo del nombre de archivo aunque la imagen en golden_set_2/ ya
# esté anonimizada como "01.jpg", "02.jpg", etc.
CATEGORIAS = [
    (re.compile(r"^Blossom_end_root", re.IGNORECASE), "Blossom End Rot"),
    (re.compile(r"^Fruit_Cracking", re.IGNORECASE), "Fruit Cracking"),
    (re.compile(r"^Gray_Mold", re.IGNORECASE), "Gray Mold"),
    (re.compile(r"^White_Mold", re.IGNORECASE), "White Mold"),
    (re.compile(r"^L_blight", re.IGNORECASE), "Late Blight"),
    (re.compile(r"^LateBlight", re.IGNORECASE), "Late Blight"),
    (re.compile(r"^anthracnose", re.IGNORECASE), "Anthracnose"),
    (re.compile(r"^catfaced", re.IGNORECASE), "Catfacing"),
    (re.compile(r"^spot", re.IGNORECASE), "Bacterial Spot"),
    (re.compile(r"^h\d", re.IGNORECASE), "Healthy"),
]


def etiqueta_real(archivo_original: str) -> str:
    for patron, etiqueta in CATEGORIAS:
        if patron.match(archivo_original):
            return etiqueta
    return "desconocido"


def cargar_labels() -> dict[str, str]:
    labels = {}
    with open(LABELS_CSV, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            id_, archivo_original = row
            labels[f"{id_}.jpg"] = etiqueta_real(archivo_original)
    return labels


def image_to_base64(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def main():
    labels = cargar_labels()
    resultados = []

    extensiones = {".jpg", ".jpeg", ".png", ".webp"}

    for image_file in sorted(GOLDEN_SET_DIR.iterdir()):
        if image_file.suffix.lower() not in extensiones:
            continue

        etiqueta = labels.get(image_file.name, "desconocido")
        print(f"Procesando: {image_file.name} (real: {etiqueta})")

        try:
            imagen_b64 = image_to_base64(image_file)

            cultivo_detectado = clasificar_cultivo(imagen_b64)
            agent_name = agente_para_cultivo(cultivo_detectado)

            respuesta = diagnostico(imagen_b64, agent_name)

            try:
                respuesta_json = json.loads(respuesta)
            except json.JSONDecodeError:
                respuesta_json = {"raw_response": respuesta}

            resultados.append(
                {
                    "archivo": image_file.name,
                    "real": etiqueta,
                    "cultivo_detectado": cultivo_detectado,
                    "agente_usado": agent_name,
                    "resultado": respuesta_json,
                }
            )

        except Exception as e:
            resultados.append(
                {
                    "archivo": image_file.name,
                    "real": etiqueta,
                    "error": str(e),
                }
            )

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    print(f"\nCompletado. Resultados guardados en {OUTPUT_JSON}")

    total = len(resultados)
    con_error = sum(1 for r in resultados if "error" in r)
    tomate_detectado = sum(
        1 for r in resultados if r.get("cultivo_detectado") == "Tomates"
    )
    print(f"Total imágenes: {total}")
    print(f"Errores: {con_error}")
    print(f"Clasificadas localmente como Tomates: {tomate_detectado}/{total}")


if __name__ == "__main__":
    main()
