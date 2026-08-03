# -*- coding: utf-8 -*-
"""
Фото блюд: PNG 1122×1402 по 2–3 МБ → WebP под ширину экрана телефона.

Картинки сгенерированные, личного в них нет — они лежат в репозитории,
в отличие от plan16-data.json.

Запуск:  python make_photos.py
"""

import os
import re
from pathlib import Path

from PIL import Image

# папка с исходными PNG; путь можно переопределить переменной окружения
SRC = Path(os.environ.get("PLAN16_PHOTOS", Path(__file__).resolve().parent.parent / "plan-16" / "Фото блюд"))
OUT = Path(__file__).parent / "photos"

WIDTH = 800
QUALITY = 80


def pick_latest(paths):
    """Из «18-soupe-oignon.png» и «18-soupe-oignon-v2.png» берётся вторая.

    Перегенерированные картинки Саид кладёт рядом с суффиксом -vN, старую не удаляя.
    Без этого отбора очередной прогон вернул бы забракованный вариант.
    """
    best = {}
    for path in paths:
        m = re.match(r"(.+?)(?:-v(\d+))?$", path.stem)
        base, version = m.group(1), int(m.group(2) or 1)
        if base not in best or version > best[base][0]:
            best[base] = (version, path)
    return sorted((base, path) for base, (_, path) in best.items())


def main():
    OUT.mkdir(exist_ok=True)
    before = after = 0
    for base, src in pick_latest(SRC.glob("*.png")):
        img = Image.open(src).convert("RGB")
        img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
        dst = OUT / (base + ".webp")
        img.save(dst, "WEBP", quality=QUALITY, method=6)
        before += src.stat().st_size
        after += dst.stat().st_size
        mark = "" if src.stem == base else "  ← " + src.name
        print("%-32s %5.0f КБ%s" % (dst.name, dst.stat().st_size / 1024, mark))
    print("итого %.1f МБ → %.1f МБ" % (before / 1048576, after / 1048576))


if __name__ == "__main__":
    main()
