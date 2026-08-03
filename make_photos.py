# -*- coding: utf-8 -*-
"""
Фото блюд: PNG 1122×1402 по 2–3 МБ → WebP под ширину экрана телефона.

Картинки сгенерированные, личного в них нет — они лежат в репозитории,
в отличие от plan16-data.json.

Запуск:  python make_photos.py
"""

import os
from pathlib import Path

from PIL import Image

# папка с исходными PNG; путь можно переопределить переменной окружения
SRC = Path(os.environ.get("PLAN16_PHOTOS", Path(__file__).resolve().parent.parent / "plan-16" / "Фото блюд"))
OUT = Path(__file__).parent / "photos"

WIDTH = 800
QUALITY = 80


def main():
    OUT.mkdir(exist_ok=True)
    before = after = 0
    for src in sorted(SRC.glob("*.png")):
        img = Image.open(src).convert("RGB")
        img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
        dst = OUT / (src.stem + ".webp")
        img.save(dst, "WEBP", quality=QUALITY, method=6)
        before += src.stat().st_size
        after += dst.stat().st_size
        print("%-32s %5.0f КБ" % (dst.name, dst.stat().st_size / 1024))
    print("итого %.1f МБ → %.1f МБ" % (before / 1048576, after / 1048576))


if __name__ == "__main__":
    main()
