import base64
import csv
import json
import unicodedata
from pathlib import Path

from crop_router import agente_para_cultivo, clasificar_cultivo
from diagnostico_agent import diagnostico

GOLDEN_SET_DIR = Path("golden_set_3")
LABELS_CSV = GOLDEN_SET_DIR / "labels.csv"
OUTPUT_JSON = Path("resultados_golden_set_3.json")

# golden_set_3 mezcla 10 tomates, 10 uvas, 10 cerezas y 10 "otros" cultivos,
# todos con imagenes de plantas enfermas. Los cultivos que no son de los
# tres principales deben enrutarse al agente general (bucket "General").
CULTIVOS_PRINCIPALES = {"Tomates", "Uvas", "Cerezas"}

# Palabras clave (sin acentos, en minuscula) para verificar si la
# enfermedad devuelta por el agente coincide con la enfermedad real de la
# imagen. El texto del agente rara vez calza exacto con nuestra etiqueta,
# asi que se busca cualquiera de estas variantes como substring.
KEYWORDS_ENFERMEDAD = {
    "Early Blight": ["early blight", "tizon temprano", "alternaria"],
    "Late Blight": ["late blight", "tizon tardio", "phytophthora", "tizon tardio"],
    "Black Measles (Esca)": ["esca", "black measles", "sarampion negro", "medida negra"],
    "Black Rot": ["black rot", "podredumbre negra", "pudricion negra"],
    "Leaf Blight (Isariopsis)": [
        "leaf blight",
        "isariopsis",
        "tizon de la hoja",
        "tizon foliar",
    ],
    "Powdery Mildew": ["powdery mildew", "oidio", "mildiu polvorient", "cenicilla"],
    "Apple Scab": ["scab", "sarna"],
    "Apple Black Rot": ["black rot", "podredumbre negra", "pudricion negra"],
    "Common Rust": ["rust", "roya"],
    "Bacterial Spot": ["bacterial spot", "mancha bacteriana"],
    "Leaf Scorch": ["leaf scorch", "quemadura foliar", "escaldado"],
    "Huanglongbing (Citrus Greening)": [
        "huanglongbing",
        "citrus greening",
        "dragon amarillo",
        "hlb",
        "enverdecimiento",
    ],
}


def strip_accents(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def cultivo_esperado(cultivo_real: str) -> str:
    return cultivo_real if cultivo_real in CULTIVOS_PRINCIPALES else "General"


def enfermedad_coincide(enfermedad_real: str, resultado_diagnostico: dict) -> bool:
    keywords = KEYWORDS_ENFERMEDAD.get(enfermedad_real, [])
    if not keywords:
        return False

    texto = " ".join(
        str(resultado_diagnostico.get(campo, ""))
        for campo in ("enfermedad", "razonamiento", "sintomas")
    )
    texto = strip_accents(texto.lower())

    return any(strip_accents(kw.lower()) in texto for kw in keywords)


def cargar_labels() -> list[dict]:
    with open(LABELS_CSV, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def image_to_base64(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def main():
    labels = {row["id"]: row for row in cargar_labels()}
    resultados = []

    extensiones = {".jpg", ".jpeg", ".png", ".webp"}

    for image_file in sorted(GOLDEN_SET_DIR.iterdir()):
        if image_file.suffix.lower() not in extensiones:
            continue

        id_ = image_file.stem
        etiqueta = labels.get(id_)
        if etiqueta is None:
            continue

        cultivo_real = etiqueta["cultivo_real"]
        enfermedad_real = etiqueta["enfermedad_real"]
        esperado = cultivo_esperado(cultivo_real)

        print(f"Procesando: {image_file.name} (real: {cultivo_real} / {enfermedad_real})")

        try:
            imagen_b64 = image_to_base64(image_file)

            cultivo_detectado = clasificar_cultivo(imagen_b64)
            agent_name = agente_para_cultivo(cultivo_detectado)

            respuesta = diagnostico(imagen_b64, agent_name)

            try:
                resultado_diagnostico = json.loads(respuesta)
            except json.JSONDecodeError:
                resultado_diagnostico = {"raw_response": respuesta}

            crop_correcto = cultivo_detectado == esperado
            enfermedad_correcta = enfermedad_coincide(enfermedad_real, resultado_diagnostico)

            resultados.append(
                {
                    "archivo": image_file.name,
                    "cultivo_real": cultivo_real,
                    "cultivo_esperado": esperado,
                    "cultivo_detectado": cultivo_detectado,
                    "crop_correcto": crop_correcto,
                    "enfermedad_real": enfermedad_real,
                    "agente_usado": agent_name,
                    "resultado": resultado_diagnostico,
                    "enfermedad_correcta": enfermedad_correcta,
                }
            )

        except Exception as e:
            resultados.append(
                {
                    "archivo": image_file.name,
                    "cultivo_real": cultivo_real,
                    "cultivo_esperado": esperado,
                    "enfermedad_real": enfermedad_real,
                    "error": str(e),
                }
            )

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    print(f"\nCompletado. Resultados guardados en {OUTPUT_JSON}")
    imprimir_resumen(resultados)


def imprimir_resumen(resultados: list[dict]):
    total = len(resultados)
    con_error = [r for r in resultados if "error" in r]
    evaluados = [r for r in resultados if "error" not in r]

    crop_ok = sum(1 for r in evaluados if r["crop_correcto"])
    enfermedad_ok = sum(1 for r in evaluados if r["enfermedad_correcta"])

    print("\n=== Resumen ===")
    print(f"Total imagenes: {total}")
    print(f"Errores: {len(con_error)}")
    print(f"Evaluadas: {len(evaluados)}")
    if evaluados:
        print(
            f"Precisión de enrutamiento de cultivo: {crop_ok}/{len(evaluados)} "
            f"({100 * crop_ok / len(evaluados):.1f}%)"
        )
        print(
            f"Precisión de diagnóstico de enfermedad: {enfermedad_ok}/{len(evaluados)} "
            f"({100 * enfermedad_ok / len(evaluados):.1f}%)"
        )

    print("\n--- Por cultivo ---")
    por_cultivo: dict[str, dict[str, int]] = {}
    for r in evaluados:
        stats = por_cultivo.setdefault(r["cultivo_real"], {"total": 0, "crop_ok": 0, "enf_ok": 0})
        stats["total"] += 1
        stats["crop_ok"] += int(r["crop_correcto"])
        stats["enf_ok"] += int(r["enfermedad_correcta"])

    for cultivo, stats in sorted(por_cultivo.items()):
        print(
            f"{cultivo}: enrutamiento {stats['crop_ok']}/{stats['total']}, "
            f"diagnóstico {stats['enf_ok']}/{stats['total']}"
        )


if __name__ == "__main__":
    main()
