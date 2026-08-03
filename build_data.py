# -*- coding: utf-8 -*-
"""
Собирает личный файл plan16-data.json из markdown-документов plan-16.

Публикуется только движок (index.html и прочее). Этот файл и то, что он
производит, в репозиторий не попадают: см. .gitignore.

Запуск:  python build_data.py
"""

import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path

import markdown

# где лежат исходные заметки; путь можно переопределить переменной окружения
SRC = Path(os.environ.get("PLAN16_SRC", Path(__file__).resolve().parent.parent / "plan-16"))
OUT = Path(__file__).parent / "plan16-data.json"

YEAR = 2026
MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

MD = markdown.Markdown(extensions=["tables", "nl2br", "sane_lists"])


def html(text):
    """markdown → html. Пустой текст даёт пустую строку, а не <p></p>."""
    text = text.strip()
    # хвостовой разделитель разделов в <hr> превращать незачем
    text = re.sub(r"\n-{3,}\s*$", "", text).strip()
    # прочерки для заполнения от руки: markdown принял бы их за выделение
    text = re.sub(r"_{3,}", '<span class="fill"></span>', text)
    if not text:
        return ""
    MD.reset()
    return MD.convert(text)


def slug(text):
    """Заголовок → идентификатор из латиницы и цифр."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    ru = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    text = "".join(ru.get(c, c) for c in text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "x"


def split_headings(text, level):
    """Режет текст по заголовкам заданного уровня.

    Возвращает (текст до первого заголовка, [(заголовок, тело), ...]).
    Заголовки внутри блоков кода тут не встречаются, поэтому проверки на них нет.
    """
    pattern = re.compile(r"^%s (.+)$" % ("#" * level), re.M)
    marks = list(pattern.finditer(text))
    if not marks:
        return text, []
    head = text[: marks[0].start()]
    parts = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        parts.append((m.group(1).strip(), text[m.end():end]))
    return head, parts


def read(name):
    return (SRC / name).read_text(encoding="utf-8")


# ─────────────────────────── распорядок ───────────────────────────

def parse_schedule(body):
    """Строки вида «**06:30** Подъём…» → [{t, s}]."""
    out = []
    for line in body.splitlines():
        m = re.match(r"\*\*(\d{1,2}:\d{2})\*\*\s*(.+)", line.strip())
        if m:
            out.append({"t": m.group(1), "s": html(m.group(2)).replace("<p>", "").replace("</p>", "")})
    return out


def parse_day(title, body):
    """«День 1 · понедельник, 3 августа» + шапка с залом, темой и едой."""
    n = int(re.search(r"День\s+(\d+)", title).group(1))
    weekday = ""
    iso = ""
    m = re.search(r"·\s*([а-яё]+),\s*(\d{1,2})\s+([а-яё]+)", title)
    if m:
        weekday = m.group(1)
        iso = date(YEAR, MONTHS[m.group(3)], int(m.group(2))).isoformat()

    lines = body.strip().splitlines()
    meta_line = lines[0] if lines else ""
    rest = "\n".join(lines[1:])

    def grab(label):
        # «**Зал: кардио**» и «Тема: **DNS**» — обе формы встречаются в шапке
        for pattern in (r"\*\*%s:\s*(.+?)\*\*", r"%s:\s*\*\*(.+?)\*\*"):
            m = re.search(pattern % label, meta_line)
            if m:
                return m.group(1).strip()
        return ""

    gym = grab("Зал")
    topic = grab("Тема")
    if not topic:
        # дни 14 и 15 вместо темы несут одиночную пометку: **Самоэкзамен**, **Финал**
        for chunk in re.findall(r"\*\*(.+?)\*\*", meta_line):
            if not re.match(r"(Зал|Тема|Обед|Ужин):", chunk):
                topic = chunk.strip()
                break

    return {
        "n": n,
        "date": iso,
        "weekday": weekday,
        "gym": gym,
        "topic": topic,
        "lunch": grab("Обед"),
        "dinner": grab("Ужин"),
        "html": html(rest),
    }


def build_sprint():
    text = read("РАСПОРЯДОК.md")
    intro, h1 = split_headings(text, 1)
    sec = {t: b for t, b in h1}

    skeleton_intro, skeleton_parts = split_headings(sec["Скелет дня"], 2)
    schedule = []
    skeleton_html = [html(skeleton_intro)]
    for title, body in skeleton_parts:
        if title == "Расписание":
            schedule = parse_schedule(body)
            continue
        skeleton_html.append("<h3>%s</h3>%s" % (title, html(body)))

    _, day_parts = split_headings(sec["Дни"], 2)
    days = [parse_day(t, b) for t, b in day_parts]

    checklist = re.findall(r"^- \[ \]\s*(.+)$", sec["Чек-лист дня"], re.M)

    extras = []
    for key, title in [
        ("Если что-то пошло не так", "Если что-то пошло не так"),
        ("До завтра", "Подготовка"),
    ]:
        if key in sec:
            extras.append({"id": slug(key), "title": title, "html": html(sec[key])})

    first = next((d["date"] for d in days if d["date"]), "")
    last = next((d["date"] for d in reversed(days) if d["date"]), "")

    return {
        "id": "sprint-2026-08",
        "title": "Рывок · 3–17 августа",
        "short": "Рывок",
        "kind": "plan",
        "start": first,
        "end": last,
        "note": html(intro.split("\n", 1)[1] if "\n" in intro else ""),
        "skeletonHtml": "".join(x for x in skeleton_html if x),
        "schedule": schedule,
        "checklist": checklist,
        "days": days,
        "extras": extras,
    }


# ─────────────────────────── кухня и справка ───────────────────────────

PHOTOS = {
    "poulet-basquaise": "01-poulet-basquaise",
    "piperade": "02-piperade",
    "omelette": "03-omelette-fines-herbes",
    "ratatouille": "04-ratatouille",
    "saumon": "05-saumon-papillote",
    "crevettes": "06-crevettes-ail-persil",
    "lentilles": "07-salade-lentilles",
    "escalope": "08-escalope-moutarde",
    "vinaigrette": "09-vinaigrette-maison",
}


def photo_for(title):
    s = slug(title)
    for key, name in PHOTOS.items():
        if key in s:
            return name
    return ""


def build_doc(filename, doc_id, title):
    """Документ → плоский список разделов в порядке текста."""
    text = read(filename)
    intro, h1 = split_headings(text, 1)
    sections = []
    for h1_title, h1_body in h1:
        h2_intro, h2_parts = split_headings(h1_body, 2)
        sections.append({
            "id": slug(h1_title),
            "level": 1,
            "title": h1_title,
            "html": html(h2_intro),
        })
        for h2_title, h2_body in h2_parts:
            sections.append({
                "id": slug(h1_title + "-" + h2_title),
                "level": 2,
                "title": h2_title,
                "html": html(h2_body),
                "photo": photo_for(h2_title),
            })
    return {"id": doc_id, "title": title, "html": html(intro), "sections": sections}


DISH = re.compile(r"^(\d+\s*·|Sauce\b|Gremolata|Déglaçage)", re.I)


def build_recipes(docs):
    """Индекс блюд: карточки, на которые ссылается день. Фото есть только у кухни."""
    out = []
    for doc in docs:
        if doc["id"] not in ("cuisine", "salades"):
            continue
        group = ""
        for s in doc["sections"]:
            if s["level"] == 1:
                group = re.sub(r"^База\s*·\s*", "", s["title"]).strip()
                if "vinaigrette" in slug(s["title"]) and s["html"]:
                    out.append({
                        "id": slug(s["title"]), "title": group, "group": "База",
                        "doc": doc["id"], "sec": s["id"],
                        "photo": photo_for(s["title"]), "html": s["html"],
                    })
                continue
            if not DISH.match(s["title"]):
                continue
            name = re.sub(r"^\d+\s*·\s*", "", s["title"]).strip()
            out.append({
                "id": slug(name), "title": name, "group": group,
                "doc": doc["id"], "sec": s["id"],
                "photo": s["photo"] if doc["id"] == "cuisine" else "",
                "html": s["html"],
            })
    return out


def main():
    docs = [
        build_doc("Рацион.md", "racion", "Рацион"),
        build_doc("Французская_кухня.md", "cuisine", "Французская кухня"),
        build_doc("Салаты_и_соусы.md", "salades", "Салаты и соусы"),
        build_doc("Вкус.md", "gout", "Вкус"),
        build_doc("Что_это_значит.md", "glossaire", "Что это значит"),
    ]

    data = {
        "v": 1,
        "generated": date.today().isoformat(),
        "periods": [build_sprint()],
        "recipes": build_recipes(docs),
        "docs": docs,
    }

    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    p = data["periods"][0]
    size = OUT.stat().st_size / 1024
    print("периодов: %d, дней: %d, чек-лист: %d пунктов, расписание: %d строк"
          % (len(data["periods"]), len(p["days"]), len(p["checklist"]), len(p["schedule"])))
    print("блюд: %d (с фото %d), документов: %d"
          % (len(data["recipes"]), sum(1 for r in data["recipes"] if r["photo"]), len(docs)))
    print("%s — %.1f КБ" % (OUT.name, size))
    for d in p["days"]:
        if not (d["date"] and d["gym"] and d["topic"]):
            print("  ! день %s разобран не полностью: %s" % (d["n"], d))


if __name__ == "__main__":
    main()
