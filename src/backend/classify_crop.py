"""
Prueba manual del clasificador de cultivo, usando el mismo modelo local
(LM Studio) y logica de crop_router.py que usa la app en produccion. Dado
un archivo de imagen, imprime el cultivo detectado.

Requiere LM Studio corriendo con un modelo de vision cargado y el servidor
local activo (por defecto en http://127.0.0.1:1234).

Uso:
    python classify_crop.py ruta/a/imagen.jpg

O sin argumentos: el script pide la ruta, asi que puedes arrastrar el
archivo de imagen a la terminal para que se autocomplete la ruta.
"""

import argparse
import base64
import sys
from pathlib import Path

from crop_router import GENERAL, PROMPT, client, extract_crop, LMSTUDIO_MODEL


def classify(image_path: Path) -> None:
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")

    response = client.chat.completions.create(
        model=LMSTUDIO_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                    },
                ],
            }
        ],
        temperature=0,
    )

    respuesta_cruda = response.choices[0].message.content.strip()
    prediccion = extract_crop(respuesta_cruda) or GENERAL

    print(f"\n{image_path.name}")
    print(f"-> Prediccion: {prediccion}")
    if prediccion == GENERAL:
        print("(sin match claro -> se enrutaria al agente general) Respuesta cruda:")
        print(respuesta_cruda)
    print()


def prompt_for_path() -> Path:
    entered = input("Arrastra la imagen a la terminal y presiona Enter: ").strip()
    entered = entered.strip('"').strip("'")
    return Path(entered)


def main():
    parser = argparse.ArgumentParser(
        description="Clasifica el cultivo de una imagen (LM Studio, zero-shot)"
    )
    parser.add_argument(
        "image", type=Path, nargs="?", help="Ruta de la imagen a clasificar"
    )
    args = parser.parse_args()

    image_path = args.image if args.image is not None else prompt_for_path()

    if not image_path.exists():
        sys.exit(f"No se encontro el archivo: {image_path}")

    classify(image_path)


if __name__ == "__main__":
    main()
