import csv
from pathlib import Path

IMAGES_DIR = Path("golden_set_2")

with open("golden_set_2/labels.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "archivo_original"])

    idx = 1

    for image_file in sorted(IMAGES_DIR.iterdir()):
        if image_file.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue

        writer.writerow([idx, image_file.name])

        idx += 1

print("labels.csv generado")
