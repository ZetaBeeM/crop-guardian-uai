import base64
import csv
import json
import os
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")
AGENT_NAME = os.getenv("AZURE_AI_AGENT1_NAME")

labels = {}
with open("labels.csv", "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        labels[f"{row[0]}.jpg"] = row[1]

project = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential(),
)

openai_client = project.get_openai_client()

GOLDEN_SET_DIR = Path("golden_set_2")


def diagnosticar_imagen(image_b64: str):
    response = openai_client.responses.create(
        extra_body={
            "agent_reference": {
                "name": AGENT_NAME,
                "type": "agent_reference",
            }
        },
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{image_b64}",
                    },
                ],
            }
        ],
    )

    return response.output_text


def image_to_base64(image_path: Path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def main():
    resultados = []

    extensiones = {".jpg", ".jpeg", ".png", ".webp"}

    for image_file in sorted(GOLDEN_SET_DIR.iterdir()):
        if image_file.suffix.lower() not in extensiones:
            continue

        print(f"Procesando: {image_file.name}")

        try:
            image_b64 = image_to_base64(image_file)

            respuesta = diagnosticar_imagen(image_b64)

            try:
                respuesta_json = json.loads(respuesta)
            except json.JSONDecodeError:
                respuesta_json = {"raw_response": respuesta}

            resultados.append(
                {
                    "archivo": image_file.name,
                    "real": labels.get(image_file.name, "desconocido"),
                    "resultado": respuesta_json,
                }
            )

        except Exception as e:
            resultados.append(
                {
                    "archivo": image_file.name,
                    "error": str(e),
                }
            )

    with open(
        "resultados_golden_set.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            resultados,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Completado. Resultados guardados en resultados_golden_set.json")


if __name__ == "__main__":
    main()
