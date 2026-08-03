# -*- coding: utf-8 -*-
"""
Иконки приложения: список дел — три строки и отметка на текущей.

Запуск:  python make_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent
BG = (20, 22, 26)
LINE = (150, 155, 166)
ACC = (217, 122, 74)


def draw(size, pad_ratio):
    """pad_ratio — доля поля по краям: у maskable она больше, иначе обрежут."""
    s = size * 4  # рисуем крупнее и уменьшаем — края выходят гладкими
    img = Image.new("RGB", (s, s), BG)
    d = ImageDraw.Draw(img)

    pad = s * pad_ratio
    inner = s - pad * 2
    row = inner / 3.4
    bar_h = row * 0.30
    dot_r = row * 0.26
    gap = row * 0.62

    for i in range(3):
        y = pad + row * i + row * 0.35
        cx = pad + dot_r
        cy = y + bar_h / 2
        colour = ACC if i == 1 else LINE
        if i == 1:
            d.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=ACC)
        else:
            d.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], outline=LINE, width=int(s * 0.012))
        x0 = cx + dot_r + gap
        width = inner - (x0 - pad) - (0 if i != 2 else inner * 0.22)
        d.rounded_rectangle([x0, y, x0 + width, y + bar_h], radius=bar_h / 2, fill=colour)

    return img.resize((size, size), Image.LANCZOS)


def main():
    for name, size, pad in [
        ("icon-180.png", 180, 0.20),
        ("icon-192.png", 192, 0.20),
        ("icon-512.png", 512, 0.20),
        ("icon-512-maskable.png", 512, 0.28),
    ]:
        draw(size, pad).save(OUT / name)
        print(name, "%.1f КБ" % ((OUT / name).stat().st_size / 1024))


if __name__ == "__main__":
    main()
