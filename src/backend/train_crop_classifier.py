"""
Entrena un MobileNetV2 (transfer learning) para clasificar el cultivo de una
foto, usando las imagenes en training_set/<cultivo>/...

Cada subcarpeta de nivel superior en training_set/ se trata como una clase
(p.ej. Cerezas, Manzanas, Uvas). Las imagenes se recolectan recursivamente,
asi que subcarpetas internas (variedad, estado sanitario, etc.) no afectan
la etiqueta de cultivo.

Ejecutar desde src/backend/:
    python train_crop_classifier.py
"""

import json
import random
import re
from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

TRAINING_DIR = Path("training_set")
MODEL_OUT = Path("crop_classifier.pt")
CLASSES_OUT = Path("crop_classifier_classes.json")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
IMAGE_SIZE = 224
BATCH_SIZE = 32
EPOCHS = 15
LEARNING_RATE = 1e-3
VAL_SPLIT = 0.2
SEED = 42

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# Some source datasets (e.g. PlantVillage-style folders) ship pre-augmented
# mirror copies alongside the originals, named like "<id>_flipTB.JPG". Those
# are near-duplicates of the same photo, not independent samples, so they
# must be grouped together and kept on the same side of the train/val split.
FLIP_SUFFIX_RE = re.compile(r"_flip[a-zA-Z]*$")

TRAIN_TRANSFORM = transforms.Compose(
    [
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ]
)

EVAL_TRANSFORM = transforms.Compose(
    [
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ]
)


class CropDataset(Dataset):
    def __init__(self, samples: list[tuple[Path, int]], transform):
        self.samples = samples
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        image = Image.open(path).convert("RGB")
        return self.transform(image), label


def discover_classes(training_dir: Path) -> list[str]:
    return sorted(d.name for d in training_dir.iterdir() if d.is_dir())


def collect_samples(training_dir: Path, classes: list[str]) -> list[tuple[Path, int]]:
    samples: list[tuple[Path, int]] = []
    for label_idx, class_name in enumerate(classes):
        class_dir = training_dir / class_name
        images = [
            p for p in class_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTENSIONS
        ]
        print(f"  {class_name}: {len(images)} imagenes")
        samples.extend((p, label_idx) for p in images)
    return samples


def _source_group_key(path: Path) -> str:
    return FLIP_SUFFIX_RE.sub("", path.stem)


def split_train_val(
    samples: list[tuple[Path, int]], val_split: float, seed: int
) -> tuple[list, list]:
    # Group by (class, source image) so mirrored/flipped variants of the same
    # photo always land on the same side of the split.
    by_class: dict[int, dict[str, list[tuple[Path, int]]]] = {}
    for path, label in samples:
        groups = by_class.setdefault(label, {})
        groups.setdefault(_source_group_key(path), []).append((path, label))

    rng = random.Random(seed)
    train, val = [], []
    for groups in by_class.values():
        group_items = list(groups.values())
        rng.shuffle(group_items)

        target_val = int(sum(len(g) for g in group_items) * val_split)

        val_groups, train_groups = [], []
        val_count = 0
        for group in group_items:
            if val_count < target_val:
                val_groups.append(group)
                val_count += len(group)
            else:
                train_groups.append(group)

        # Guarantee both splits are non-empty even for very small classes.
        if not val_groups and train_groups:
            val_groups.append(train_groups.pop())
        if not train_groups and val_groups:
            train_groups.append(val_groups.pop())

        for group in train_groups:
            train.extend(group)
        for group in val_groups:
            val.extend(group)

    return train, val


def compute_class_weights(samples: list[tuple[Path, int]], num_classes: int) -> torch.Tensor:
    counts = [0] * num_classes
    for _, label in samples:
        counts[label] += 1
    total = sum(counts)
    return torch.tensor(
        [total / (num_classes * count) for count in counts], dtype=torch.float32
    )


def build_model(num_classes: int) -> nn.Module:
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
    for param in model.features.parameters():
        param.requires_grad = False
    model.classifier[1] = nn.Linear(model.last_channel, num_classes)
    return model


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> float:
    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            preds = model(images).argmax(dim=1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)
    return correct / total if total else 0.0


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Usando device: {device}")

    classes = discover_classes(TRAINING_DIR)
    if not classes:
        raise SystemExit(f"No se encontraron carpetas de clase en {TRAINING_DIR}/")
    print(f"Clases detectadas: {classes}")

    samples = collect_samples(TRAINING_DIR, classes)
    train_samples, val_samples = split_train_val(samples, VAL_SPLIT, SEED)
    print(f"Train: {len(train_samples)} imagenes | Val: {len(val_samples)} imagenes")

    train_loader = DataLoader(
        CropDataset(train_samples, TRAIN_TRANSFORM),
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=2,
    )
    val_loader = DataLoader(
        CropDataset(val_samples, EVAL_TRANSFORM),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=2,
    )

    model = build_model(len(classes)).to(device)
    weights = compute_class_weights(train_samples, len(classes)).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.Adam(model.classifier.parameters(), lr=LEARNING_RATE)

    best_val_acc = 0.0
    for epoch in range(1, EPOCHS + 1):
        model.train()
        running_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)

        train_loss = running_loss / len(train_samples)
        val_acc = evaluate(model, val_loader, device)
        print(
            f"epoch {epoch:2d}/{EPOCHS}  train_loss={train_loss:.4f}  val_acc={val_acc:.4f}"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), MODEL_OUT)

    CLASSES_OUT.write_text(
        json.dumps(classes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Mejor val_acc: {best_val_acc:.4f}")
    print(f"Modelo guardado en {MODEL_OUT}, clases en {CLASSES_OUT}")


if __name__ == "__main__":
    main()
